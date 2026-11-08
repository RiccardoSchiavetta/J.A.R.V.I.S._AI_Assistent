# J.A.R.V.I.S. (Termux Edition) 🤖

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python&logoColor=white)
![Termux](https://img.shields.io/badge/Platform-Termux-green?style=for-the-badge&logo=android)
![Groq](https://img.shields.io/badge/AI-Groq%20Cloud-orange?style=for-the-badge&logo=fastapi)
![Flask](https://img.shields.io/badge/Server-Flask-black?style=for-the-badge&logo=flask)

**Just A Rather Very Intelligent System**

Un assistente vocale AI avanzato progettato per trasformare vecchi tablet Android (testato su Huawei MediaPad T5) in Smart Display futuristici in stile Iron Man.
Il progetto gira interamente su Termux (ambiente Linux per Android) e utilizza **Groq** come cervello (con **ricerca web integrata**), garantendo risposte immediate e aggiornate in tempo reale. In più mostra una dashboard con **calendario e meteo** e ha una personalità ispirata al maggiordomo cibernetico di Tony Stark.

---

## ✨ Caratteristiche Principali

* **🧠 Cervello AI:** Basato su **Groq Cloud**, con il modello configurabile da `config.py` (`GROQ_MODEL`) e **ricerca web integrata** per notizie, sport, prezzi e altro. Ha una **memoria breve**: ricorda gli ultimi 4 scambi (così funziona anche *"e domani?"*) e li dimentica dopo 3 minuti di inattività. Include un **fallback automatico**: in caso di errore 413 (richiesta troppo grande per il limite del piano gratuito) ritenta senza ricerca web e senza cronologia. Gli errori vengono spiegati a voce (limite di richieste raggiunto, chiave non valida, modello non più disponibile).
* **📅 Calendario:** Legge uno o più calendari in formato iCal (il tuo Google Calendar, quello della Formula 1, qualsiasi feed `.ics`), compresi gli eventi ricorrenti, e mostra i prossimi eventi dei prossimi giorni. Puoi chiedere a voce *"che impegni ho domani?"*.
* **🌦️ Meteo:** Dati locali da Open-Meteo (gratis, senza chiave): temperatura, minima/massima, probabilità di pioggia e vento nelle prossime 6 ore.
* **🔔 Annunci proattivi:** Jarvis ti avvisa a voce **15 minuti prima** di un evento del calendario e **all'inizio**. Gli annunci del calendario sono silenziosi dalle 23:00 alle 07:00.
* **⏱️ Timer e sveglie a voce:** *"Timer di 10 minuti"*, *"Sveglia alle 7:30"*. Sono gestiti da Jarvis stesso (voce + vibrazione), non dall'app Orologio.
* **🗣️ Voce:** Utilizza **gTTS (Google Text-to-Speech)** per una sintesi vocale italiana chiara e affidabile, con riproduzione tramite **mpv**.
* **👂 Wake Word & VAD:** Riconoscimento vocale continuo con alias fonetici (*"Jarvis"*, *"Computer"*, *"Assistente"*, *"Svegliati"* e varianti di pronuncia). Il confronto è a **parole intere**, per evitare attivazioni accidentali. Rilevamento dinamico dell'attività vocale (VAD) tramite monitoraggio audio a basso livello (`parecord`) con analisi RMS in tempo reale e **soglia adattiva**: si alza da sola se la stanza è rumorosa.
* **📴 Spegnimento Vocale:** Comando di spegnimento vocale integrato. Frasi come *"Spegniti"*, *"Shutdown"*, *"Esci"*, *"Chiudi tutto"*, *"Termina"* o *"Addio"* terminano la sessione in modo pulito, sbloccando il wake-lock e aggiornando lo stato HUD.
* **📳 Feedback Tattile:** Vibrazione breve del dispositivo alla rilevazione della wake word, per conferma immediata.
* **🖥️ Interfaccia HUD:** Server Web locale (Flask) che proietta un'interfaccia grafica animata con orologio, meteo, prossimi eventi, timer attivi e stato di Jarvis, visualizzabile a schermo intero come Web App (PWA). Lo stato cambia colore dinamicamente in base all'attività: ciano (attesa), verde (ascolto), giallo (elaborazione), rosso (parlando).
* **🔒 Sicurezza:** Il server web ascolta solo su `localhost`; le app possono essere lanciate solo se presenti nella lista `LISTA_APP` (il testo generato dal modello non viene mai eseguito come comando); chiavi e URL privati stanno solo in `config.py`.
* **🛠️ Ottimizzazione Hardware:** Bypassa le limitazioni audio di Android/EMUI utilizzando driver nativi Linux (`pulseaudio` e `parecord`) per un ascolto stabile in background.
* **🔋 Always On:** Progettato per girare 24/7 su tablet collegati all'alimentazione, con `termux-wake-lock` attivo.

### 📱 Controllo App & Integrazione
Jarvis è in grado di interagire con il sistema operativo per avviare applicazioni specifiche tramite comandi vocali (es. *"Apri Spotify"*).
Le app supportate di default sono:
* **Spotify** (`com.spotify.music`)
* **Orologio / Sveglia** (`com.android.deskclock`)
* **Calendario** (`com.android.calendar`)

> **Nota Tecnica:** Il sistema utilizza i "Package Name" (nomi pacchetto) Android per lanciare le app. I nomi preinseriti potrebbero variare in base al produttore del tuo dispositivo (Samsung, Huawei, Xiaomi, ecc.). La lista si personalizza dal file `config.py` (vedi la sezione [Configurazione](#%EF%B8%8F-configurazione-configpy)). Il lancio delle app avviene in thread separati per non bloccare il flusso principale.

### 📅 Calendario, Meteo e Annunci
* **Aggiornamento:** calendario e meteo si aggiornano in background ogni 5 minuti, senza mai bloccare l'interfaccia. Se un calendario non risponde, Jarvis tiene gli ultimi eventi noti e segnala che i dati non sono aggiornati.
* **Finestra temporale:** vengono mostrati gli eventi dei prossimi `GIORNI_AVANTI` giorni (di default 7).
* **Più calendari:** puoi usarne quanti vuoi (es. il tuo e la Formula 1): gli eventi vengono uniti e ordinati per data.
* **Domande a voce:** Jarvis conosce agenda e meteo locale e risponde senza fare ricerche sul web. Per il meteo di altre città usa invece la ricerca web.
* **Annunci:** a 15 minuti dall'inizio e all'inizio dell'evento (non per gli eventi "tutto il giorno" e non dalle 23:00 alle 07:00).
* **Timer e sveglie:** impostati a voce, compaiono anche sullo schermo. Sono gestiti da Jarvis: se riavvii lo script vengono persi e non sostituiscono una vera sveglia del mattino.

### 🤖 Personalità & System Prompt
Il modello AI è configurato con un system prompt dettagliato che definisce il comportamento di J.A.R.V.I.S.:
* Dà del **Lei** e chiama l'utente **"Signore"**
* Tono **colto, elegante, imperturbabile** con ironia britannica sottile
* Risposte **concise** (massimo 1-3 frasi) ottimizzate per la lettura vocale
* Output in **testo semplice** (niente markdown, asterischi o elenchi)
* Per agenda e meteo locale usa i dati forniti dal sistema; per notizie e dati in tempo reale usa la **ricerca web**
* **Mai esce dal personaggio**: non si identifica come modello linguistico

---

## 📂 Struttura del Progetto

```
J.A.R.V.I.S._AI_Assistent/
├── jarvis.py      # Script principale con logica AI, audio, HUD e comandi
├── config.py      # Chiavi e impostazioni personali (escluso dal repository)
├── .gitignore     # Esclude config.py, __pycache__ e file temporanei
└── README.md      # Documentazione del progetto
```

---

## 🚀 Requisiti

* Dispositivo Android (Tablet o Smartphone).
* App Termux (scaricare da F-Droid).
* App Termux:API (scaricare da F-Droid).
* Python 3.9 o superiore (incluso in Termux).
* Connessione Internet.
* Una API Key gratuita di **Groq Cloud**.
* *(Opzionale)* Un account Google Calendar o un feed iCal, per la dashboard degli eventi.

---

## 📦 Installazione

**1. Aggiorna i repository e installa le dipendenze di sistema:**
Apri Termux e lancia:

```bash
pkg update && pkg upgrade
pkg install python pulseaudio sox ffmpeg mpv termux-api git
```

**2. Scarica i file:**
Clona la repository nella cartella home di Termux.

```bash
git clone https://github.com/TUO_UTENTE/J.A.R.V.I.S._AI_Assistent.git
cd J.A.R.V.I.S._AI_Assistent
```

**3. Installa le librerie Python:**

```bash
python -m pip install flask requests speechrecognition gTTS icalendar recurring-ical-events tzdata
```

> Le ultime tre (`icalendar`, `recurring-ical-events`, `tzdata`) servono solo per il calendario. Si usa `python -m pip` e non `pip` per essere sicuri di installare i pacchetti per lo stesso Python che poi avvia lo script.

**4. Configurazione:**
Crea un file chiamato `config.py` nella stessa cartella di `jarvis.py`:

```bash
nano config.py
```

Il minimo indispensabile è la chiave Groq:

```python
GROQ_API_KEY = "gsk_LA_TUA_CHIAVE_GROQ_QUI"
```

Tutto il resto (calendario, meteo, app, modello) è opzionale: vedi la sezione [Configurazione](#%EF%B8%8F-configurazione-configpy).

**5. Avvio:**

```bash
python jarvis.py
```

**6. Interfaccia Grafica:**
Apri Chrome sul dispositivo, vai su `http://localhost:5000` e aggiungi la pagina alla Schermata Home per averla a schermo intero senza barre.

---

## ⚙️ Configurazione (`config.py`)

`config.py` contiene le tue impostazioni personali. **Non va mai caricato su GitHub** (è già escluso dal `.gitignore`). Dopo ogni modifica riavvia `python jarvis.py`.

| Opzione | Obbligatoria | Default | A cosa serve |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ Sì | — | La tua chiave API di Groq Cloud |
| `GROQ_MODEL` | No | `"openai/gpt-oss-120b"` | Il modello Groq usato come cervello |
| `ICAL_URLS` | No | nessuno (calendario disattivato) | Lista di feed iCal da mostrare |
| `ICAL_URL` | No | nessuno | Come `ICAL_URLS`, ma per un solo calendario (una stringa) |
| `GIORNI_AVANTI` | No | `7` | Quanti giorni in avanti mostrare gli eventi |
| `METEO_LAT`, `METEO_LON` | No | `41.686`, `12.778` (Velletri) | Coordinate per il meteo |
| `LISTA_APP` | No | Spotify, Orologio, Sveglia, Calendario | App che Jarvis può aprire a voce |

### Esempio completo

```python
GROQ_API_KEY = "gsk_LA_TUA_CHIAVE_GROQ_QUI"

# Modello Groq (opzionale)
GROQ_MODEL = "openai/gpt-oss-120b"

# Calendari (opzionale): uno o più feed iCal
ICAL_URLS = [
    "https://calendar.google.com/calendar/ical/.../basic.ics",   # il tuo Google Calendar
    "https://esempio.it/formula1.ics",                           # un calendario pubblico (es. Formula 1)
]
GIORNI_AVANTI = 7

# Meteo (opzionale): coordinate della tua città
METEO_LAT = 41.9028
METEO_LON = 12.4964

# App apribili a voce (opzionale): sostituisce la lista di default
LISTA_APP = {
    "amazon music": "com.amazon.mp3",
    "orologio": "com.android.deskclock",
    "calendario": "com.android.calendar",
}
```

### 📅 Come ottenere l'URL del tuo Google Calendar
1. Apri **Google Calendar dal browser** (da computer o in modalità desktop).
2. Nella barra laterale passa sopra il tuo calendario, premi **⋮** e scegli **Impostazioni e condivisione**.
3. Scorri fino a **Integra calendario** e copia l'**Indirizzo segreto in formato iCal**.
4. Incollalo in `config.py` come `ICAL_URL` (o dentro `ICAL_URLS`).

> ⚠️ L'indirizzo segreto dà accesso in lettura a tutto il tuo calendario a chiunque lo possieda: tienilo solo in `config.py`. Jarvis non lo scrive mai nei log.

### ➕ Come aggiungere altri calendari (es. Formula 1)
Aggiungi un altro indirizzo alla lista `ICAL_URLS`: gli eventi vengono uniti a quelli del tuo calendario e ordinati per data.
* Per i calendari **a cui sei iscritto** (come quello della F1) Google di solito non mostra l'indirizzo segreto: usa lo stesso link `.ics` con cui l'hai aggiunto.
* Funziona qualsiasi feed iCal pubblico (`.ics`). Se l'indirizzo inizia con `webcal://`, sostituisci `webcal://` con `https://`.
* Se un calendario non risponde, gli altri continuano a funzionare: il log mostra quale ha fallito (`calendario 2 errore: ...`).

### 🌦️ Come cambiare la città del meteo
Imposta `METEO_LAT` e `METEO_LON` con le coordinate della tua città. Le trovi tenendo premuto sulla mappa di Google Maps: le prime due cifre in alto sono latitudine e longitudine (es. Roma: `41.9028`, `12.4964`).

### 📱 Come cambiare le app apribili
`LISTA_APP` associa un nome pronunciabile al nome pacchetto Android dell'app. Puoi trovare i nomi pacchetto con un'app come *Package Name Viewer*.
* La lista in `config.py` **sostituisce** quella di default: inserisci tutte le app che vuoi poter aprire.
* Solo i pacchetti presenti nella lista possono essere lanciati.
* Esempio: per usare Amazon Music al posto di Spotify aggiungi `"amazon music": "com.amazon.mp3"`.

### 🧠 Come cambiare modello
Groq aggiorna spesso il proprio catalogo e ritira i modelli più vecchi. Per vedere i modelli disponibili con la tua chiave:

```bash
python - << 'EOF'
import config, requests
r = requests.get("https://api.groq.com/openai/v1/models",
                 headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"})
print("\n".join(m["id"] for m in r.json()["data"]))
EOF
```

Poi scrivi il nome scelto in `GROQ_MODEL`. Per la ricerca web integrata serve un modello che la supporti.

### 🔐 Sicurezza della chiave
* `config.py` e le cartelle `__pycache__/` (che contengono una copia compilata di `config.py`, chiave inclusa) devono restare nel `.gitignore` e **non devono mai essere committati**.
* Se per errore hai pubblicato una chiave, non basta cancellare il file dal repository: la chiave resta nella cronologia di git. Generane una nuova dalla console di Groq, elimina la vecchia e aggiorna `config.py`.

---

## 🔄 Aggiornare il progetto

```bash
cd J.A.R.V.I.S._AI_Assistent
git pull
```

Tieni le tue personalizzazioni **solo in `config.py`** (app, calendari, città, modello): è un file non versionato, quindi `git pull` non va mai in conflitto. Se modifichi direttamente `jarvis.py` sulla tablet, il prossimo `git pull` potrebbe rifiutarsi di sovrascriverlo.

---

## 🎙️ Comandi Vocali

| Tipo | Esempi | Azione |
|---|---|---|
| **Attivazione** | *"Jarvis"*, *"Computer"*, *"Assistente"*, *"Svegliati"* | Attiva l'ascolto del comando |
| **Domande AI** | *"Jarvis, chi ha vinto ieri la partita?"* | Elabora con Groq + ricerca web |
| **Agenda** | *"Jarvis, che impegni ho domani?"* | Risponde dai tuoi calendari |
| **Meteo** | *"Jarvis, che tempo fa oggi?"* | Usa il meteo locale (per altre città, ricerca web) |
| **Timer** | *"Jarvis, timer di 10 minuti"* | Imposta un timer, annunciato a voce con vibrazione |
| **Sveglia** | *"Jarvis, sveglia alle 7:30"* | Imposta una sveglia gestita da Jarvis |
| **Apertura App** | *"Apri Spotify"* | Lancia l'app Android corrispondente (se in `LISTA_APP`) |
| **Spegnimento** | *"Jarvis spegniti"*, *"Shutdown"*, *"Esci"*, *"Addio"* | Termina la sessione e sblocca il dispositivo |

> **Nota:** Se dici solo la wake word (es. *"Jarvis"*), il sistema risponderà *"Sì Signore?"* e ascolterà il tuo comando successivo. Se includi il comando nella stessa frase (es. *"Jarvis che ore sono"*), verrà elaborato immediatamente.

---

## 🩺 Risoluzione problemi

| Sintomo | Causa probabile | Soluzione |
|---|---|---|
| `ModuleNotFoundError: No module named 'requests'` (o `flask`, `gtts`...) | Dopo un `pkg upgrade` Python può cambiare versione e i pacchetti pip installati si perdono | Rilancia il comando di installazione del passo 3 |
| `Address already in use` all'avvio, oppure l'interfaccia non cambia dopo un aggiornamento | È ancora attiva una vecchia istanza di Jarvis sulla porta 5000, oppure la pagina nel browser è quella vecchia | `pkill -f jarvis.py`, poi riavvia; ricarica la pagina (se è una PWA chiudila dai recenti e riaprila) |
| Jarvis dice *"Il modello configurato non è più disponibile"* (nel terminale: `404 model_not_found`) | Groq ha ritirato il modello | Scegli un modello disponibile e impostalo in `GROQ_MODEL` (vedi sopra) |
| Jarvis dice *"Ho raggiunto il limite di richieste"* | Limiti del piano gratuito di Groq (richieste e token al minuto) | Aspetta un minuto e riprova |
| Jarvis dice *"La mia chiave di accesso non risulta valida"* | `GROQ_API_KEY` errata, scaduta o revocata | Genera una nuova chiave e aggiorna `config.py` |
| Il pannello eventi dice *"Calendario non configurato"* | Manca `ICAL_URL`/`ICAL_URLS` in `config.py` | Aggiungilo seguendo la sezione Configurazione |
| Nel terminale compare `[CALENDARIO] errore: ...` | URL errato, calendario non raggiungibile o librerie mancanti | Controlla l'URL; se l'errore è `ModuleNotFoundError`, installa `icalendar`, `recurring-ical-events` e `tzdata` |
| `git pull` rifiuta di aggiornare per modifiche locali | Hai modificato `jarvis.py` (o ci sono file `.pyc` versionati) sulla tablet | Sposta le tue impostazioni in `config.py`; poi `cp jarvis.py ~/jarvis_backup.py` e `git restore jarvis.py` prima del `git pull`. Per i `.pyc`: `git rm -r --cached __pycache__` una volta sul PC, poi commit e push |
| `./jarvis.py: Permission denied` | Lo script non è eseguibile | Si avvia sempre con `python jarvis.py` |

---

## 🛠️ Tecnologie Usate

* Python 3.9+
* Flask (Server Web Locale con PWA Manifest)
* **Groq Cloud API** (modello configurabile, con ricerca web integrata)
* **Open-Meteo** (meteo, senza chiave)
* **iCalendar** + **recurring-ical-events** (lettura di calendari iCal ed eventi ricorrenti)
* **gTTS** (Google Text-to-Speech)
* **mpv** (Riproduzione Audio)
* PulseAudio & Parecord (Gestione Audio a basso livello)
* SpeechRecognition (Input Vocale tramite Google Speech API)
* Termux:API (Wake Lock, Vibrazione, Apertura App)

---

## ℹ️ Note

* **Privacy:** per riconoscere la wake word, ogni frase captata dal microfono viene trascritta tramite la Google Speech API, anche se non è rivolta a Jarvis. Tienine conto nel scegliere dove posizionare il dispositivo.
* **Limiti del piano gratuito:** Groq limita richieste e token al minuto. Con la ricerca web una singola richiesta può essere grande: in quel caso Jarvis risponde comunque, ma senza ricerca.
* **Accesso alla dashboard:** il server web ascolta solo su `localhost` (il browser deve girare sullo stesso dispositivo). Per aprirlo da un altro dispositivo in rete locale, in `run_web_server()` cambia `host='127.0.0.1'` in `host='0.0.0.0'`, sapendo che così chiunque sulla tua rete potrà vederlo.

---

> Progetto realizzato per ridare vita all'hardware datato senza dover comprare componenti esterni come un microcontrollore, un microfono e uno speaker.