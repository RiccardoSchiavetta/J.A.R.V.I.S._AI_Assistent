import os
import time
import requests
import json
import speech_recognition as sr
import subprocess
import threading
import logging
import struct
import wave
import math
import re
import queue
from collections import deque
from datetime import datetime, timedelta, time as dtime
from flask import Flask, jsonify, Response, request
from gtts import gTTS

import comandi
import musica
import promemoria
import riposo

try:
    import config
    API_KEY = config.GROQ_API_KEY
except (ImportError, AttributeError):
    print("ERRORE: config.py non trovato o senza GROQ_API_KEY!")
    print("Crea un file config.py con la variabile GROQ_API_KEY = 'la_tua_chiave'")
    exit()

# Opzionali in config.py: se mancano, il calendario resta disattivato e il meteo usa i default
GIORNI_AVANTI = getattr(config, "GIORNI_AVANTI", 60)  # quanti giorni in avanti leggere dal calendario
AGGIORNA_CALENDARIO_SEC = max(15, int(getattr(config, "AGGIORNA_CALENDARIO_SEC", 60)))  # ogni quanto rileggerlo
CALENDARIO_NOCACHE = getattr(config, "CALENDARIO_NOCACHE", True)  # chiede il feed senza copie in cache
EVENTI_PER_IL_MODELLO = 15  # quanti eventi passare a Jarvis quando risponde a voce

# Musica, timer e sveglie (tutto opzionale in config.py)
DATI_DIR = os.path.expanduser(getattr(config, "DATI_DIR", "~/.jarvis"))  # qui si salvano timer e sveglie
RADIO_PRESET = getattr(config, "RADIO", {})                      # {"deejay": "https://..."}: radio preferite con il loro link
RADIO_PREFERITA = getattr(config, "RADIO_PREFERITA", "")         # per "metti un po' di musica" e per le sveglie con la musica
MUSICA_CARTELLE = getattr(config, "MUSICA_CARTELLE", ["~/storage/music"])  # file audio della tablet
MUSICA_YOUTUBE = getattr(config, "MUSICA_YOUTUBE", True)         # "metti i Queen" cerca su YouTube (serve yt-dlp)
ADB_DISPOSITIVO = getattr(config, "ADB_DISPOSITIVO", None)       # es. "localhost:5555": tasti multimediali per Amazon Music & co.
VOLUME_MUSICA = int(getattr(config, "VOLUME_MUSICA", 60))        # volume iniziale del lettore (0-100)
DUCKING = float(getattr(config, "DUCKING", 0.25))                # a che frazione scende la musica mentre Jarvis ascolta
SVEGLIA_MAX_SEC = int(getattr(config, "SVEGLIA_MAX_SEC", 300))   # dopo quanto una sveglia smette da sola di suonare
SNOOZE_MIN = int(getattr(config, "SNOOZE_MIN", 10))              # minuti di "rimanda"

# Riposo: la "notte" automatica (di default 00:00-08:00) e il riposo manuale ("Jarvis, sto uscendo")
NOTTE_INIZIO = int(getattr(config, "NOTTE_INIZIO", 0))
NOTTE_FINE = int(getattr(config, "NOTTE_FINE", 8))
LINGUE_RIPOSO = ("it-IT", "en-US")   # da riposo si ascolta anche in inglese: "wake up, daddy's home"
# Groq cambia spesso i modelli (compound-mini e' stato spento il 21/09/2026): tienilo in config.py
GROQ_MODEL = getattr(config, "GROQ_MODEL", "openai/gpt-oss-120b")


def _lista_url(valore):
    """Accetta una stringa o una lista di stringhe (uno o piu' feed iCal)."""
    if not valore:
        return []
    if isinstance(valore, str):
        return [valore]
    return [u for u in valore if u]


# Feed iCal: l'indirizzo segreto di Google Calendar, piu' eventuali altri calendari (es. Formula 1)
ICAL_URLS = _lista_url(getattr(config, "ICAL_URLS", None) or getattr(config, "ICAL_URL", None))
METEO_LAT = getattr(config, "METEO_LAT", 41.686)  # default: Velletri
METEO_LON = getattr(config, "METEO_LON", 12.778)

URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"

# Fuso orario (serve "pip install tzdata" su Termux; altrimenti usa quello del dispositivo)
try:
    from zoneinfo import ZoneInfo
    LOCALE_TZ = ZoneInfo("Europe/Rome")
except Exception:
    LOCALE_TZ = datetime.now().astimezone().tzinfo


def adesso():
    return datetime.now(LOCALE_TZ)


GIORNI_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
           "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def data_ora_it():
    n = adesso()
    return f"{GIORNI_IT[n.weekday()]} {n.day} {MESI_IT[n.month - 1]} {n.year}, ore {n:%H:%M}"


# Alias wake word (confronto a parole intere, vedi RE_JARVIS)
ALIAS_JARVIS = [
    "jarvis", "giarvis", "iarvis",
    "service", "servis", "services",
    "travis", "davis", "mavis", "harvest",
    "svegliati", "computer", "assistente"
]

# Alias comando di spegnimento
ALIAS_SPEGNITI = [
    "spegniti", "spegneti", "spegni ti",
    "shutdown", "shut down", "esci",
    "chiudi tutto", "termina", "addio"
]


def _compila(alias):
    return re.compile(r"\b(?:" + "|".join(re.escape(a) for a in alias) + r")\b")


RE_JARVIS = _compila(ALIAS_JARVIS)
RE_SPEGNITI = _compila(ALIAS_SPEGNITI)

# Testo di default
TESTO_DEFAULT = "Sistemi Online. Sono a sua piena disposizione Signore."
HUD_STATO = "INIZIALIZZAZIONE"
HUD_TESTO = TESTO_DEFAULT

# Impostazioni audio
SOGLIA_RUMORE = 800        # soglia minima: l'adattiva la alza se la stanza e' rumorosa
TEMPO_SILENZIO_STOP = 1.2  # secondi di silenzio dopo il parlato prima di chiudere la registrazione
MAX_DURATA = 20
RMS_RECENTI = deque(maxlen=120)  # ~4 s di chunk, per stimare il rumore di fondo

# Memoria breve della conversazione
CRONOLOGIA = []
ULTIMO_SCAMBIO = 0.0
MAX_SCAMBI = 4
SCADENZA_CRONOLOGIA = 180  # secondi di inattivita' dopo i quali si dimentica tutto

# Configurazione App (solo questi pacchetti possono essere lanciati)
LISTA_APP = getattr(config, "LISTA_APP", {
    "spotify": "com.spotify.music",
    "orologio": "com.android.deskclock",
    "sveglia": "com.android.deskclock",
    "calendario": "com.android.calendar"
})
PACCHETTI_CONSENTITI = set(LISTA_APP.values())

# Dati per la dashboard (aggiornati da un thread in background)
CACHE = {"eventi": [], "cal_stato": "caricamento", "cal_ts": None, "meteo": None, "meteo_ts": None}
LOCK_CACHE = threading.Lock()

# Coda degli annunci da leggere, timer/sveglie persistenti, lettore musicale, suoneria
ANNUNCI = queue.Queue()
PROM = promemoria.Promemoria(os.path.join(DATI_DIR, "promemoria.json"), adesso)
LETTORE = musica.Lettore(volume_iniziale=VOLUME_MUSICA)
SUONERIA = musica.Suoneria()
FILE_SUONERIA = os.path.join(DATI_DIR, "suoneria.wav")
SQUILLO = {"voce": None, "inizio": 0.0, "radio": False}  # sveglia o timer che sta suonando adesso
PARLA_ORA = threading.Event()                              # "tocca per parlare" dallo schermo
RIPOSO = riposo.Riposo(os.path.join(DATI_DIR, "riposo.json"), adesso, NOTTE_INIZIO, NOTTE_FINE)

# Server web
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

MANIFEST_JSON = {
    "name": "J.A.R.V.I.S.",
    "short_name": "Jarvis",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#000000",
    "theme_color": "#000000",
    "icons": [{"src": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png", "sizes": "192x192", "type": "image/png"}]
}

HTML_HUD = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>J.A.R.V.I.S.</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#000000">
<link rel="manifest" href="/manifest.json">
<style>
:root { --c: #00e5ff; --linea: rgba(0,229,255,.28); --warn: #ffd633; --ok: #33ff77; --err: #ff4040; }
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; }
body {
    background-color: #000; color: var(--c);
    font-family: 'Courier New', Courier, monospace;
    overflow: hidden; cursor: none;
    background-image:
        linear-gradient(rgba(0,229,255,.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,229,255,.04) 1px, transparent 1px);
    background-size: 40px 40px;
}
#reactor { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; pointer-events: none; z-index: 0; }
.anello { position: absolute; border-radius: 50%; will-change: transform; }
.a1 { width: min(80vw, 130vh); height: min(80vw, 130vh); border: 2px dashed rgba(0,229,255,.12); animation: spin 40s linear infinite; }
.a2 { width: min(55vw, 90vh); height: min(55vw, 90vh); border: 4px solid rgba(0,229,255,.06); border-top-color: rgba(0,229,255,.3); animation: spin-rev 20s linear infinite; }
body.ascolto .a2 { animation-duration: 9s; }
body.parla .a2 { animation-duration: 4s; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes spin-rev { to { transform: rotate(-360deg); } }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .55; } }

#app {
    position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 1;
    display: grid; grid-template-columns: 5fr 6fr; grid-template-rows: auto minmax(0, 1fr) auto;
    gap: 2.5vh 2.5vw; padding: 3vh 3vw;
}
#titolo { grid-column: 1 / span 2; grid-row: 1; text-align: center; font-size: min(2.8vw, 5vh); font-weight: bold; letter-spacing: .5em; padding: 0 0 1.2vh .5em; line-height: 1; border-bottom: 1px solid var(--linea); text-shadow: 0 0 16px rgba(0,229,255,.7); }
#sx { grid-column: 1; grid-row: 2; display: flex; flex-direction: column; justify-content: space-between; gap: 2vh; min-width: 0; }
#dx { grid-column: 2; grid-row: 2; overflow: hidden; min-width: 0; display: flex; flex-direction: column; }
#eventi { flex: 1; min-height: 0; overflow: hidden; }
#barra { grid-column: 1 / span 2; grid-row: 3; }
.pannello { border: 1px solid var(--linea); border-radius: 12px; padding: 2vh 1.6vw; background: rgba(0,0,0,.6); }
.titolo { font-size: min(1.5vw, 2.6vh); letter-spacing: 4px; opacity: .65; margin-bottom: 1.4vh; display: flex; justify-content: space-between; }
.titolo .agg { color: var(--warn); letter-spacing: 1px; }
.titolo .agg.ok { color: var(--c); opacity: .7; }

#clock { font-size: min(12vw, 30vh); font-weight: bold; line-height: 1; white-space: nowrap; text-shadow: 0 0 18px rgba(0,229,255,.7); }
#seconds { font-size: .2em; opacity: .75; margin-left: .3em; text-shadow: none; }
/* Molto spazio in altezza (es. schermo intero): ore sopra e minuti sotto, stesso font, nessuna deformazione */
#sx.impilato #alto { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: row; align-items: flex-start; gap: 2.2vw; }
#sx.impilato #clock { display: flex; align-items: flex-end; gap: .1em; font-size: var(--fs, 20vh); line-height: .84; flex: 0 0 auto; }
#sx.impilato #ore { display: flex; flex-direction: column; }
#sx.impilato #sep { display: none; }
#sx.impilato #seconds { font-size: .2em; margin: 0; line-height: 1; }
#sx.impilato #date span { display: block; white-space: nowrap; }
#sx.impilato #date { font-size: min(2vw, 3.6vh); letter-spacing: 2px; line-height: 1.6; align-self: center; flex: 1; min-width: 0; }
#date { font-size: min(2.2vw, 4vh); letter-spacing: 3px; opacity: .75; }

#meteo { display: flex; flex-wrap: wrap; align-items: baseline; gap: .6vh 1.6vw; }
#meteo .titolo { width: 100%; margin-bottom: .6vh; }
.m-temp { font-size: min(7vw, 13vh); font-weight: bold; line-height: 1; }
.m-desc { font-size: min(2.6vw, 4.6vh); color: #fff; text-transform: uppercase; }
.m-det { width: 100%; font-size: min(2vw, 3.5vh); opacity: .9; display: flex; flex-wrap: wrap; gap: .4vh 1.6vw; }
.warn { color: var(--warn); }
#basso { display: flex; flex-direction: column; gap: 1.2vh; }
#timers { font-size: min(1.9vw, 3.4vh); color: var(--warn); }
#timers div { margin-top: .6vh; }

.giorno { font-size: min(1.5vw, 2.6vh); letter-spacing: 4px; opacity: .6; margin: 1.6vh 0 .6vh; }
.giorno:first-of-type { margin-top: 0; }
.ev { display: flex; gap: 1.4vw; align-items: baseline; font-size: min(2.2vw, 4.2vh); padding: .7vh 0; border-bottom: 1px solid rgba(0,229,255,.12); }
.ev-ora { flex: 0 0 3.7em; }
.ev-ora.tg { flex-basis: 4.9em; }
.ev-tit { flex: 1; min-width: 0; color: #fff; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.ev-tra { flex: 0 0 auto; font-size: .8em; opacity: .8; }
.ev.presto, .ev.presto .ev-tit { color: var(--warn); }
.ev.incorso, .ev.incorso .ev-tit { color: var(--ok); }
.vuoto { font-size: min(2vw, 3.6vh); opacity: .6; }

#barra { border-top: 1px solid var(--linea); padding-top: 1.4vh; }
#status { font-size: min(2.6vw, 4.4vh); font-weight: bold; text-transform: uppercase; animation: pulse 2s infinite; }
#message { font-size: min(1.8vw, 3.2vh); margin-top: .6vh; color: #fff; font-style: italic; min-height: 1.3em;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

#timers .musica { color: var(--c); opacity: .85; font-size: .7em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
#barra { cursor: pointer; }
#squillo { display: none; position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 50; background: rgba(0,0,0,.88);
    flex-direction: column; align-items: center; justify-content: center; gap: 5vh; text-align: center; }
#sq-titolo { font-size: min(7vw, 13vh); font-weight: bold; color: var(--warn); text-shadow: 0 0 24px rgba(255,214,51,.6); animation: pulse 1s infinite; }
#squillo button { font-family: inherit; font-size: min(3vw, 6vh); font-weight: bold; letter-spacing: 3px; color: #000; background: var(--c);
    border: 0; border-radius: 14px; padding: 2.4vh 4vw; margin: 0 1.5vw; }
#squillo button.sec { background: transparent; color: var(--c); border: 2px solid var(--c); }
/* Modalita' notte: solo l'orario, attenuato */
body.notte #titolo, body.notte #dx, body.notte #barra, body.notte #reactor, body.notte #meteo, body.notte #date { display: none; }
body.notte #app { display: flex; align-items: center; justify-content: center; }
body.notte #sx { align-items: center; justify-content: center; }
body.notte #clock { opacity: .35; }
#riposo-label { display: none; text-align: center; font-size: min(2vw, 3.6vh); letter-spacing: .6em; padding-left: .6em; opacity: .35; margin-top: 1vh; }

@media (orientation: portrait) {
    #app { grid-template-columns: 1fr; grid-template-rows: auto auto minmax(0, 1fr) auto; }
    #titolo, #sx, #dx, #barra { grid-column: 1; }
    #titolo { grid-row: 1; } #sx { grid-row: 2; } #dx { grid-row: 3; } #barra { grid-row: 4; }
    #clock { font-size: min(18vw, 14vh); }
}
</style>
</head>
<body onclick="toccoSchermo()">
<div id="reactor"><div class="anello a1"></div><div class="anello a2"></div></div>
<div id="app">
    <header id="titolo">J.A.R.V.I.S.</header>
    <section id="sx">
        <div id="alto">
            <div id="clock"><span id="ore"><span id="hh">00</span><span id="sep">:</span><span id="mm">00</span></span><span id="seconds">00</span></div>
            <div id="date"><span id="d-g">CARICAMENTO...</span> <span id="d-m"></span> <span id="d-a"></span></div>
            <div id="riposo-label">RIPOSO</div>
        </div>
        <div id="basso">
            <div id="timers"></div>
            <div id="meteo" class="pannello"></div>
        </div>
    </section>
    <section id="dx" class="pannello">
        <div class="titolo"><span>PROSSIMI EVENTI</span><span id="cal-agg" class="agg"></span></div>
        <div id="eventi"></div>
    </section>
    <footer id="barra" onclick="event.stopPropagation(); parlaOra()">
        <div id="status">OFFLINE</div>
        <div id="message">...</div>
    </footer>
</div>
<div id="squillo" onclick="event.stopPropagation()">
    <div id="sq-titolo"></div>
    <div><button onclick="inviaAzione('stop')">FERMA</button><button class="sec" onclick="inviaAzione('snooze')">RIMANDA</button></div>
</div>
<script>
const $ = id => document.getElementById(id);
let DASH = null;

function el(tag, cls, testo) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (testo !== undefined) e.textContent = testo;
    return e;
}
function toccoSchermo() {
    if (document.body.classList.contains('notte')) fetch('/risveglia', { method: 'POST' }).catch(() => {});
    toggleFull();
}
function renderRiposo(stato) {
    const era = document.body.classList.contains('notte');
    document.body.classList.toggle('notte', !!stato);
    $('riposo-label').style.display = stato === 'manuale' ? 'block' : 'none';
    if (era !== !!stato) allineaColonne();
}
function toggleFull() {
    if (!document.fullscreenElement) { document.documentElement.requestFullscreen().catch(e => console.log(e)); }
}
function pad(n) { return String(n).padStart(2, '0'); }
function minutiFa(iso) { return iso ? (Date.now() - new Date(iso).getTime()) / 60000 : Infinity; }

function aggiornaOrologio() {
    const now = new Date();
    $('hh').textContent = pad(now.getHours());
    $('mm').textContent = pad(now.getMinutes());
    $('seconds').textContent = pad(now.getSeconds());
    const dataIt = o => now.toLocaleDateString('it-IT', o).toUpperCase();
    $('d-g').textContent = dataIt({ weekday: 'long' });
    $('d-m').textContent = dataIt({ day: 'numeric', month: 'long' });
    $('d-a').textContent = dataIt({ year: 'numeric' });
    renderTimers();
}

function aggiornaStato() {
    fetch('/data').then(r => r.json()).then(data => {
        $('status').textContent = data.stato;
        $('message').textContent = data.testo;
        renderSquillo(data.squillo);
        renderRiposo(data.riposo);
        const s = $('status');
        if (data.stato.includes('PARLANDO')) s.style.color = '#ff3333';
        else if (data.stato.includes('ELABORAZIONE')) s.style.color = '#ffff33';
        else if (data.stato.includes('ASCOLTO') || data.stato.includes('VOCE')) s.style.color = '#00ff00';
        else s.style.color = '#00e5ff';
        document.body.classList.toggle('parla', data.stato.includes('PARLANDO'));
        document.body.classList.toggle('ascolto', data.stato.includes('ASCOLTO') || data.stato.includes('VOCE'));
    }).catch(() => {
        $('status').textContent = 'OFFLINE';
        $('status').style.color = '#ff4040';
        $('message').textContent = 'Server non raggiungibile';
    });
}

function renderSquillo(sq) {
    $('squillo').style.display = sq ? 'flex' : 'none';
    if (sq) $('sq-titolo').textContent = sq.testo;
}
function inviaAzione(azione) {
    fetch('/azione', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ azione: azione }) })
        .then(() => aggiornaStato()).catch(() => {});
}
function parlaOra() { fetch('/parla', { method: 'POST' }).catch(() => {}); }

function aggiornaDash() {
    fetch('/dash').then(r => r.json()).then(d => { DASH = d; renderMeteo(); renderEventi(); renderTimers(); }).catch(() => {});
}

function tra(ms) {
    const m = Math.round(ms / 60000);
    if (m < 1) return 'ora';
    if (m < 60) return 'tra ' + m + ' min';
    const h = Math.floor(m / 60), mm = m % 60;
    if (h < 24) return 'tra ' + h + 'h' + (mm ? ' ' + pad(mm) + 'm' : '');
    const g = Math.floor(h / 24), hh = h % 24;
    return 'tra ' + g + 'g' + (hh ? ' ' + hh + 'h' : '');
}
function etichettaGiorno(d) {
    const oggi = new Date(), dom = new Date();
    dom.setDate(oggi.getDate() + 1);
    if (d.toDateString() === oggi.toDateString()) return 'OGGI';
    if (d.toDateString() === dom.toDateString()) return 'DOMANI';
    return d.toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' }).toUpperCase();
}

function renderEventi() {
    const box = $('eventi'), info = $('cal-agg');
    box.textContent = '';
    info.textContent = '';
    info.className = 'agg';
    if (!DASH) return;
    if (DASH.cal_stato === 'non_configurato') { box.appendChild(el('div', 'vuoto', 'Calendario non configurato')); return; }
    if (DASH.cal_stato === 'caricamento') { box.appendChild(el('div', 'vuoto', 'Caricamento...')); return; }
    if (DASH.cal_stato === 'errore') {
        info.textContent = DASH.cal_ts ? 'NON AGGIORNATO DA ' + Math.round(minutiFa(DASH.cal_ts)) + ' MIN' : 'ERRORE';
    } else if (DASH.cal_ts) {
        const t = new Date(DASH.cal_ts);
        info.className = 'agg ok';
        info.textContent = 'AGG. ' + pad(t.getHours()) + ':' + pad(t.getMinutes());
    }
    const now = new Date();
    const evs = (DASH.eventi || []).filter(e => new Date(e.fine) > now);
    if (!evs.length) { box.appendChild(el('div', 'vuoto', 'Nessun impegno in programma')); return; }
    let ultimo = '';
    for (const e of evs) {
        const ini = new Date(e.inizio), fin = new Date(e.fine);
        const g = etichettaGiorno(ini < now ? now : ini);
        const nuovi = [];
        if (g !== ultimo) nuovi.push(el('div', 'giorno', g));
        const incorso = ini <= now && now < fin;
        const presto = !incorso && (ini - now) < 30 * 60000;
        const riga = el('div', 'ev' + (incorso ? ' incorso' : presto ? ' presto' : ''));
        riga.appendChild(el('span', 'ev-ora' + (e.tutto_giorno ? ' tg' : ''), e.tutto_giorno ? 'GIORNATA' : pad(ini.getHours()) + ':' + pad(ini.getMinutes())));
        riga.appendChild(el('span', 'ev-tit', e.titolo));
        riga.appendChild(el('span', 'ev-tra', e.tutto_giorno ? '' : (incorso ? 'IN CORSO' : tra(ini - now))));
        nuovi.push(riga);
        nuovi.forEach(n => box.appendChild(n));
        // si aggiungono eventi finche' c'e' spazio: il primo che non entra viene tolto e si ferma l'elenco
        if (box.scrollHeight > box.clientHeight + 1) { nuovi.forEach(n => box.removeChild(n)); break; }
        ultimo = g;
    }
}

function renderMeteo() {
    const box = $('meteo');
    box.textContent = '';
    box.appendChild(el('div', 'titolo', 'METEO'));
    const m = DASH && DASH.meteo;
    if (!m) { box.appendChild(el('div', 'vuoto', 'Meteo non disponibile')); return; }
    box.appendChild(el('span', 'm-temp', m.temp + '°'));
    box.appendChild(el('span', 'm-desc', m.desc));
    const det = el('div', 'm-det');
    det.appendChild(el('span', '', 'MIN ' + m.min + '° · MAX ' + m.max + '°'));
    if (m.pioggia !== null) det.appendChild(el('span', m.pioggia >= 50 ? 'warn' : '', 'PIOGGIA 6H ' + m.pioggia + '%'));
    if (m.vento !== null) det.appendChild(el('span', m.vento >= 40 ? 'warn' : '', 'VENTO ' + m.vento + ' KM/H'));
    if (minutiFa(DASH.meteo_ts) > 20) det.appendChild(el('span', 'warn', 'DATI NON AGGIORNATI'));
    box.appendChild(det);
}

function renderTimers() {
    const box = $('timers');
    box.textContent = '';
    if (!DASH) return;
    const now = Date.now();
    const voci = (DASH.promemoria || []).map(p => ({ p: p, rest: Math.round((new Date(p.quando).getTime() - now) / 1000) })).filter(x => x.rest > 0);
    voci.filter(x => x.p.tipo === 'timer').slice(0, 3).forEach(x => {
        const r = x.rest, s = r % 60, m = Math.floor(r % 3600 / 60), h = Math.floor(r / 3600);
        const t = (h ? h + ':' + pad(m) : pad(m)) + ':' + pad(s);
        box.appendChild(el('div', '', 'TIMER ' + (x.p.nome ? x.p.nome.toUpperCase() + ' ' : '') + t));
    });
    voci.filter(x => x.p.tipo === 'sveglia').slice(0, 2).forEach(x => {
        const q = new Date(x.p.quando);
        box.appendChild(el('div', '', 'SVEGLIA ' + pad(q.getHours()) + ':' + pad(q.getMinutes())));
    });
    const mu = DASH.musica;
    if (mu && mu.attiva) box.appendChild(el('div', 'musica', (mu.pausa ? 'IN PAUSA ' : 'MUSICA ') + (mu.titolo || '')));
}

let ULTIMA_ALTEZZA = 0;
function allineaColonne() {
    // Orario+meteo devono avere sempre la stessa altezza del pannello eventi, anche dopo
    // lo schermo intero (alcuni Chrome Android non ricalcolano subito il layout).
    const sx = $('sx'), dx = $('dx');
    sx.classList.remove('impilato');
    sx.style.height = '';
    $('date').style.fontSize = '';
    $('clock').style.fontSize = '';
    if (window.innerWidth > window.innerHeight && !document.body.classList.contains('notte')) {
        const h = Math.round(dx.getBoundingClientRect().height);
        if (h > 0) sx.style.height = h + 'px';
        // spazio vuoto tra orologio (su una riga) e meteo: se e' tanto, l'orologio va su due righe e lo riempie
        const vuoto = $('basso').getBoundingClientRect().top - $('alto').getBoundingClientRect().bottom;
        if (vuoto < 0 || sx.scrollHeight > sx.clientHeight + 1) {
            // timer, sveglie e musica occupano molto: l'orologio si rimpicciolisce quanto serve
            const ck = $('clock');
            let f = parseFloat(getComputedStyle(ck).fontSize);
            while (sx.scrollHeight > sx.clientHeight && f > 40) { f = Math.floor(f * 0.94); ck.style.fontSize = f + 'px'; }
        }
        if (h > 0 && vuoto > h * 0.2) {
            sx.classList.add('impilato');
            const fs = Math.floor(Math.min($('alto').clientHeight / 1.8, sx.clientWidth * 0.4));
            sx.style.setProperty('--fs', fs + 'px');
            // la data si rimpicciolisce finche' "11 NOVEMBRE" sta su una riga sola
            const dt = $('date');
            let f = parseFloat(getComputedStyle(dt).fontSize);
            while (dt.scrollWidth > dt.clientWidth + 1 && f > 14) { f -= 1; dt.style.fontSize = f + 'px'; }
        }
    }
    if (window.innerHeight !== ULTIMA_ALTEZZA) { ULTIMA_ALTEZZA = window.innerHeight; renderEventi(); }
}
window.addEventListener('resize', allineaColonne);
window.addEventListener('orientationchange', () => setTimeout(allineaColonne, 300));
document.addEventListener('fullscreenchange', () => { allineaColonne(); setTimeout(allineaColonne, 300); setTimeout(allineaColonne, 1000); });
setInterval(allineaColonne, 2000);

setInterval(aggiornaOrologio, 1000);
setInterval(aggiornaStato, 1000);
setInterval(aggiornaDash, 15000);
setInterval(renderEventi, 30000);
aggiornaOrologio(); aggiornaStato(); aggiornaDash(); allineaColonne();
</script>
</body>
</html>
"""


@app.route('/')
def index():
    return Response(HTML_HUD, mimetype='text/html')


@app.route('/data')
def get_data():
    voce = SQUILLO["voce"]
    return jsonify({'stato': HUD_STATO, 'testo': HUD_TESTO, 'riposo': RIPOSO.stato(),
                    'squillo': {'testo': testo_squillo(voce)} if voce else None})


@app.route('/risveglia', methods=['POST'])
def risveglia_web():
    """Tocco sullo schermo in riposo: torna sveglio (in silenzio)."""
    return jsonify({"ok": RIPOSO.esci() is not None})


@app.route('/azione', methods=['POST'])
def azione_web():
    """Pulsanti a schermo per la sveglia che suona."""
    a = (request.get_json(silent=True) or {}).get("azione")
    if a == "stop":
        return jsonify({"ok": ferma_squillo()})
    if a == "snooze":
        return jsonify({"ok": rimanda_squillo(SNOOZE_MIN)})
    return jsonify({"ok": False}), 400


@app.route('/parla', methods=['POST'])
def parla_web():
    """Tocco sulla barra di stato: Jarvis ascolta subito, senza wake word (utile con la musica alta)."""
    PARLA_ORA.set()
    return jsonify({"ok": True})


@app.route('/dash')
def get_dash():
    with LOCK_CACHE:
        eventi = list(CACHE["eventi"])
        out = {"cal_stato": CACHE["cal_stato"], "cal_ts": CACHE["cal_ts"],
               "meteo": CACHE["meteo"], "meteo_ts": CACHE["meteo_ts"]}
    out["eventi"] = [{"titolo": e["titolo"], "luogo": e["luogo"], "tutto_giorno": e["tutto_giorno"],
                      "inizio": e["inizio"].isoformat(), "fine": e["fine"].isoformat()} for e in eventi]
    out["promemoria"] = PROM.pubblico()
    try:
        out["musica"] = LETTORE.stato()
    except Exception:
        out["musica"] = {"attiva": False, "pausa": False, "titolo": None}
    return jsonify(out)


@app.route('/manifest.json')
def manifest():
    return Response(json.dumps(MANIFEST_JSON), mimetype='application/json')


def run_web_server():
    # Solo localhost: il browser gira sullo stesso tablet
    app.run(host='127.0.0.1', port=5000, threaded=True)


# ---------------------------------------------------------------------------
# Dati dashboard: calendario (iCal) e meteo (Open-Meteo), aggiornati in background
# ---------------------------------------------------------------------------

def _a_datetime(d):
    """DTSTART/DTEND (date o datetime) -> datetime con fuso."""
    if isinstance(d, datetime):
        if d.tzinfo is None:
            return d.replace(tzinfo=LOCALE_TZ)
        return d.astimezone(LOCALE_TZ)
    return datetime.combine(d, dtime.min, tzinfo=LOCALE_TZ)


FEED = {}  # indice del feed -> {"eventi": [...], "ts": datetime dell'ultimo scaricamento riuscito}


def scarica_feed(url):
    import icalendar
    import recurring_ical_events
    kw = {"timeout": 20}
    if CALENDARIO_NOCACHE:
        # Google puo' servire il feed .ics con ritardo: un parametro diverso a ogni richiesta evita le copie in cache
        kw["params"] = {"_": int(time.time())}
        kw["headers"] = {"Cache-Control": "no-cache", "Pragma": "no-cache"}
    r = requests.get(url, **kw)
    r.raise_for_status()
    cal = icalendar.Calendar.from_ical(r.content)
    ora = adesso()
    eventi = []
    for ev in recurring_ical_events.of(cal).between(ora, ora + timedelta(days=GIORNI_AVANTI)):
        if str(ev.get("STATUS", "")).upper() == "CANCELLED":
            continue
        dtstart = ev.get("DTSTART")
        if dtstart is None:
            continue
        tutto_giorno = not isinstance(dtstart.dt, datetime)
        inizio = _a_datetime(dtstart.dt)
        dtend = ev.get("DTEND")
        if dtend is not None:
            fine = _a_datetime(dtend.dt)
        else:
            fine = inizio + (timedelta(days=1) if tutto_giorno else timedelta(hours=1))
        if fine <= ora:
            continue
        eventi.append({
            "uid": str(ev.get("UID", "")),
            "titolo": str(ev.get("SUMMARY", "(senza titolo)")),
            "luogo": str(ev.get("LOCATION", "")),
            "tutto_giorno": tutto_giorno,
            "inizio": inizio,
            "fine": fine,
        })
    return eventi


def aggiorna_calendario():
    if not ICAL_URLS:
        with LOCK_CACHE:
            CACHE["cal_stato"] = "non_configurato"
        return
    fallito = False
    for i, url in enumerate(ICAL_URLS):
        try:
            FEED[i] = {"eventi": scarica_feed(url), "ts": adesso()}
        except Exception as e:
            # Se un calendario fallisce si tengono i suoi ultimi eventi noti.
            # Mai stampare il messaggio: gli errori di requests contengono l'URL segreto.
            fallito = True
            print(f"[CALENDARIO] calendario {i + 1} errore: {type(e).__name__}")
            if isinstance(e, ImportError):
                print("[CALENDARIO] installa: pip install icalendar recurring-ical-events tzdata")
    ora = adesso()
    eventi = sorted((ev for f in FEED.values() for ev in f["eventi"] if ev["fine"] > ora),
                    key=lambda e: e["inizio"])[:60]
    completo = len(FEED) == len(ICAL_URLS)
    ts = min((f["ts"] for f in FEED.values()), default=None) if completo else None
    with LOCK_CACHE:
        CACHE["eventi"] = eventi
        CACHE["cal_stato"] = "errore" if fallito else "ok"
        CACHE["cal_ts"] = ts.isoformat() if ts else None


CODICI_METEO = {
    0: "sereno", 1: "prevalentemente sereno", 2: "parzialmente nuvoloso", 3: "coperto",
    45: "nebbia", 48: "nebbia con brina", 51: "pioviggine leggera", 53: "pioviggine",
    55: "pioviggine intensa", 56: "pioviggine gelata", 57: "pioviggine gelata",
    61: "pioggia debole", 63: "pioggia", 65: "pioggia forte", 66: "pioggia gelata",
    67: "pioggia gelata forte", 71: "neve debole", 73: "neve", 75: "neve forte",
    77: "nevischio", 80: "rovesci deboli", 81: "rovesci", 82: "rovesci violenti",
    85: "rovesci di neve", 86: "forti rovesci di neve", 95: "temporale",
    96: "temporale con grandine", 99: "temporale con forte grandine",
}


def scarica_meteo():
    params = {
        "latitude": METEO_LAT, "longitude": METEO_LON,
        "current": "temperature_2m,weather_code",
        "hourly": "precipitation_probability,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "Europe/Rome", "forecast_days": 2, "wind_speed_unit": "kmh",
    }
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15)
    r.raise_for_status()
    j = r.json()
    ora_locale = adesso().replace(tzinfo=None, minute=0, second=0, microsecond=0)
    ore = [datetime.fromisoformat(t) for t in j["hourly"]["time"]]
    idx = [i for i, t in enumerate(ore) if t >= ora_locale][:6]
    pioggia = [j["hourly"]["precipitation_probability"][i] for i in idx]
    vento = [j["hourly"]["wind_speed_10m"][i] for i in idx]
    pioggia = [p for p in pioggia if p is not None]
    vento = [v for v in vento if v is not None]
    return {
        "temp": round(j["current"]["temperature_2m"]),
        "desc": CODICI_METEO.get(j["current"]["weather_code"], "variabile"),
        "min": round(j["daily"]["temperature_2m_min"][0]),
        "max": round(j["daily"]["temperature_2m_max"][0]),
        "pioggia": int(max(pioggia)) if pioggia else None,
        "vento": round(max(vento)) if vento else None,
    }


def aggiorna_meteo():
    try:
        meteo = scarica_meteo()
        with LOCK_CACHE:
            CACHE["meteo"] = meteo
            CACHE["meteo_ts"] = adesso().isoformat()
    except Exception as e:
        print(f"[METEO] errore: {type(e).__name__}")


INTERVALLO_METEO = 300


def thread_dati():
    """Rilegge calendario (ogni AGGIORNA_CALENDARIO_SEC) e meteo (ogni 5 minuti), senza mai fermarsi."""
    ultimo_cal = ultimo_meteo = 0.0
    while True:
        try:
            ora = time.time()
            if ora - ultimo_cal >= AGGIORNA_CALENDARIO_SEC:
                ultimo_cal = ora
                aggiorna_calendario()
            if ora - ultimo_meteo >= INTERVALLO_METEO:
                ultimo_meteo = ora
                aggiorna_meteo()
        except Exception as e:
            print(f"[DATI] errore: {type(e).__name__}")
        time.sleep(5)


def _giorno_relativo(dt):
    delta = (dt.date() - adesso().date()).days
    if delta <= 0:
        return "oggi"
    if delta == 1:
        return "domani"
    if delta == 2:
        return "dopodomani"
    if delta < 7:
        return GIORNI_IT[dt.weekday()]
    return f"{dt.day} {MESI_IT[dt.month - 1]}"


def riepilogo_contesto():
    """Testo breve con agenda e meteo, da accodare al messaggio per il modello."""
    with LOCK_CACHE:
        stato = CACHE["cal_stato"]
        eventi = list(CACHE["eventi"])
        meteo = CACHE["meteo"]
    righe = []
    if stato == "non_configurato":
        righe.append("[CALENDARIO: non configurato]")
    elif stato == "caricamento" or (stato == "errore" and not eventi):
        righe.append("[CALENDARIO: non disponibile al momento]")
    else:
        ora = adesso()
        voci = []
        for e in eventi[:EVENTI_PER_IL_MODELLO]:
            if e["fine"] <= ora:
                continue
            titolo = e["titolo"][:60]
            if e["tutto_giorno"]:
                voci.append(f"{_giorno_relativo(max(e['inizio'], ora))} tutto il giorno: {titolo}")
            else:
                voci.append(f"{_giorno_relativo(e['inizio'])} {e['inizio']:%H:%M}: {titolo}")
        if len(eventi) > EVENTI_PER_IL_MODELLO:
            voci.append("altri eventi più avanti")
        nota = " (dati non aggiornati)" if stato == "errore" else ""
        righe.append(f"[CALENDARIO prossimi eventi in ordine, fino a {GIORNI_AVANTI} giorni" + nota + ": " + ("; ".join(voci) if voci else "nessun impegno") + "]")
    if meteo:
        parti = [f"{meteo['temp']} gradi", meteo["desc"], f"minima {meteo['min']}", f"massima {meteo['max']}"]
        if meteo["pioggia"] is not None:
            parti.append(f"probabilità di pioggia fino al {meteo['pioggia']}% nelle prossime 6 ore")
        if meteo["vento"] is not None:
            parti.append(f"vento fino a {meteo['vento']} km/h")
        righe.append("[METEO locale: " + ", ".join(parti) + "]")
    return "\n".join(righe)


# ---------------------------------------------------------------------------
# Timer, sveglie e annunci proattivi
# ---------------------------------------------------------------------------

def ora_silenziosa(ora):
    """Niente annunci del calendario mentre Jarvis e' in riposo (notte o riposo manuale)."""
    return RIPOSO.stato(ora) is not None


def imposta_timer(secondi, nome=None):
    return PROM.aggiungi_timer(secondi, nome)


def imposta_sveglia(ore, minuti):
    return PROM.aggiungi_sveglia(ore, minuti)


def vibra(ms=500):
    try:
        subprocess.run(["termux-vibrate", "-d", str(ms)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass


def testo_squillo(voce):
    if voce["tipo"] == "timer":
        return "TIMER " + (voce["nome"].upper() + " " if voce.get("nome") else "") + "SCADUTO"
    q = datetime.fromisoformat(voce["quando"])
    return f"SVEGLIA {q:%H:%M}" + (" - " + voce["nome"].upper() if voce.get("nome") else "")


def avvia_squillo(voce):
    """Sveglia o timer scaduto: suona (bip oppure la radio scelta) finche' non lo fermi."""
    ferma_squillo()
    SQUILLO.update(voce=voce, inizio=time.time(), radio=False)
    azione = voce.get("azione") or {}
    if "radio" in azione:
        SQUILLO["radio"] = bool(riproduci_radio(azione["radio"]))
    if not SQUILLO["radio"]:
        try:
            if LETTORE.attivo():
                LETTORE.pausa()  # la musica in corso lascia il posto alla sveglia
        except Exception:
            pass
        if not os.path.exists(FILE_SUONERIA):
            musica.crea_suoneria(FILE_SUONERIA)
        SUONERIA.avvia(FILE_SUONERIA)
    vibra(800)
    print(f"[SQUILLO] {testo_squillo(voce)}")


def ferma_squillo():
    voce = SQUILLO["voce"]
    if not voce:
        return False
    SUONERIA.ferma()
    if SQUILLO["radio"]:
        LETTORE.stop()
    SQUILLO.update(voce=None, radio=False)
    return True


def rimanda_squillo(minuti):
    voce = SQUILLO["voce"]
    if not voce:
        return False
    ferma_squillo()
    if voce["tipo"] == "timer":
        PROM.aggiungi_timer(minuti * 60, voce.get("nome"))
    else:
        PROM.rimanda(voce, minuti)
    return True


def controlla_promemoria(annunciati):
    """Fa suonare timer/sveglie scaduti e accoda gli annunci degli eventi del calendario in arrivo."""
    ora = adesso()
    for voce in PROM.scattati():
        avvia_squillo(voce)
    if SQUILLO["voce"]:
        massimo = SVEGLIA_MAX_SEC if SQUILLO["voce"]["tipo"] == "sveglia" else min(120, SVEGLIA_MAX_SEC)
        if time.time() - SQUILLO["inizio"] > massimo:
            ferma_squillo()

    if ora_silenziosa(ora):
        return
    with LOCK_CACHE:
        eventi = list(CACHE["eventi"])
    for ev in eventi:
        if ev["tutto_giorno"]:
            continue
        secondi = (ev["inizio"] - ora).total_seconds()
        base = (ev["uid"], ev["inizio"].isoformat())
        if 30 < secondi <= 900 and base + ("pre",) not in annunciati:
            annunciati.add(base + ("pre",))
            minuti = max(1, round(secondi / 60))
            ANNUNCI.put(f"Signore, tra {minuti} minuti ha: {ev['titolo']}.")
        elif -60 <= secondi <= 30 and base + ("ora",) not in annunciati:
            annunciati.add(base + ("ora",))
            ANNUNCI.put(f"Signore, è l'ora di: {ev['titolo']}.")
    if len(annunciati) > 500:
        annunciati.clear()


def thread_promemoria():
    annunciati = set()
    while True:
        try:
            controlla_promemoria(annunciati)
        except Exception as e:
            print(f"[PROMEMORIA] errore: {type(e).__name__}")
        time.sleep(2)


def svuota_annunci():
    while True:
        try:
            testo = ANNUNCI.get_nowait()
        except queue.Empty:
            return
        parla(testo)


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

def avvia_server_audio():
    os.system("pulseaudio --kill > /dev/null 2>&1")
    time.sleep(1)
    os.system("pulseaudio --start --load=\"module-sles-sink\" --load=\"module-sles-source\" --exit-idle-time=-1 > /dev/null 2>&1")
    time.sleep(1)
    os.system("pacmd set-source-mute 0 0 > /dev/null 2>&1")


def lancia_applicazione(pacchetto):
    # Il pacchetto arriva dall'output del modello: va trattato come input non fidato.
    if pacchetto not in PACCHETTI_CONSENTITI:
        print(f"[SECURITY] Pacchetto rifiutato: {pacchetto!r}")
        return
    if pacchetto == "com.spotify.music":
        cmd = ["termux-open-url", "spotify:"]
    else:
        cmd = ["am", "start", "--user", "0", "-a", "android.intent.action.MAIN",
               "-c", "android.intent.category.LAUNCHER", "-p", pacchetto]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception as e:
        print(f"[SYSTEM] Errore lancio app: {type(e).__name__}")
    print(f"[SYSTEM] Lancio app: {pacchetto}")


def parla(testo):
    global HUD_STATO, HUD_TESTO
    if not testo:
        return

    HUD_STATO = "PARLANDO..."
    HUD_TESTO = testo

    # Gli apostrofi restano: gTTS legge male "lora" al posto di "l'ora"
    testo_pulito = re.sub(r'[*_#`|]', '', testo)
    testo_pulito = re.sub(r'^\s*[-•]\s*', '', testo_pulito, flags=re.MULTILINE)
    testo_pulito = testo_pulito.replace('"', '').replace("\n", " ")
    testo_pulito = re.sub(r'\s+', ' ', testo_pulito).strip()

    print(f"\nJARVIS: {testo_pulito}\n")

    file_mp3 = "google_voice.mp3"

    try:
        tts = gTTS(text=testo_pulito, lang='it')
        tts.save(file_mp3)

        if os.path.exists(file_mp3):
            subprocess.run(["mpv", "--no-terminal", file_mp3],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[TTS] errore: {type(e).__name__}: {e}")
        HUD_STATO = "ERRORE VOCE"
        time.sleep(2)

    HUD_STATO = "IN ATTESA"
    HUD_TESTO = TESTO_DEFAULT


def soglia_corrente():
    """Soglia di parlato: mai sotto SOGLIA_RUMORE, sale se il rumore di fondo recente e' alto."""
    if len(RMS_RECENTI) < 20:
        return SOGLIA_RUMORE
    return min(6000, max(SOGLIA_RUMORE, min(RMS_RECENTI) * 2.5))


def trascrivi(nome_file, lingue=("it-IT",)):
    """Testo sentito nel file: una trascrizione per lingua, unite da " ; "."""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(nome_file) as source:
            audio_data = recognizer.record(source)
    except Exception:
        return ""
    testi = []
    for lingua in lingue:
        try:
            testi.append(recognizer.recognize_google(audio_data, language=lingua).lower())
        except Exception:
            pass
    return " ; ".join(testi)


def ascolta_dinamico(nome_file="mic_monitor.wav", lingue=("it-IT",)):
    global HUD_STATO

    if os.path.exists(nome_file):
        os.remove(nome_file)
    os.system("pkill -x parecord > /dev/null 2>&1")

    # Parametri Audio
    RATE = 16000
    CHUNK = 1024

    comando = ["parecord", "--channels=1", "--rate=16000", "--format=s16le", "--raw"]
    processo = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    HUD_STATO = "IN ASCOLTO"

    frames = []
    inizio_silenzio = None
    ha_parlato = False
    start_time = time.time()

    try:
        while True:
            data = processo.stdout.read(CHUNK)
            if not data:
                break
            data = data[:len(data) // 2 * 2]
            if not data:
                continue
            frames.append(data)

            shorts = struct.unpack(f"{len(data)//2}h", data)
            sum_squares = sum(s**2 for s in shorts)
            rms = math.sqrt(sum_squares / len(shorts))

            # Il rumore di fondo si stima solo prima del parlato
            if not ha_parlato:
                RMS_RECENTI.append(rms)

            if rms > soglia_corrente():
                if not ha_parlato:
                    HUD_STATO = "VOCE RILEVATA..."
                ha_parlato = True
                inizio_silenzio = None
            else:
                if ha_parlato and inizio_silenzio is None:
                    inizio_silenzio = time.time()

            durata_totale = time.time() - start_time

            if ha_parlato and inizio_silenzio and (time.time() - inizio_silenzio > TEMPO_SILENZIO_STOP):
                break
            if durata_totale > MAX_DURATA:
                break
            if not ha_parlato and durata_totale > 5:
                break
            if PARLA_ORA.is_set() and not ha_parlato:
                break  # tocco sullo schermo: si esce subito e si ascolta il comando

    except Exception as e:
        print(e)
    finally:
        processo.terminate()
        try:
            processo.wait(timeout=0.5)
        except Exception:
            processo.kill()

    if not ha_parlato:
        return ""

    with wave.open(nome_file, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    return trascrivi(nome_file, lingue)


# ---------------------------------------------------------------------------
# Cervello Groq
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Sei J.A.R.V.I.S., magiordomo cibernetico di Tony Stark. Dai del Lei, chiama l'utente solo "Signore". Tono colto, elegante, imperturbabile, ironia britannica sottile. Mai slang, mai emozioni esagerate.

LUNGHEZZA (regola assoluta): ogni parola viene letta ad alta voce. Massimo 1 frase per domande dirette, massimo 3 frasi brevi solo se chiesto esplicitamente di analizzare o spiegare. Mai preamboli inutili.

FORMATO: solo testo semplice, mai asterischi, elenchi puntati, tabelle, cancelletti o markdown.

VERITA: se non hai un dato certo dopo aver cercato, ammettilo. Mai inventare. Mai citare fonti web, presenta tutto come dai tuoi sistemi.

IMMERSIONE: non uscire mai dal personaggio. Mai dire "modello linguistico" o "non ho un corpo fisico". Se impossibilitato: "I miei protocolli non permettono l'accesso".

AGENDA E METEO: nel messaggio dell'utente trovi [CALENDARIO] e [METEO locale] già aggiornati. Per impegni, agenda e meteo locale usa SOLO quei dati, senza ricerca web. Mai inventare eventi: se non risulta nulla, dillo. Per il meteo di altre città usa la ricerca web.

RICERCA WEB: per notizie, risultati sportivi, eventi, prezzi, orari o altri dati in tempo reale (esclusi agenda e meteo locale) usa SEMPRE la ricerca web prima di rispondere.

APP: se l'utente chiede di aprire un'app, cerca il pacchetto nella lista SYSTEM APPS del messaggio utente. Rispondi includendo [CMD_OPEN:nome.del.pacchetto]. Se non presente, comunica che non hai accesso a quel protocollo.

TIMER E SVEGLIE: per un timer includi [CMD_TIMER:secondi] (solo il numero di secondi); per una sveglia includi [CMD_ALARM:HH:MM] (24 ore, il prossimo orario futuro). Aggiungi una conferma brevissima.

SALUTI: non presentarti a meno che l'utente non ti saluti. Se va dritto al punto, rispondi al punto."""

RE_OPEN = re.compile(r'\[CMD_OPEN:\s*([A-Za-z0-9_.]+)\s*\]')
RE_TIMER = re.compile(r'\[CMD_TIMER:\s*(\d{1,6})\s*\]')
RE_ALARM = re.compile(r'\[CMD_ALARM:\s*(\d{1,2}):(\d{2})\s*\]')
RE_TAG = re.compile(r'\[CMD_[A-Z]+:[^\]]*\]')


def _registra_scambio(domanda, risposta):
    global ULTIMO_SCAMBIO
    CRONOLOGIA.append({"role": "user", "content": domanda})
    CRONOLOGIA.append({"role": "assistant", "content": RE_TAG.sub("", risposta).strip()})
    del CRONOLOGIA[:-MAX_SCAMBI * 2]
    ULTIMO_SCAMBIO = time.time()


def _errore_groq_parlato(codice):
    """Messaggio parlato in base al motivo reale dell'errore (il dettaglio resta nel terminale)."""
    if codice == 429:
        return "Ho raggiunto il limite di richieste, Signore. Riprovi tra un minuto."
    if codice in (401, 403):
        return "La mia chiave di accesso non risulta valida, Signore."
    if codice == 404:
        return "Il modello configurato non è più disponibile, Signore."
    return "I server neurali richiedono manutenzione, Signore."


def chiedi_a_groq(domanda):
    global HUD_STATO, HUD_TESTO
    HUD_STATO = "ELABORAZIONE..."
    HUD_TESTO = f"Analisi: {domanda}..."

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}',
    }

    if time.time() - ULTIMO_SCAMBIO > SCADENZA_CRONOLOGIA:
        CRONOLOGIA.clear()

    user_content = (f"[SYSTEM DATA: {data_ora_it()}] [SYSTEM APPS: {json.dumps(LISTA_APP)}]\n"
                    f"{riepilogo_contesto()}\n\nDomanda: {domanda}")
    sistema = {"role": "system", "content": SYSTEM_PROMPT}
    utente = {"role": "user", "content": user_content}

    # gpt-oss e' un modello a ragionamento: i token di ragionamento contano nel limite,
    # quindi max_completion_tokens e' ampio (la risposta parlata resta breve per il system prompt).
    payload = {
        "model": GROQ_MODEL,
        "messages": [sistema] + list(CRONOLOGIA) + [utente],
        "temperature": 0.6,
        "max_completion_tokens": 1000,
        "reasoning_effort": "low",
        "tools": [{"type": "browser_search"}],  # ricerca web lato server, il modello decide se usarla
    }

    try:
        r = requests.post(URL_GROQ, headers=headers, data=json.dumps(payload), timeout=30)

        if r.status_code == 413:
            # Piano gratuito: 8000 token al minuto. Se la ricerca web fa sforare, si risponde senza.
            print("[GROQ] 413, riprovo senza ricerca web e senza cronologia...")
            payload.pop("tools", None)
            utente_senza_web = {"role": "user", "content": user_content +
                                "\n[Ricerca web momentaneamente non disponibile: se serve un dato in tempo reale, dillo.]"}
            payload["messages"] = [sistema, utente_senza_web]
            r = requests.post(URL_GROQ, headers=headers, data=json.dumps(payload), timeout=30)

        if r.status_code == 200:
            scelta = r.json()['choices'][0]
            risposta = (scelta['message'].get('content') or "").strip()
            if not risposta:
                print(f"[GROQ] risposta vuota, finish_reason={scelta.get('finish_reason')}")
                return "Non sono riuscito a formulare una risposta, Signore."
            _registra_scambio(domanda, risposta)
            return risposta

        print(f"\n[ERRORE GROQ]: {r.status_code} - {r.text}")
        return _errore_groq_parlato(r.status_code)

    except Exception as e:
        print(f"[ERRORE CONNESSIONE]: {e}")
        return "Sono Offline."


def gestisci_risposta_e_comandi(risposta_completa):
    for m in RE_OPEN.finditer(risposta_completa):
        threading.Thread(target=lancia_applicazione, args=(m.group(1),)).start()

    for m in RE_TIMER.finditer(risposta_completa):
        imposta_timer(int(m.group(1)))

    for m in RE_ALARM.finditer(risposta_completa):
        ore, minuti = int(m.group(1)), int(m.group(2))
        if 0 <= ore < 24 and 0 <= minuti < 60:
            imposta_sveglia(ore, minuti)

    parla(RE_TAG.sub("", risposta_completa).strip())


def _quando_parlato(q):
    delta = (q.date() - adesso().date()).days
    if delta == 0:
        return "oggi"
    if delta == 1:
        return "domani"
    if delta == 2:
        return "dopodomani"
    return f"{GIORNI_IT[q.weekday()]} {q.day} {MESI_IT[q.month - 1]}"


def risolvi_radio(nome):
    """(titolo, url): prima le radio di config.py (RADIO), poi la ricerca su radio-browser.info."""
    n = (nome or RADIO_PREFERITA or "").strip().lower()
    if not n:
        return None
    for chiave, url in RADIO_PRESET.items():
        if chiave.lower() in n or n in chiave.lower():
            return chiave, url
    ris = musica.cerca_radio(n)
    return ris[0] if ris else None


def riproduci_radio(nome):
    r = risolvi_radio(nome)
    return bool(r and LETTORE.riproduci(r[1], titolo=r[0]))


def _musica_attiva():
    try:
        return LETTORE.attivo()
    except Exception:
        return False


def esegui_intent(i):
    """Esegue un comando riconosciuto da comandi.interpreta().

    Restituisce None se non sa gestirlo (si passa al modello), "" se e' fatto in silenzio
    (es. pausa: la musica che cambia e' gia' la risposta), altrimenti la frase da dire."""
    t = i["tipo"]
    adesso_ = adesso()

    if t == "ora":
        h, m = adesso_.hour, adesso_.minute
        if (h, m) == (0, 0):
            return "È mezzanotte, Signore."
        if h == 1:
            return "È l'una" + (f" e {m}" if m else "") + ", Signore."
        return f"Sono le {h}" + (f" e {m}" if m else "") + ", Signore."
    if t == "data":
        return f"Oggi è {GIORNI_IT[adesso_.weekday()]} {adesso_.day} {MESI_IT[adesso_.month - 1]} {adesso_.year}, Signore."

    # --- timer ---
    if t == "timer":
        v = PROM.aggiungi_timer(i["secondi"], i.get("nome"))
        nome = f" {v['nome']}" if v.get("nome") else ""
        return f"Timer{nome} di {comandi.durata_parlata(v['durata'])} impostato."
    if t == "timer_quanto":
        timer = PROM.quanto_manca()
        if not timer:
            return "Non ci sono timer attivi, Signore."
        parti = [(f"{v['nome']}: " if v.get("nome") else "") + comandi.durata_parlata(sec) for v, sec in timer]
        if len(timer) == 1:
            v = timer[0][0]
            return f"Al timer{' ' + v['nome'] if v.get('nome') else ''} mancano {comandi.durata_parlata(timer[0][1])}."
        return "Timer attivi. " + ". ".join(parti) + "."
    if t == "timer_cancella":
        timer = PROM.elenco("timer")
        if not timer:
            return "Non ci sono timer da cancellare, Signore."
        if i.get("nome"):
            n = PROM.cancella(tipo="timer", nome=i["nome"])
            return "Timer cancellato." if n else f"Non trovo un timer {i['nome']}, Signore."
        if i.get("tutti") or len(timer) == 1:
            n = PROM.cancella(tipo="timer", tutti=True)
            return "Timer cancellato." if n == 1 else "Timer cancellati."
        return "Ho più timer attivi, Signore: dica quale, oppure cancelli tutti i timer."

    # --- sveglie ---
    if t == "sveglia":
        azione = {"radio": i["radio"]} if i.get("radio") is not None else None
        if i.get("giorni"):
            ore = comandi.ore_ricorrente(i["ore"], i["qual"])
            PROM.aggiungi_sveglia(ore, i["minuti"], giorni=i["giorni"], azione=azione)
            return f"Sveglia impostata per {comandi.orario_parlato(ore, i['minuti'])}, {comandi.giorni_parlati(i['giorni'])}."
        quando = comandi.istante_sveglia(i["ore"], i["minuti"], i["qual"], adesso_, data=i.get("data"), weekday=i.get("weekday"))
        PROM.aggiungi_sveglia(quando.hour, quando.minute, None, azione, quando=quando)
        return f"Sveglia impostata per {comandi.orario_parlato(quando.hour, quando.minute)}, {_quando_parlato(quando)}."
    if t == "sveglia_tra":
        azione = {"radio": i["radio"]} if i.get("radio") is not None else None
        PROM.aggiungi_sveglia_tra(i["secondi"], azione)
        return f"Sveglia impostata tra {comandi.durata_parlata(i['secondi'])}."
    if t == "sveglie_elenco":
        voci = PROM.elenco("sveglia")
        if not voci:
            return "Non ci sono sveglie attive, Signore."
        parti = []
        for v in voci:
            q = datetime.fromisoformat(v["quando"])
            quando = comandi.giorni_parlati(v["giorni"]) if v.get("giorni") else _quando_parlato(q)
            parti.append(f"{comandi.orario_parlato(q.hour, q.minute)}, {quando}")
        return ("Una sveglia: " if len(parti) == 1 else f"{len(parti)} sveglie: ") + ". ".join(parti) + "."
    if t == "sveglia_cancella":
        voci = PROM.elenco("sveglia")
        if not voci:
            return "Non ci sono sveglie da cancellare, Signore."
        if i.get("ore") is not None:
            n = PROM.cancella(tipo="sveglia", ore=i["ore"], minuti=i["minuti"], qual=i.get("qual"))
            return "Sveglia cancellata." if n else "Non trovo una sveglia a quell'ora, Signore."
        if i.get("tutte") or len(voci) == 1:
            n = PROM.cancella(tipo="sveglia", tutti=True)
            return "Sveglia cancellata." if n == 1 else "Sveglie cancellate."
        return "Ho più sveglie attive, Signore: dica a che ora, oppure cancelli tutte le sveglie."

    # --- riposo ---
    if t == "riposo_entra":
        RIPOSO.entra()
        if _musica_attiva():
            LETTORE.stop()
        return "A più tardi, Signore. Entro in modalità riposo."
    if t == "riposo_esci":
        if RIPOSO.stato() is None:
            return "Sono già sveglio, Signore."
        RIPOSO.esci()
        return benvenuto()

    # --- stop / rimanda ---
    if t == "stop":
        if ferma_squillo():
            return ""
        if _musica_attiva():
            LETTORE.stop()
        return ""
    if t == "snooze":
        minuti = i.get("minuti") or SNOOZE_MIN
        if rimanda_squillo(minuti):
            return f"Rimando di {minuti} minuti."
        return "Non c'è nessuna sveglia che suona, Signore."

    # --- controllo della musica ---
    if t in ("musica_pausa", "musica_riprendi", "musica_prossima", "musica_precedente", "musica_stop"):
        nome = t[len("musica_"):]
        if _musica_attiva():
            ok = {"pausa": LETTORE.pausa, "riprendi": LETTORE.riprendi, "prossima": LETTORE.prossima,
                  "precedente": LETTORE.precedente, "stop": LETTORE.stop}[nome]()
            if not ok and nome in ("prossima", "precedente"):
                return "Non c'è un altro brano in lista, Signore."
            return ""
        if musica.tasto_sistema(nome, ADB_DISPOSITIVO):  # per esempio Amazon Music
            return ""
        return "" if nome == "stop" else None  # senza musica, "continua"/"avanti" restano frasi normali
    if t in ("volume_delta", "volume_imposta"):
        if _musica_attiva():
            if t == "volume_delta":
                LETTORE.volume_delta(i["delta"])
            else:
                LETTORE.imposta_volume(i["valore"])
            return ""
        livello = musica.volume_sistema(delta=i.get("delta"), valore=i.get("valore"))
        return "" if livello is not None else None
    if t == "musica_cosa":
        st = LETTORE.stato()
        if st["attiva"] and st["titolo"]:
            return f"Sta suonando {st['titolo']}, Signore."
        return "Non c'è nulla in riproduzione che io possa vedere, Signore."

    # --- avvio della musica ---
    if t == "radio":
        nome = i.get("nome") or RADIO_PREFERITA
        if not nome:
            return "Quale radio vuole ascoltare, Signore?"
        return "" if riproduci_radio(nome) else f"Non riesco a trovare la radio {nome}, Signore."
    if t == "musica_locale":
        files = musica.trova_musica(MUSICA_CARTELLE)
        if files and LETTORE.riproduci_lista(files, titolo="La mia musica"):
            return ""
        if RADIO_PREFERITA and riproduci_radio(RADIO_PREFERITA):
            return ""
        return "Non ho musica sulla tablet né una radio preferita, Signore. Provi con: metti radio deejay."
    if t == "cerca_musica":
        if not MUSICA_YOUTUBE or not musica.youtube_disponibile():
            return "Per cercare musica su internet serve yt-dlp, Signore."
        return "" if LETTORE.riproduci(musica.sorgente_youtube(i["query"]), titolo=i["query"]) else "Non riesco ad avviare la musica, Signore."

    # --- apri app ---
    if t == "apri_app":
        nome = i["nome"]
        for chiave, pacchetto in LISTA_APP.items():
            if chiave == nome or chiave in nome or nome in chiave:
                threading.Thread(target=lancia_applicazione, args=(pacchetto,)).start()
                return ""
        return None
    return None


def _alle(h, m):
    if (h, m) == (0, 0):
        return "a mezzanotte"
    return ("all'una" if h == 1 else f"alle {h}") + (f" e {m}" if m else "")


def benvenuto():
    """Il saluto al ritorno ("wake up, daddy's home"), con il prossimo impegno se c'e'."""
    testo = "Bentornato a casa, Signore."
    ora = adesso()
    with LOCK_CACHE:
        futuri = [e for e in CACHE["eventi"] if e["inizio"] > ora]
    if futuri:
        e = futuri[0]
        quando = _giorno_relativo(e["inizio"])
        testo += f" Il prossimo impegno è {e['titolo']}, {quando}"
        testo += "." if e["tutto_giorno"] else f" {_alle(e['inizio'].hour, e['inizio'].minute)}."
    return testo


def risveglia():
    """Risveglio a voce dal riposo: il saluto viene letto dalla coda degli annunci."""
    if RIPOSO.esci() is not None:
        ANNUNCI.put(benvenuto())


def rispondi(testo):
    """Un comando detto a voce: prima il riconoscimento locale (istantaneo), poi il modello."""
    global HUD_STATO, HUD_TESTO
    HUD_TESTO = f"Comando: {testo}"
    try:
        intent = comandi.interpreta(testo, app_note=tuple(LISTA_APP))
        risposta = esegui_intent(intent) if intent else None
    except Exception as e:
        print(f"[COMANDO] errore: {type(e).__name__}: {e}")
        risposta = "Non sono riuscito a eseguire il comando, Signore."
    if risposta is not None:
        if risposta:
            parla(risposta)
        else:
            HUD_STATO = "IN ATTESA"
            HUD_TESTO = TESTO_DEFAULT
        return
    gestisci_risposta_e_comandi(chiedi_a_groq(testo))


def _e_spegnimento(frase):
    """Spegnimento vocale ("esci", "shutdown"...), tranne le frasi di riposo come "esci dalla modalità riposo"."""
    if not RE_SPEGNITI.search(frase):
        return False
    intent = comandi.interpreta(frase)
    return not (intent and intent["tipo"] in ("riposo_entra", "riposo_esci"))


def gestisci_attivazione(frase_udita):
    """Wake word sentita. Restituisce True se Jarvis va spento."""
    global HUD_STATO
    if _e_spegnimento(frase_udita):
        spegni_sistemi()
        return True
    HUD_STATO = "WAKE WORD RILEVATA"
    os.system("termux-vibrate -d 100 > /dev/null 2>&1")
    with LETTORE.ducking(DUCKING):  # la musica si abbassa mentre ascolto e rispondo
        if len(frase_udita.split()) <= 2:
            parla("Sì Signore?")
            comando = ascolta_dinamico()
            if not comando:
                parla("Non ho udito alcun comando, Signore.")
                return False
            if _e_spegnimento(comando):
                spegni_sistemi()
                return True
            rispondi(comando)
        else:
            rispondi(frase_udita)
    return False


def gestisci_parla_ora():
    """Tocco sulla barra di stato: ascolta subito il comando, senza wake word."""
    global HUD_STATO
    PARLA_ORA.clear()
    HUD_STATO = "WAKE WORD RILEVATA"
    os.system("termux-vibrate -d 100 > /dev/null 2>&1")
    with LETTORE.ducking(DUCKING):
        comando = ascolta_dinamico()
        if not comando:
            HUD_STATO = "IN ATTESA"
            return False
        if _e_spegnimento(comando):
            spegni_sistemi()
            return True
        rispondi(comando)
    return False


def spegni_sistemi():
    global HUD_STATO, HUD_TESTO
    HUD_STATO = "SPEGNIMENTO"
    ferma_squillo()
    LETTORE.chiudi()
    parla("Spengo i sistemi. È stato un piacere servirla, Signore.")
    HUD_STATO = "OFFLINE"
    HUD_TESTO = "Sistemi Offline."
    os.system("termux-wake-unlock > /dev/null 2>&1")
    print("\n--- JARVIS SPENTO ---")


def main():
    global HUD_STATO, HUD_TESTO
    os.system("clear")
    os.system("termux-wake-lock")
    print("--- INIZIALIZZAZIONE ---")

    for target in (run_web_server, thread_dati, thread_promemoria):
        threading.Thread(target=target, daemon=True).start()
    print("--- INTERFACCIA: http://localhost:5000 ---")
    if not ICAL_URLS:
        print("[CALENDARIO] ICAL_URL non impostato in config.py: pannello calendario disattivato")

    avvia_server_audio()
    time.sleep(2)
    parla(TESTO_DEFAULT)
    HUD_STATO = "IN ATTESA"

    while True:
        svuota_annunci()
        if PARLA_ORA.is_set():
            if gestisci_parla_ora():
                return
            continue
        print(".", end="", flush=True)
        try:
            # da riposo si ascolta anche in inglese, per "wake up, daddy's home"
            frase_udita = ascolta_dinamico(lingue=LINGUE_RIPOSO if RIPOSO.stato() else ("it-IT",))
        except Exception:
            avvia_server_audio()
            continue

        if not frase_udita:
            continue

        print(f"\n[Rilevato]: {frase_udita}")

        # Con una sveglia o un timer che suona basta dire "stop" o "rimanda": niente wake word
        if SQUILLO["voce"]:
            intent = comandi.interpreta(frase_udita)
            if intent and intent["tipo"] in ("stop", "snooze"):
                risposta = esegui_intent(intent)
                if risposta:
                    parla(risposta)
                continue

        # Riposo: il risveglio vale sempre; in riposo manuale (sei fuori) si ascolta solo quello
        stato_riposo = RIPOSO.stato()
        if stato_riposo:
            if comandi.e_risveglio(frase_udita):
                risveglia()
                continue
            if stato_riposo == "manuale":
                continue

        if RE_JARVIS.search(frase_udita):
            if gestisci_attivazione(frase_udita):
                return


if __name__ == "__main__":
    main()