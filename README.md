# J.A.R.V.I.S. (Termux Edition) 🤖

![Python](https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python&logoColor=white)
![Termux](https://img.shields.io/badge/Platform-Termux-green?style=for-the-badge&logo=android)
![Groq](https://img.shields.io/badge/AI-Groq%20(Llama%203)-orange?style=for-the-badge&logo=fastapi)
![Flask](https://img.shields.io/badge/Server-Flask-black?style=for-the-badge&logo=flask)

**Just A Rather Very Intelligent System**

Un assistente vocale AI avanzato progettato per trasformare vecchi tablet Android (testato su Huawei MediaPad T5) in Smart Display futuristici in stile Iron Man.
Il progetto gira interamente su Termux (ambiente Linux per Android) e utilizza la velocità estrema di **Groq** (con modello **Llama 3**) come cervello, garantendo risposte immediate e una personalità personalizzata.

---

## ✨ Caratteristiche Principali

* **🧠 Cervello AI:** Basato su **Groq (modello Llama 3.3 70B Versatile)** per un'elaborazione del linguaggio naturale incredibilmente veloce e intelligente.
* **🗣️ Voce:** Utilizza **gTTS (Google Text-to-Speech)** per una sintesi vocale italiana chiara e affidabile.
* **👂 Wake Word & VAD:** Riconoscimento vocale continuo ("Ciao Jarvis", "Computer", "Assistente") con rilevamento dinamico dell'attività vocale (VAD) tramite monitoraggio audio a basso livello (`parecord`) per ascoltare finché parli senza interromperti.
* **🖥️ Interfaccia HUD:** Server Web locale (Flask) che proietta un'interfaccia grafica animata (Orologio, Stato, Reattore Arc) visualizzabile a schermo intero come Web App (PWA).
* **🛠️ Ottimizzazione Hardware:** Bypassa le limitazioni audio di Android/EMUI utilizzando driver nativi Linux (`pulseaudio` e `parecord`) per un ascolto stabile in background.
* **🔋 Always On:** Progettato per girare 24/7 su tablet collegati all'alimentazione.

### 📱 Controllo App & Integrazione
Jarvis è in grado di interagire con il sistema operativo per avviare applicazioni specifiche tramite comandi vocali (es. *"Apri Spotify"*, *"Metti la sveglia"*).
Le app attualmente supportate di default sono:
* **Spotify**
* **Orologio / Sveglia**
* **Calendario**

> **Nota Tecnica:** Il sistema utilizza i "Package Name" (nomi pacchetto) Android per lanciare le app. I nomi preinseriti nel codice (es. `com.android.deskclock`) potrebbero variare in base al produttore del tuo dispositivo (Samsung, Huawei, Xiaomi, ecc.). È possibile verificarli e aggiornarli facilmente nel file `jarvis.py` utilizzando un'app come *Package Name Viewer*.

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
Scarica i file di questo progetto (o l'intera repository come ZIP) e metti il file `jarvis.py` nella cartella home di Termux.

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

## 🛠️ Tecnologie Usate

* Python 3.x
* Flask (Server Web Locale)
* **Groq Cloud API** (LLM Llama 3.3)
* **gTTS** (Google Text-to-Speech)
* PulseAudio & Parecord (Gestione Audio a basso livello)
* SpeechRecognition (Input Vocale)

---

> Progetto realizzato per ridare vita all'hardware datato senza dover comprare componenti esterni come un microcontrollore, un microfono e uno speaker.
