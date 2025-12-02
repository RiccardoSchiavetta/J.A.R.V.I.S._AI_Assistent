J.A.R.V.I.S. (Termux Edition) 🤖

Just A Rather Very Intelligent System

Un assistente vocale AI avanzato progettato per trasformare vecchi tablet Android (testato su Huawei MediaPad T5) in Smart Display futuristici in stile Iron Man.

Il progetto gira interamente su Termux (ambiente Linux per Android) e utilizza Google Gemini come cervello, garantendo risposte intelligenti e contestuali con una personalità personalizzata.

✨ Caratteristiche Principali

🧠 Cervello AI: Basato su Google Gemini 2.0 Flash per risposte rapide, intelligenti e con personalità.

🗣️ Voce Neurale: Utilizza Microsoft Edge-TTS per una sintesi vocale italiana fluida e realistica.

👂 Wake Word & VAD: Riconoscimento vocale continuo ("Ciao Jarvis") con rilevamento dinamico dell'attività vocale (VAD) per ascoltare finché parli senza interromperti.

🖥️ Interfaccia HUD: Server Web locale (Flask) che proietta un'interfaccia grafica animata (Orologio, Stato, Reattore Arc) visualizzabile a schermo intero come Web App (PWA).

🛠️ Ottimizzazione Hardware: Bypassa le limitazioni audio di Android/EMUI utilizzando driver nativi Linux (pulseaudio e parecord) per un ascolto stabile in background.

🔋 Always On: Progettato per girare 24/7 su tablet collegati all'alimentazione.

🚀 Requisiti

Dispositivo Android (Tablet o Smartphone).

App Termux (scaricare da F-Droid).

App Termux:API (scaricare da F-Droid)..

Connessione Internet.

Una API Key gratuita di Google Gemini.

📦 Installazione

Aggiorna i repository e installa le dipendenze di sistema:
Apri Termux e lancia:

pkg update && pkg upgrade
pkg install python pulseaudio sox ffmpeg


Scarica i file:
Scarica i file di questo progetto (o l'intera repository come ZIP) e metti il file jarvis.py nella cartella home di Termux.

Installa le librerie Python:

pip install flask requests speechrecognition gTTS edge-tts


Configurazione:
Crea un file chiamato config.py nella stessa cartella di jarvis.py e inserisci la tua API Key (non inclusa nel codice per sicurezza):

GEMINI_API_KEY = "LA_TUA_CHIAVE_GOOGLE_AI_STUDIO"


Avvio:

python jarvis.py


Interfaccia Grafica:
Apri Chrome sul dispositivo, vai su http://localhost:5000 e aggiungi la pagina alla Schermata Home per averla a schermo intero senza barre.

🛠️ Tecnologie Usate

Python 3.x

Flask (Server Web Locale)

Google Generative AI (Gemini)

PulseAudio & Parecord (Gestione Audio a basso livello)

SpeechRecognition (Input Vocale)

Edge-TTS (Output Vocale Neurale)

Progetto realizzato per ridare vita all'hardware datato senza dover comprare componenti esterni come un microcontrrollore un microfono e uno speaker.
