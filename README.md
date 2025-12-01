J.A.R.V.I.S. (Termux Edition) 🤖

Just A Rather Very Intelligent System

Un assistente vocale AI avanzato progettato per trasformare vecchi tablet Android (testato su Huawei MediaPad T5) in Smart Display futuristici in stile Iron Man.

Il progetto gira interamente su Termux (ambiente Linux per Android) e utilizza Google Gemini come cervello, garantendo risposte intelligenti e contestuali con una personalità personalizzata.


✨ Caratteristiche Principali

🧠 Cervello AI: Basato su Google Gemini 2.0 Flash per risposte rapide, intelligenti e sarcastici.

🗣️ Voce Neurale: Utilizza Microsoft Edge-TTS per una sintesi vocale italiana fluida e realistica (non robotica).

👂 Wake Word & VAD: Riconoscimento vocale continuo ("Ciao Jarvis") con rilevamento dinamico dell'attività vocale (VAD) per non tagliare le frasi a metà.

🖥️ Interfaccia HUD: Server Web locale (Flask) che proietta un'interfaccia grafica animata (Orologio, Stato, Reattore Arc) visualizzabile a schermo intero come Web App.

🛠️ Ottimizzazione Hardware: Bypassa le limitazioni audio di Android/EMUI utilizzando driver nativi Linux (pulseaudio e parecord) per un ascolto stabile in background.

🔋 Always On: Progettato per girare 24/7 su tablet collegati all'alimentazione.

🚀 Requisiti

Dispositivo Android (Tablet o Smartphone).

App Termux (da F-Droid).

App Termux:API (da F-Droid).

Connessione Internet.

Una API Key gratuita di Google Gemini.

📦 Installazione

Aggiorna i repository e installa le dipendenze di sistema:

pkg update && pkg upgrade
pkg install python pulseaudio sox ffmpeg


Clona la repository:

git clone [https://github.com/TUO_USERNAME/NOME_REPO.git](https://github.com/TUO_USERNAME/NOME_REPO.git)
cd NOME_REPO


Installa le librerie Python:

pip install flask requests speechrecognition gTTS edge-tts


Configurazione:
Crea un file config.py nella cartella principale e inserisci la tua chiave:

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

⚠️ Nota sulla Privacy

Questo progetto ascolta l'audio locale per rilevare la parola chiave "Jarvis". Le registrazioni vocali vengono inviate ai server di Google (Speech-to-Text) solo quando viene rilevata attività vocale. L'API Key di Gemini è personale e non deve essere condivisa.

Progetto realizzato per ridare vita all'hardware datato senza dover comprare componenti esterni come un microcontrrollore un microfono e uno speaker.
