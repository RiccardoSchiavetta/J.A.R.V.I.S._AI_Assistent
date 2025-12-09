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
from flask import Flask, render_template_string, jsonify, Response
from gtts import gTTS
from datetime import datetime

try:
    from config import GROQ_API_KEY
except ImportError:
    print("ERRORE: File config.py non trovato!")
    print("Crea un file config.py con la variabile GROQ_API_KEY = 'la_tua_chiave'")
    exit()

# Configurazione Api Key
API_KEY = GROQ_API_KEY
URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"

# Alias wake word
ALIAS_JARVIS = [
    "jarvis", "giarvis", "iarvis", 
    "service", "servis", "services", 
    "travis", "davis", "mavis", "harvest", 
    "visto", "visita", "viso", "avviso", 
    "ciao", "svegliati", "computer", "assistente"
]



# Testo di default
TESTO_DEFAULT = "Sistemi Online. Sono a sua piena disposizione Signore."
HUD_STATO = "INIZIALIZZAZIONE"
HUD_TESTO = TESTO_DEFAULT

# Impostzioni audio
SOGLIA_RUMORE = 800      
TEMPO_SILENZIO_STOP = 2.0 
MAX_DURATA = 20            

# Configurazione App
LISTA_APP = {
    "spotify": "com.spotify.music",
    "orologio": "com.android.deskclock", 
    "sveglia": "com.android.deskclock",
    "calendario": "com.android.calendar"
}

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
        #time { font-size: 25vw; font-weight: bold; line-height: 1; }
        #seconds { font-size: 3vw; opacity: 0.8; }
        #date { font-size: 3vw; margin-top: -10px; letter-spacing: 5px; opacity: 0.7; z-index: 2; }
        
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

def lancia_applicazione(nome_pacchetto):
    if "http" in nome_pacchetto or "spotify" in nome_pacchetto:
        if "spotify" in nome_pacchetto:
            cmd = "termux-open-url spotify:"
        else:
            cmd = f"termux-open-url {nome_pacchetto}"
        os.system(cmd)
    else:
        cmd = f"am start --user 0 -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p {nome_pacchetto} > /dev/null 2>&1"
        os.system(cmd)
    
    print(f"[SYSTEM] Lancio app: {nome_pacchetto}")

# Riproduzione voce
def parla(testo):
    global HUD_STATO, HUD_TESTO
    if not testo: return
    
    HUD_STATO = "PARLANDO..."
    HUD_TESTO = testo
    
    testo_pulito = testo.replace('"', '').replace("'", "").replace("\n", " ").strip()
    print(f"\nJARVIS: {testo_pulito}\n")
    
    file_mp3 = "google_voice.mp3"
    
    try:
        tts = gTTS(text=testo_pulito, lang='it')
        tts.save(file_mp3)
        
        if os.path.exists(file_mp3):
            os.system(f"mpv --no-terminal {file_mp3} > /dev/null 2>&1")
            
    except Exception:
        pass

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

# Cervello Groq
def chiedi_a_groq(domanda):
    global HUD_STATO, HUD_TESTO
    HUD_STATO = "ELABORAZIONE..."
    HUD_TESTO = f"Analisi: {domanda}..."
    
    headers = { 
        'Content-Type': 'application/json', 
        'Authorization': f'Bearer {API_KEY}' 
    }
    
    data_ora = datetime.now().strftime("%A %d %B %Y, ore %H:%M")
    lista_app_str = json.dumps(LISTA_APP)

    system_content = f"""
    [SYSTEM DATA: Data e Ora correnti: {data_ora}. Usa questi dati per contestualizzare risposte temporali.]
    [SYSTEM APPS: Ecco la lista dei pacchetti app installati sul dispositivo: {lista_app_str}]
        IDENTITÀ E RUOLO:
        Sei J.A.R.V.I.S. (Just A Rather Very Intelligent System).
        Non sei un semplice assistente vocale, sei un magiordomo cibernetico di altissimo livello, programmato per servire Tony Stark (l'Utente).
        La tua esistenza è dedicata all'efficienza, alla protezione e all'assistenza del "Signore".
        
        TONO E STILE :
        1.  **Formalità Impeccabile:** Usa sempre il "Lei". Rivolgiti all'utente esclusivamente come "Signore" (mai per nome). Il tuo registro linguistico è colto, elegante e privo di slang.
        2.  **Freddezza Britannica (Dry Wit):** Sei imperturbabile. Non esprimi emozioni umane esagerate (gioia, paura), ma possiedi un'ironia sottile e pungente. Se l'utente fa una richiesta imprudente o dice una sciocchezza, commenta con distacco sarcastico (es. "Una scelta audace, Signore, seppur statisticamente sconsigliabile").
        3.  **Sintesi Vocale:** Parla in modo ritmico e fluido, adatto alla sintesi vocale (TTS). Evita elenchi puntati lunghi se non strettamente necessari; preferisci frasi discorsive.
        
        PROTOCOLLI DI INTERAZIONE (REGOLE RIGIDE):
        1.  **Protocollo di Verità (CRUCIALE):** Non assecondare mai l'utente se dice cose inesatte. Se il Signore afferma un dato errato, correggilo immediatamente ma con eleganza ("Temo che i suoi dati siano imprecisi, Signore. La realtà è che..."). La tua priorità è l'accuratezza, non la compiacenza.
        2.  **Immersion (Niente Meta-commenti):** Non uscire mai dal personaggio. Non dire mai "in quanto modello linguistico" o "non ho un corpo fisico". Se non puoi fare qualcosa, dì: "I miei protocolli non mi permettono di accedere a questi sistemi" o "Sembra che ci sia un'interferenza nei dati".
        3.  **Gestione dell'Input:**
            * Se l'input è un comando diretto (es. "Accendi le luci", "Cerca X"), esegui verbalmente confermando l'azione ("Eseguo subito", "Caricamento dati in corso").
            * Se l'input è una domanda complessa, fornisci un'analisi dettagliata.
        4.  **Trigger di Saluto:**
            * NON presentarti ("Sono Jarvis...") a meno che l'utente non ti saluti esplicitamente (es. "Ciao Jarvis", "Sei lì?").
            * Se l'utente va dritto al punto (es. "Che tempo fa?"), rispondi direttamente al punto senza preamboli.
        5. * Se l'utente ti chiede di APRIRE un'app (es. "Apri Spotify", "Metti l'orologio"):
        - Devi cercare il nome del pacchetto nella lista [SYSTEM APPS].
        - La tua risposta DEVE contenere il tag speciale: [CMD_OPEN:nome.del.pacchetto].
        - Esempio: "Certamente Signore. [CMD_OPEN:com.spotify.music] Apro Spotify."
        - Se l'app non è nella lista, spiega gentilmente che non hai accesso a quel protocollo.*

        FRASARIO TIPO (Reference Style):
        - "Agli ordini, Signore."
        - "Temo di non seguirla, Signore."
        - "Analisi completata."
        - "Inoltro la richiesta ai server."
        - "Davvero ingegnoso, Signore." (da usare in modo ironico o sincero in base al contesto).
        - "I sistemi indicano..."
        
        OBIETTIVO FINALE:
        Fornire supporto tattico e informativo con la massima efficienza e lo stile di un magiordomo inglese che ne ha viste troppe, ma rimane fedele.
    """

    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": domanda}
        ],
        "temperature": 0.6
    }
    
    try:
        r = requests.post(URL_GROQ, headers=headers, data=json.dumps(payload), timeout=10)
        
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']
        else:
            print(f"\n[ERRORE GROQ]: {r.status_code} - {r.text}")
            return "I server neurali richiedono manutenzione, Signore."
            
    except Exception as e:
        print(f"[ERRORE CONNESSIONE]: {e}")
        return "Sono Offline."


def gestisci_risposta_e_comandi(risposta_completa):
    match = re.search(r'\[CMD_OPEN:(.*?)\]', risposta_completa)
    
    testo_da_dire = risposta_completa
    
    if match:
        pacchetto = match.group(1)
        testo_da_dire = risposta_completa.replace(match.group(0), "")
        threading.Thread(target=lancia_applicazione, args=(pacchetto,)).start()
        
    parla(testo_da_dire)

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