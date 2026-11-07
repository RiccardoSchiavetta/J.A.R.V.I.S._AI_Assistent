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
from flask import Flask, jsonify, Response
from gtts import gTTS

try:
    import config
    API_KEY = config.GROQ_API_KEY
except (ImportError, AttributeError):
    print("ERRORE: config.py non trovato o senza GROQ_API_KEY!")
    print("Crea un file config.py con la variabile GROQ_API_KEY = 'la_tua_chiave'")
    exit()

# Opzionali in config.py: se mancano, il calendario resta disattivato e il meteo usa i default
GIORNI_AVANTI = getattr(config, "GIORNI_AVANTI", 7)  # quanti giorni in avanti mostrare
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

# Timer e sveglie impostati a voce, e coda degli annunci da leggere
PROMEMORIA = []
LOCK_PROMEMORIA = threading.Lock()
ANNUNCI = queue.Queue()

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
    position: relative; z-index: 1; height: 100%;
    display: grid; grid-template-columns: 5fr 6fr; grid-template-rows: minmax(0, 1fr) auto;
    gap: 2.5vh 2.5vw; padding: 3vh 3vw;
}
#sx { grid-column: 1; grid-row: 1; display: flex; flex-direction: column; justify-content: space-between; gap: 2vh; min-width: 0; }
#dx { grid-column: 2; grid-row: 1; overflow: hidden; min-width: 0; display: flex; flex-direction: column; }
#eventi { flex: 1; min-height: 0; overflow: hidden; }
#barra { grid-column: 1 / span 2; grid-row: 2; }
.pannello { border: 1px solid var(--linea); border-radius: 12px; padding: 2vh 1.6vw; background: rgba(0,0,0,.6); }
.titolo { font-size: min(1.5vw, 2.6vh); letter-spacing: 4px; opacity: .65; margin-bottom: 1.4vh; display: flex; justify-content: space-between; }
.titolo .agg { color: var(--warn); letter-spacing: 1px; }

#clock { font-size: min(12vw, 30vh); font-weight: bold; line-height: 1; white-space: nowrap; text-shadow: 0 0 18px rgba(0,229,255,.7); }
#seconds { font-size: .2em; opacity: .75; margin-left: .3em; text-shadow: none; }
#date { font-size: min(2.2vw, 4vh); letter-spacing: 3px; opacity: .75; }

#meteo { display: flex; flex-wrap: wrap; align-items: baseline; gap: .6vh 1.6vw; }
#meteo .titolo { width: 100%; margin-bottom: .6vh; }
.m-temp { font-size: min(7vw, 13vh); font-weight: bold; line-height: 1; }
.m-desc { font-size: min(2.6vw, 4.6vh); color: #fff; text-transform: uppercase; }
.m-det { width: 100%; font-size: min(2vw, 3.5vh); opacity: .9; display: flex; flex-wrap: wrap; gap: .4vh 1.6vw; }
.warn { color: var(--warn); }
#timers { font-size: min(2.4vw, 4.4vh); color: var(--warn); }
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

/* Modalita' notte: solo l'orario, attenuato */
body.notte #dx, body.notte #barra, body.notte #reactor, body.notte #meteo, body.notte #date { display: none; }
body.notte #app { display: flex; align-items: center; justify-content: center; }
body.notte #sx { align-items: center; justify-content: center; }
body.notte #clock { opacity: .35; }

@media (orientation: portrait) {
    #app { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr) auto; }
    #sx, #dx, #barra { grid-column: 1; }
    #sx { grid-row: 1; } #dx { grid-row: 2; } #barra { grid-row: 3; }
    #clock { font-size: min(18vw, 14vh); }
}
</style>
</head>
<body onclick="toggleFull()">
<div id="reactor"><div class="anello a1"></div><div class="anello a2"></div></div>
<div id="app">
    <section id="sx">
        <div id="alto">
            <div id="clock"><span id="time">00:00</span><span id="seconds">00</span></div>
            <div id="date">CARICAMENTO...</div>
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
    <footer id="barra">
        <div id="status">OFFLINE</div>
        <div id="message">...</div>
    </footer>
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
function toggleFull() {
    if (!document.fullscreenElement) { document.documentElement.requestFullscreen().catch(e => console.log(e)); }
}
function pad(n) { return String(n).padStart(2, '0'); }
function minutiFa(iso) { return iso ? (Date.now() - new Date(iso).getTime()) / 60000 : Infinity; }

function aggiornaOrologio() {
    const now = new Date();
    $('time').textContent = pad(now.getHours()) + ':' + pad(now.getMinutes());
    $('seconds').textContent = pad(now.getSeconds());
    $('date').textContent = now.toLocaleDateString('it-IT', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }).toUpperCase();
    document.body.classList.toggle('notte', now.getHours() >= 23 || now.getHours() < 7);
    renderTimers();
}

function aggiornaStato() {
    fetch('/data').then(r => r.json()).then(data => {
        $('status').textContent = data.stato;
        $('message').textContent = data.testo;
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

function aggiornaDash() {
    fetch('/dash').then(r => r.json()).then(d => { DASH = d; renderMeteo(); renderEventi(); renderTimers(); }).catch(() => {});
}

function tra(ms) {
    const m = Math.round(ms / 60000);
    if (m < 1) return 'ora';
    if (m < 60) return 'tra ' + m + ' min';
    const h = Math.floor(m / 60), mm = m % 60;
    return 'tra ' + h + 'h' + (mm ? ' ' + pad(mm) + 'm' : '');
}
function etichettaGiorno(d) {
    const oggi = new Date(), dom = new Date();
    dom.setDate(oggi.getDate() + 1);
    if (d.toDateString() === oggi.toDateString()) return 'OGGI';
    if (d.toDateString() === dom.toDateString()) return 'DOMANI';
    return d.toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' }).toUpperCase();
}

function renderEventi() {
    const box = $('eventi');
    box.textContent = '';
    $('cal-agg').textContent = '';
    if (!DASH) return;
    if (DASH.cal_stato === 'non_configurato') { box.appendChild(el('div', 'vuoto', 'Calendario non configurato')); return; }
    if (DASH.cal_stato === 'caricamento') { box.appendChild(el('div', 'vuoto', 'Caricamento...')); return; }
    if (DASH.cal_stato === 'errore') {
        $('cal-agg').textContent = DASH.cal_ts ? 'NON AGGIORNATO DA ' + Math.round(minutiFa(DASH.cal_ts)) + ' MIN' : 'ERRORE';
    }
    const now = new Date();
    const evs = (DASH.eventi || []).filter(e => new Date(e.fine) > now).slice(0, 7);
    if (!evs.length) { box.appendChild(el('div', 'vuoto', 'Nessun impegno in programma')); return; }
    let ultimo = '';
    evs.forEach(e => {
        const ini = new Date(e.inizio), fin = new Date(e.fine);
        const g = etichettaGiorno(ini < now ? now : ini);
        if (g !== ultimo) { box.appendChild(el('div', 'giorno', g)); ultimo = g; }
        const incorso = ini <= now && now < fin;
        const presto = !incorso && (ini - now) < 30 * 60000;
        const riga = el('div', 'ev' + (incorso ? ' incorso' : presto ? ' presto' : ''));
        riga.appendChild(el('span', 'ev-ora' + (e.tutto_giorno ? ' tg' : ''), e.tutto_giorno ? 'GIORNATA' : pad(ini.getHours()) + ':' + pad(ini.getMinutes())));
        riga.appendChild(el('span', 'ev-tit', e.titolo));
        riga.appendChild(el('span', 'ev-tra', e.tutto_giorno ? '' : (incorso ? 'IN CORSO' : tra(ini - now))));
        box.appendChild(riga);
    });
    while (box.scrollHeight > box.clientHeight + 1 && box.lastChild) box.removeChild(box.lastChild);
    while (box.lastChild && box.lastChild.classList.contains('giorno')) box.removeChild(box.lastChild);
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
    (DASH.promemoria || []).forEach(p => {
        const rest = Math.round((new Date(p.quando).getTime() - now) / 1000);
        if (rest <= 0) return;
        let testo;
        if (p.tipo === 'sveglia') {
            const q = new Date(p.quando);
            testo = 'SVEGLIA ' + pad(q.getHours()) + ':' + pad(q.getMinutes());
        } else {
            testo = 'TIMER ' + pad(Math.floor(rest / 60)) + ':' + pad(rest % 60);
        }
        box.appendChild(el('div', '', testo));
    });
}

setInterval(aggiornaOrologio, 1000);
setInterval(aggiornaStato, 1000);
setInterval(aggiornaDash, 15000);
setInterval(renderEventi, 30000);
aggiornaOrologio(); aggiornaStato(); aggiornaDash();
</script>
</body>
</html>
"""


@app.route('/')
def index():
    return Response(HTML_HUD, mimetype='text/html')


@app.route('/data')
def get_data():
    return jsonify({'stato': HUD_STATO, 'testo': HUD_TESTO})


@app.route('/dash')
def get_dash():
    with LOCK_CACHE:
        eventi = list(CACHE["eventi"])
        out = {"cal_stato": CACHE["cal_stato"], "cal_ts": CACHE["cal_ts"],
               "meteo": CACHE["meteo"], "meteo_ts": CACHE["meteo_ts"]}
    out["eventi"] = [{"titolo": e["titolo"], "luogo": e["luogo"], "tutto_giorno": e["tutto_giorno"],
                      "inizio": e["inizio"].isoformat(), "fine": e["fine"].isoformat()} for e in eventi]
    with LOCK_PROMEMORIA:
        out["promemoria"] = [{"tipo": p["tipo"], "quando": p["quando"].isoformat()} for p in PROMEMORIA]
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
    r = requests.get(url, timeout=20)
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
                    key=lambda e: e["inizio"])[:20]
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


def thread_dati():
    while True:
        aggiorna_calendario()
        aggiorna_meteo()
        time.sleep(300)


def _giorno_relativo(dt):
    delta = (dt.date() - adesso().date()).days
    if delta <= 0:
        return "oggi"
    if delta == 1:
        return "domani"
    if delta == 2:
        return "dopodomani"
    return GIORNI_IT[dt.weekday()]


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
        for e in eventi[:8]:
            if e["fine"] <= ora:
                continue
            titolo = e["titolo"][:60]
            if e["tutto_giorno"]:
                voci.append(f"{_giorno_relativo(max(e['inizio'], ora))} tutto il giorno: {titolo}")
            else:
                voci.append(f"{_giorno_relativo(e['inizio'])} {e['inizio']:%H:%M}: {titolo}")
        nota = " (dati non aggiornati)" if stato == "errore" else ""
        righe.append(f"[CALENDARIO prossimi {GIORNI_AVANTI} giorni" + nota + ": " + ("; ".join(voci) if voci else "nessun impegno") + "]")
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
    return ora.hour >= 23 or ora.hour < 7


def imposta_timer(secondi):
    secondi = max(1, min(int(secondi), 24 * 3600))
    with LOCK_PROMEMORIA:
        PROMEMORIA.append({"tipo": "timer", "quando": adesso() + timedelta(seconds=secondi),
                           "testo": "Signore, il timer è scaduto."})


def imposta_sveglia(ore, minuti):
    ora = adesso()
    quando = ora.replace(hour=ore, minute=minuti, second=0, microsecond=0)
    if quando <= ora:
        quando += timedelta(days=1)
    with LOCK_PROMEMORIA:
        PROMEMORIA.append({"tipo": "sveglia", "quando": quando,
                           "testo": f"Signore, sono le {ore:02d}:{minuti:02d}. È l'ora della sveglia."})


def vibra(ms=500):
    try:
        subprocess.run(["termux-vibrate", "-d", str(ms)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass


def controlla_promemoria(annunciati):
    """Accoda gli annunci dovuti: timer/sveglie scaduti e eventi del calendario in arrivo."""
    ora = adesso()
    scaduti = []
    with LOCK_PROMEMORIA:
        for p in PROMEMORIA[:]:
            if p["quando"] <= ora:
                PROMEMORIA.remove(p)
                scaduti.append(p)
    for p in scaduti:
        ANNUNCI.put(p["testo"])
        vibra()

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
        time.sleep(20)


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


def ascolta_dinamico(nome_file="mic_monitor.wav"):
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

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(nome_file) as source:
            audio_data = recognizer.record(source)
            testo = recognizer.recognize_google(audio_data, language="it-IT")
            return testo.lower()
    except Exception:
        return ""


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


def spegni_sistemi():
    global HUD_STATO, HUD_TESTO
    HUD_STATO = "SPEGNIMENTO"
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
        print(".", end="", flush=True)
        try:
            frase_udita = ascolta_dinamico()
        except Exception:
            avvia_server_audio()
            continue

        if not frase_udita:
            continue

        print(f"\n[Rilevato]: {frase_udita}")

        if RE_JARVIS.search(frase_udita):
            if RE_SPEGNITI.search(frase_udita):
                spegni_sistemi()
                return

            HUD_STATO = "WAKE WORD RILEVATA"
            os.system("termux-vibrate -d 100 > /dev/null 2>&1")

            if len(frase_udita.split()) <= 2:
                parla("Sì Signore?")
                comando_vero = ascolta_dinamico()
                if comando_vero:
                    if RE_SPEGNITI.search(comando_vero):
                        spegni_sistemi()
                        return
                    HUD_TESTO = f"Comando: {comando_vero}"
                    risposta = chiedi_a_groq(comando_vero)
                    gestisci_risposta_e_comandi(risposta)
                else:
                    parla("Non ho udito alcun comando, Signore.")
            else:
                HUD_TESTO = f"Comando: {frase_udita}"
                risposta = chiedi_a_groq(frase_udita)
                gestisci_risposta_e_comandi(risposta)


if __name__ == "__main__":
    main()