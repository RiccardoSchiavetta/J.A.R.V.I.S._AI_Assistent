# J.A.R.V.I.S. (Termux Edition) 🤖

![Python](https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)
![Termux](https://img.shields.io/badge/Platform-Termux-green?style=for-the-badge&logo=android)
![Groq](https://img.shields.io/badge/AI-Groq%20(Compound%20Mini)-orange?style=for-the-badge&logo=fastapi)
![Flask](https://img.shields.io/badge/Server-Flask-black?style=for-the-badge&logo=flask)

**Just A Rather Very Intelligent System**

Un assistente vocale AI avanzato progettato per trasformare vecchi tablet Android (testato su Huawei MediaPad T5) in Smart Display futuristici in stile Iron Man.
Il progetto gira interamente su Termux (ambiente Linux per Android) e utilizza **Groq** con il modello **Compound Mini** (dotato di **ricerca web integrata**) come cervello, garantendo risposte immediate, aggiornate in tempo reale e una personalità personalizzata ispirata al maggiordomo cibernetico di Tony Stark.

---

## ✨ Caratteristiche Principali

* **🧠 Cervello AI:** Basato su **Groq (modello Compound Mini)** con **ricerca web integrata** per risposte aggiornate in tempo reale su meteo, notizie, sport, prezzi e altro. Include un sistema di **fallback automatico**: in caso di errore 413 (payload troppo grande), ritenta senza ricerca web per garantire sempre una risposta.
* **🗣️ Voce:** Utilizza **gTTS (Google Text-to-Speech)** per una sintesi vocale italiana chiara e affidabile, con riproduzione tramite **mpv**.
* **👂 Wake Word & VAD:** Riconoscimento vocale continuo con un ampio set di alias (tra cui *"Jarvis"*, *"Ciao"*, *"Computer"*, *"Assistente"*, *"Svegliati"* e molti altri, incluse variazioni fonetiche per migliorare il riconoscimento). Rilevamento dinamico dell'attività vocale (VAD) tramite monitoraggio audio a basso livello (`parecord`) con analisi RMS in tempo reale, per ascoltare finché parli senza interromperti.
* **📴 Spegnimento Vocale:** Comando di spegnimento vocale integrato. Frasi come *"Spegniti"*, *"Shutdown"*, *"Esci"*, *"Chiudi tutto"*, *"Termina"* o *"Addio"* terminano la sessione in modo pulito, sbloccando il wake-lock e aggiornando lo stato HUD.
* **📳 Feedback Tattile:** Vibrazione breve del dispositivo alla rilevazione della wake word, per conferma immediata.
* **🖥️ Interfaccia HUD:** Server Web locale (Flask) che proietta un'interfaccia grafica animata (Orologio, Stato, Reattore Arc) visualizzabile a schermo intero come Web App (PWA). Lo stato cambia colore dinamicamente in base all'attività: ciano (attesa), verde (ascolto), giallo (elaborazione), rosso (parlando).
* **🛠️ Ottimizzazione Hardware:** Bypassa le limitazioni audio di Android/EMUI utilizzando driver nativi Linux (`pulseaudio` e `parecord`) per un ascolto stabile in background.
* **🔋 Always On:** Progettato per girare 24/7 su tablet collegati all'alimentazione, con `termux-wake-lock` attivo.

### 📱 Controllo App & Integrazione
Jarvis è in grado di interagire con il sistema operativo per avviare applicazioni specifiche tramite comandi vocali (es. *"Apri Spotify"*, *"Metti la sveglia"*).
Le app attualmente supportate di default sono:
* **Spotify** (`com.spotify.music`)
* **Orologio / Sveglia** (`com.android.deskclock`)
* **Calendario** (`com.android.calendar`)

> **Nota Tecnica:** Il sistema utilizza i "Package Name" (nomi pacchetto) Android per lanciare le app. I nomi preinseriti nel codice potrebbero variare in base al produttore del tuo dispositivo (Samsung, Huawei, Xiaomi, ecc.). È possibile verificarli e aggiornarli facilmente nella variabile `LISTA_APP` nel file `jarvis.py` utilizzando un'app come *Package Name Viewer*. Il lancio delle app avviene in thread separati per non bloccare il flusso principale.

### 🤖 Personalità & System Prompt
Il modello AI è configurato con un system prompt dettagliato che definisce il comportamento di J.A.R.V.I.S.:
* Dà del **Lei** e chiama l'utente **"Signore"**
* Tono **colto, elegante, imperturbabile** con ironia britannica sottile
* Risposte **concise** (massimo 1-3 frasi) ottimizzate per la lettura vocale
* Output in **testo semplice** (niente markdown, asterischi o elenchi)
* Utilizza **sempre la ricerca web** per dati in tempo reale
* **Mai esce dal personaggio**: non si identifica come modello linguistico

---

## 📂 Struttura del Progetto

```
J.A.R.V.I.S._AI_Assistent/
├── jarvis.py      # Script principale con logica AI, audio, HUD e comandi
├── config.py      # Contiene la chiave API Groq (escluso dal repository)
├── .gitignore     # Esclude config.py e file temporanei
└── README.md      # Documentazione del progetto
```

---

## 🚀 Requisiti

* Dispositivo Android (Tablet o Smartphone).
* App Termux (scaricare da F-Droid).
* App Termux:API (scaricare da F-Droid).
* Connessione Internet.
* Una API Key gratuita di **Groq Cloud**.

---

## 📦 Installazione

**1. Aggiorna i repository e installa le dipendenze di sistema:**
Apri Termux e lancia:

    pkg update && pkg upgrade
    pkg install python pulseaudio sox ffmpeg mpv

**2. Scarica i file:**
Scarica i file di questo progetto (o clona la repository) e mettili nella cartella home di Termux.

    git clone https://github.com/TUO_UTENTE/J.A.R.V.I.S._AI_Assistent.git

**3. Installa le librerie Python:**

    pip install flask requests speechrecognition gTTS

**4. Configurazione:**
Crea un file chiamato `config.py` nella stessa cartella di `jarvis.py` e inserisci la tua API Key (non inclusa nel codice per sicurezza):

    GROQ_API_KEY = "gsk_LA_TUA_CHIAVE_GROQ_QUI"

**5. Avvio:**

    python jarvis.py

**6. Interfaccia Grafica:**
Apri Chrome sul dispositivo, vai su `http://localhost:5000` e aggiungi la pagina alla Schermata Home per averla a schermo intero senza barre.

---

## 🎙️ Comandi Vocali

| Tipo | Esempi | Azione |
|---|---|---|
| **Attivazione** | *"Jarvis"*, *"Ciao"*, *"Computer"*, *"Assistente"*, *"Svegliati"* | Attiva l'ascolto del comando |
| **Domande AI** | *"Jarvis, che tempo fa a Roma?"* | Elabora con Groq + ricerca web |
| **Apertura App** | *"Apri Spotify"*, *"Metti la sveglia"* | Lancia l'app Android corrispondente |
| **Spegnimento** | *"Jarvis spegniti"*, *"Shutdown"*, *"Esci"*, *"Addio"* | Termina la sessione e sblocca il dispositivo |

> **Nota:** Se dici solo la wake word (es. *"Jarvis"*), il sistema risponderà *"Sì Signore?"* e ascolterà il tuo comando successivo. Se includi il comando nella stessa frase (es. *"Jarvis che ore sono"*), verrà elaborato immediatamente.

---

## 🛠️ Tecnologie Usate

* Python 3.x
* Flask (Server Web Locale con PWA Manifest)
* **Groq Cloud API** (Compound Mini con Web Search)
* **gTTS** (Google Text-to-Speech)
* **mpv** (Riproduzione Audio)
* PulseAudio & Parecord (Gestione Audio a basso livello)
* SpeechRecognition (Input Vocale tramite Google Speech API)
* Termux:API (Wake Lock, Vibrazione, Apertura App)

---

> Progetto realizzato per ridare vita all'hardware datato senza dover comprare componenti esterni come un microcontrollore, un microfono e uno speaker.
