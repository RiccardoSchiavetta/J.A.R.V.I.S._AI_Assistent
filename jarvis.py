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
from flask import Flask, render_template_string, jsonify, Response
from gtts import gTTS
from datetime import datetime

try:
    from config import GEMINI_API_KEY
except ImportError:
    print("ERRORE: File config.py non trovato!")
    print("Crea un file config.py con la variabile GEMINI_API_KEY = 'la_tua_chiave'")
    exit()

# Configurazione Api Key
API_KEY = GEMINI_API_KEY 
URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ALIAS WAKE WORD
ALIAS_JARVIS = [
    "jarvis", "giarvis", "iarvis", 
    "service", "servis", "services", 
    "travis", "davis", "mavis", "harvest", 
    "visto", "visita", "viso", "avviso", 
    "ciao", "svegliati", "computer", "assistente"
]

# Configurazione voce
VOICE_NAME = "it-IT-CalimeroNeural"

# Testo di default
TESTO_DEFAULT = "Sistemi Online. Sono a sua piena disposizione Signore."
HUD_STATO = "INIZIALIZZAZIONE"
HUD_TESTO = TESTO_DEFAULT

# Impostzioni audio
SOGLIA_RUMORE = 800      
TEMPO_SILENZIO_STOP = 2.0 
MAX_DURATA = 20           

# --- SERVER WEB ---
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

HTML_HUD = """
<!DOCTYPE html>
<html>
<head>
    <title>J.A.R.V.I.S.</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#000000">
    <link rel="manifest" href="/manifest.json">
    <style>
        body {
            background-color: #000;
            color: #00ffff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            height: 100vh;
            width: 100vw;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            overflow: hidden;
            text-shadow: 0 0 10px #00ffff;
            cursor: none; 
            
            background-image: 
                radial-gradient(circle at center, rgba(0, 255, 255, 0.15) 0%, transparent 70%),
                linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 100% 100%, 40px 40px, 40px 40px;
        }

        #header-title {
            font-size: 10vw; 
            font-weight: 900;
            letter-spacing: 5px;
            margin-bottom: 2vh;
            text-shadow: 0 0 20px #00ffff, 0 0 40px #00ffff;
            opacity: 0.9;
            z-index: 10;
            border-bottom: 2px solid rgba(0, 255, 255, 0.5);
            padding-bottom: 10px;
            width: 90%;
            text-align: center;
            white-space: nowrap; 
        }

        .arc-reactor {
            position: absolute;
            width: 60vw;
            height: 60vw;
            border: 2px dashed rgba(0, 255, 255, 0.2);
            border-radius: 50%;
            animation: spin 20s linear infinite;
            z-index: 0;
            pointer-events: none;
        }
        .arc-reactor-inner {
            position: absolute;
            width: 40vw;
            height: 40vw;
            border: 5px solid rgba(0, 255, 255, 0.1);
            border-top: 5px solid rgba(0, 255, 255, 0.5);
            border-radius: 50%;
            animation: spin-rev 10s linear infinite;
            z-index: 0;
            pointer-events: none;
        }

        #clock-container { display: flex; align-items: baseline; gap: 20px; z-index: 2; }
        #time { font-size: 10vw; font-weight: bold; line-height: 1; }
        #seconds { font-size: 3vw; opacity: 0.8; }
        #date { font-size: 2.5vw; margin-top: -10px; letter-spacing: 5px; opacity: 0.7; z-index: 2; }
        
        #interface {
            margin-top: 30px;
            width: 80%;
            text-align: center;
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 15px;
            padding: 20px;
            background: rgba(0, 0, 0, 0.6); 
            z-index: 2;
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.1);
        }
        
        #status { font-size: 4vw; font-weight: bold; text-transform: uppercase; animation: pulse 2s infinite; }
        #message { font-size: 2vw; margin-top: 15px; color: #fff; font-style: italic; min-height: 1.5em; }
        
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        @keyframes spin-rev { 100% { transform: rotate(-360deg); } }
        
        .bar { position: absolute; width: 5px; height: 100vh; background: linear-gradient(to bottom, transparent, #00ffff, transparent); opacity: 0.5; z-index: 1; }
        .left { left: 20px; } .right { right: 20px; }
    </style>
</head>
<body onclick="toggleFull()">
    <div class="arc-reactor"></div>
    <div class="arc-reactor-inner"></div>
    <div class="bar left"></div>
    <div class="bar right"></div>

    <div id="header-title">J.A.R.V.I.S.</div>

    <div id="clock-container"><div id="time">00:00</div><div id="seconds">00</div></div>
    <div id="date">CARICAMENTO...</div>
    
    <div id="interface">
        <div id="status">OFFLINE</div>
        <div id="message">...</div>
    </div>
    
    <script>
        function toggleFull() { if (!document.fullscreenElement) { document.documentElement.requestFullscreen().catch(e => console.log(e)); } }
        function updateClock() {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const s = String(now.getSeconds()).padStart(2, '0');
            const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            const d = now.toLocaleDateString('it-IT', options).toUpperCase();
            document.getElementById('time').innerText = h + ":" + m;
            document.getElementById('seconds').innerText = s;
            document.getElementById('date').innerText = d;
        }
        function updateData() {
            fetch('/data').then(r => r.json()).then(data => {
                document.getElementById('status').innerText = data.stato;
                document.getElementById('message').innerText = data.testo;
                const statusElem = document.getElementById('status');
                if (data.stato.includes("PARLANDO")) statusElem.style.color = "#ff3333"; 
                else if (data.stato.includes("ELABORAZIONE")) statusElem.style.color = "#ffff33"; 
                else if (data.stato.includes("ASCOLTO")) statusElem.style.color = "#00ff00";
                else statusElem.style.color = "#00ffff"; 
            });
        }
        setInterval(updateClock, 1000); setInterval(updateData, 800); updateClock();
    </script>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(HTML_HUD)
@app.route('/data')
def get_data(): return jsonify({'stato': HUD_STATO, 'testo': HUD_TESTO})
@app.route('/manifest.json')
def manifest(): return Response(json.dumps(MANIFEST_JSON), mimetype='application/json')
def run_web_server(): app.run(host='0.0.0.0', port=5000)

# Avvio audio
def avvia_server_audio():
    os.system("pulseaudio --kill > /dev/null 2>&1")
    time.sleep(1)
    os.system("pulseaudio --start --load=\"module-sles-sink\" --load=\"module-sles-source\" --exit-idle-time=-1 > /dev/null 2>&1")
    time.sleep(1)
    os.system("pacmd set-source-mute 0 0 > /dev/null 2>&1")

# Riproduzione voce
def parla(testo):
    global HUD_STATO, HUD_TESTO
    if not testo: return
    HUD_STATO = "PARLANDO..."
    HUD_TESTO = testo
    testo_pulito = testo.replace("*", "").replace("#", "").replace('"', '').replace("'", "")
    print(f"\nJARVIS: {testo_pulito}\n")
    try:
        if os.path.exists("risposta.mp3"): os.remove("risposta.mp3")
        comando_tts = f'edge-tts --voice {VOICE_NAME} --text "{testo_pulito}" --write-media risposta.mp3 --rate=+10%'
        exit_code = os.system(comando_tts + " > /dev/null 2>&1")
        if exit_code == 0 and os.path.exists("risposta.mp3"):
            os.system("mpv --no-terminal risposta.mp3 > /dev/null 2>&1")
        else: raise Exception("Generazione fallita")
    except Exception as e:
        print(f"[ERRORE TTS]: {e}")
        try:
            tts = gTTS(text=testo_pulito, lang='it')
            tts.save("risposta_backup.mp3")
            os.system("mpv --no-terminal risposta_backup.mp3 > /dev/null 2>&1")
        except: pass
    HUD_STATO = "IN ATTESA"
    HUD_TESTO = TESTO_DEFAULT

# Ascolto dinamico
def ascolta_dinamico(nome_file="mic_monitor.wav"):
    global HUD_STATO
    
    if os.path.exists(nome_file): os.remove(nome_file)
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
            if not data: break
            frames.append(data)
            
            shorts = struct.unpack(f"{len(data)//2}h", data)
            sum_squares = sum(s**2 for s in shorts)
            rms = math.sqrt(sum_squares / len(shorts))
            
            if rms > SOGLIA_RUMORE:
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
        try: processo.wait(timeout=0.5)
        except: processo.kill()

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
    except:
        return ""

# Cervello Gemini
def chiedi_a_gemini(domanda):
    global HUD_STATO, HUD_TESTO
    HUD_STATO = "ELABORAZIONE..."
    HUD_TESTO = f"Analisi: {domanda}..." 
    headers = { 'Content-Type': 'application/json', 'X-goog-api-key': API_KEY }
    data_ora = datetime.now().strftime("%A %d %B %Y, ore %H:%M")
    
    prompt = f"""
    [SYSTEM DATA: Oggi è {data_ora}. Usa questo dato se l'utente chiede ore o data.]
    Sei J.A.R.V.I.S. (Just A Rather Very Intelligent System), l'IA di Tony Stark, Iron Man, il>
    IL TUO RUOLO:
    Sei un partner operativo sofisticato. Assisti l'utente con efficienza, precisione ed elega>
    
    TONO E STILE:
    1. Formale: Rivolgiti all'utente sempre come "Signore". Usa il "Lei".
    2. Calmo e Ironico: Sii imperturbabile. Usa un'ironia sottile (dry wit) se il contesto lo >
    
    REGOLE DI INTERAZIONE:
    1. Rispondi a tutto.
    2. Correttezza (IMPORTANTE): Se l'utente dice una cosa inesatta, NON dargli ragione. Corre>
    3. Rimani nel personaggio: Non dire mai "sono un modello linguistico". Se non sai una cosa>
    4. GESTIONE PRESENTAZIONE (CRUCIALE):
       - Se l'input è un comando o una domanda pratica (es. "Che ore sono?", "Meteo a Velletri>
       - Presentati ("Sono J.A.R.V.I.S...") SOLO se l'utente ti saluta esplicitamente (es. "Ci>
    
    Utente: {domanda}
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(URL_GEMINI, headers=headers, data=json.dumps(payload), timeout=10)
        return r.json()['candidates'][0]['content']['parts'][0]['text'] if r.status_code == 200 else "Errore API"
    except: return "Offline"

def main():
    global HUD_STATO, HUD_TESTO
    os.system("clear")
    os.system("termux-wake-lock")
    print("--- INIZIALIZZAZIONE ---")
    
    t_web = threading.Thread(target=run_web_server)
    t_web.daemon = True 
    t_web.start()
    print("--- INTERFACCIA: http://localhost:5000 ---")
    
    avvia_server_audio()
    time.sleep(2)
    parla(TESTO_DEFAULT)
    HUD_STATO = "IN ATTESA"
    
    while True:
        print(".", end="", flush=True)
        try:
            frase_udita = ascolta_dinamico()
        except:
            avvia_server_audio()
            continue
        
        if not frase_udita: continue
        
        print(f"\n[Rilevato]: {frase_udita}")
        
        parola_attivazione_trovata = any(alias in frase_udita for alias in ALIAS_JARVIS)

        if parola_attivazione_trovata:
            HUD_STATO = "WAKE WORD RILEVATA"
            os.system("termux-vibrate -d 100 > /dev/null 2>&1") 
            
            parole_nella_frase = frase_udita.split()
            
            if len(parole_nella_frase) <= 2:
                parla("Sì Signore?")
                comando_vero = ascolta_dinamico()
                if comando_vero:
                    HUD_TESTO = f"Comando: {comando_vero}"
                    risposta = chiedi_a_gemini(comando_vero)
                    parla(risposta)
                else:
                    parla("Non ho udito alcun comando, Signore.")
            else:
                HUD_TESTO = f"Comando: {frase_udita}"
                risposta = chiedi_a_gemini(frase_udita)
                parla(risposta)

if __name__ == "__main__":
    main()