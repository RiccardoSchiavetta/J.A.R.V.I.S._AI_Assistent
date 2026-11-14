# J.A.R.V.I.S. (Termux Edition) 🤖

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python&logoColor=white)
![Termux](https://img.shields.io/badge/Platform-Termux-green?style=for-the-badge&logo=android)
![Groq](https://img.shields.io/badge/AI-Groq%20Cloud-orange?style=for-the-badge&logo=fastapi)
![Flask](https://img.shields.io/badge/Server-Flask-black?style=for-the-badge&logo=flask)

**Just A Rather Very Intelligent System**

Un assistente vocale AI avanzato progettato per trasformare vecchi tablet Android (testato su Huawei MediaPad T5) in Smart Display futuristici in stile Iron Man.
Il progetto gira interamente su Termux (ambiente Linux per Android) e utilizza **Groq** come cervello (con **ricerca web integrata**) per le domande libere. I comandi di tutti i giorni (timer, sveglie, musica, volume, ora) vengono invece riconosciuti **in locale**, quindi rispondono subito. In più mostra una dashboard con **calendario e meteo** e ha una personalità ispirata al maggiordomo cibernetico di Tony Stark.

---

## ✨ Caratteristiche Principali

* **🧠 Cervello AI:** Basato su **Groq Cloud**, con il modello configurabile da `config.py` (`GROQ_MODEL`) e **ricerca web integrata** per notizie, sport, prezzi e altro. Ha una **memoria breve**: ricorda gli ultimi 4 scambi (così funziona anche *"e domani?"*) e li dimentica dopo 3 minuti di inattività. Include un **fallback automatico**: in caso di errore 413 (richiesta troppo grande per il limite del piano gratuito) ritenta senza ricerca web e senza cronologia. Gli errori vengono spiegati a voce (limite di richieste raggiunto, chiave non valida, modello non più disponibile).
* **⚡ Comandi locali istantanei:** Timer, sveglie, musica, volume, *"che ore sono"* e apertura app vengono capiti direttamente da Jarvis, senza passare dal modello: niente attese né consumo del piano gratuito. Tutto il resto va al modello.
* **⏰ Timer e sveglie "stile Alexa":** più timer insieme anche con un nome (*"timer per la pasta di 10 minuti"*), *"quanto manca?"*, sveglie una tantum o ricorrenti (*"dal lunedì al venerdì"*), sveglia con la radio, **rimanda (snooze)** e **stop** anche senza dire la wake word. Sono salvati su file: **sopravvivono ai riavvii**.
* **🎵 Musica a comando vocale:** radio in streaming, ricerca su YouTube, musica salvata sulla tablet, e controllo di pausa, prossima, precedente, volume e *"cosa sta suonando?"*. Mentre Jarvis ti ascolta la musica si abbassa da sola.
* **📅 Calendario:** Legge uno o più calendari in formato iCal (il tuo Google Calendar, quello della Formula 1, qualsiasi feed `.ics`), compresi gli eventi ricorrenti, e mostra i prossimi eventi in ordine cronologico, fino a riempire lo spazio disponibile. Si aggiorna da solo ogni minuto: un evento nuovo compare senza riavviare nulla. Puoi chiedere a voce *"che impegni ho domani?"*.
* **🌦️ Meteo:** Dati locali da Open-Meteo (gratis, senza chiave): temperatura, minima/massima, probabilità di pioggia e vento nelle prossime 6 ore.
* **🔔 Annunci proattivi:** Jarvis ti avvisa a voce **15 minuti prima** di un evento del calendario e **all'inizio**. Gli annunci del calendario sono silenziosi in modalità riposo (di notte o quando sei fuori).
* **🗣️ Voce:** Utilizza **gTTS (Google Text-to-Speech)** per una sintesi vocale italiana chiara e affidabile, con riproduzione tramite **mpv**.
* **👂 Wake Word & VAD:** Riconoscimento vocale continuo con alias fonetici (*"Jarvis"*, *"Computer"*, *"Assistente"*, *"Svegliati"* e varianti di pronuncia). Il confronto è a **parole intere**, per evitare attivazioni accidentali. Rilevamento dinamico dell'attività vocale (VAD) tramite monitoraggio audio a basso livello (`parecord`) con analisi RMS in tempo reale e **soglia adattiva**: si alza da sola se la stanza è rumorosa.
* **🌙 Modalità riposo:** schermo scuro con solo l'orologio. Si attiva da sola di notte (dalle 00:00 alle 08:00), oppure a voce quando esci (*"Jarvis, sto uscendo"*). Per risvegliarlo basta dire *"Wake up, daddy's home"* (o *"svegliati, papà è a casa"*, *"sono a casa"*), senza spegnere e riaccendere nulla.
* **👆 Tocca per parlare:** toccando la barra di stato in basso, Jarvis ascolta subito il comando senza wake word. È il modo più affidabile quando la musica è alta.
* **📴 Spegnimento Vocale:** Comando di spegnimento vocale integrato. Frasi come *"Spegniti"*, *"Shutdown"*, *"Esci"*, *"Chiudi tutto"*, *"Termina"* o *"Addio"* terminano la sessione in modo pulito, sbloccando il wake-lock e aggiornando lo stato HUD.
* **📳 Feedback Tattile:** Vibrazione breve del dispositivo alla rilevazione della wake word, per conferma immediata.
* **🖥️ Interfaccia HUD:** Server Web locale (Flask) che proietta un'interfaccia grafica animata con orologio, meteo, prossimi eventi, timer e sveglie attivi, musica in riproduzione e stato di Jarvis, visualizzabile a schermo intero come Web App (PWA). Quando suona una sveglia o un timer compare un avviso con i pulsanti **FERMA** e **RIMANDA**. Lo stato cambia colore dinamicamente in base all'attività: ciano (attesa), verde (ascolto), giallo (elaborazione), rosso (parlando).
* **🔒 Sicurezza:** Il server web ascolta solo su `localhost`; le app possono essere lanciate solo se presenti nella lista `LISTA_APP` (il testo generato dal modello non viene mai eseguito come comando); chiavi e URL privati stanno solo in `config.py`.
* **🛠️ Ottimizzazione Hardware:** Bypassa le limitazioni audio di Android/EMUI utilizzando driver nativi Linux (`pulseaudio` e `parecord`) per un ascolto stabile in background.
* **🔋 Always On:** Progettato per girare 24/7 su tablet collegati all'alimentazione, con `termux-wake-lock` attivo.

### 📱 Controllo App & Integrazione
Jarvis è in grado di interagire con il sistema operativo per avviare applicazioni specifiche tramite comandi vocali (es. *"Apri Amazon Music"*).
Le app supportate di default sono:
* **Spotify** (`com.spotify.music`)
* **Orologio / Sveglia** (`com.android.deskclock`)
* **Calendario** (`com.android.calendar`)

> **Nota Tecnica:** Il sistema utilizza i "Package Name" (nomi pacchetto) Android per lanciare le app. I nomi preinseriti potrebbero variare in base al produttore del tuo dispositivo (Samsung, Huawei, Xiaomi, ecc.). La lista si personalizza dal file `config.py` (vedi la sezione [Configurazione](#%EF%B8%8F-configurazione-configpy)). Il lancio delle app avviene in thread separati per non bloccare il flusso principale.

### ⏰ Timer e Sveglie
* **Timer:** puoi averne quanti vuoi, con o senza nome. *"Timer di 10 minuti"*, *"timer per la pasta di 8 minuti"*, *"timer un'ora e mezza"*, *"ricordami di spegnere il forno tra 20 minuti"*. Per sapere quanto manca: *"quanto manca?"*. Per cancellarli: *"cancella il timer della pasta"* oppure *"cancella tutti i timer"*.
* **Sveglie una tantum:** *"Sveglia alle 7:30"*, *"svegliami alle sette e mezza"*, *"sveglia domani alle 6"*, *"sveglia lunedì alle 8"*, *"svegliami tra 20 minuti"*. Se l'ora è ambigua (*"alle 7"*) vale il prossimo 7 che arriva (di sera se è già pomeriggio); con *"domani"* vale la mattina. Puoi precisare con *"di sera"* o *"di mattina"*.
* **Sveglie ricorrenti:** *"Sveglia alle 7 dal lunedì al venerdì"*, *"ogni giorno"*, *"nel weekend"*, *"ogni lunedì"*. Per vederle: *"che sveglie ho?"*; per cancellarle: *"cancella la sveglia delle 7"* o *"cancella tutte le sveglie"*.
* **Sveglia con la radio:** *"Sveglia alle 7 con radio deejay"*. Con *"con la musica"* parte la radio preferita (`RADIO_PREFERITA`). Se la radio non si trova, suonano i bip.
* **Quando suonano:** una sveglia suona con bip ripetuti (tre bip e una pausa, in modo che il microfono possa sentirti), per al massimo `SVEGLIA_MAX_SEC` secondi (di default 5 minuti); un timer per al massimo 2 minuti. Per fermarle basta dire **"stop"** (senza wake word), **"rimanda"** / **"snooze"** (di default 10 minuti, oppure *"rimanda di 5 minuti"*), oppure toccare **FERMA** / **RIMANDA** sullo schermo.
* **Persistenza:** timer e sveglie sono salvati in `~/.jarvis/promemoria.json` (cartella modificabile con `DATI_DIR`). Se Jarvis è spento quando una sveglia dovrebbe suonare, quella sveglia non suona più (a meno che sia scaduta da meno di 2 minuti); le ricorrenti si riprogrammano da sole alla prossima occorrenza.

### 🎵 Musica
Jarvis usa un lettore `mpv` interno, controllato a voce. Ci sono tre sorgenti:

| Sorgente | Esempio | Cosa serve |
|---|---|---|
| **Radio** | *"Metti radio deejay"*, *"accendi la radio rtl 102.5"* | Niente: le stazioni si cercano su [radio-browser.info](https://www.radio-browser.info), in ordine di ascolti, prima in Italia. Puoi fissare i tuoi link in `RADIO` |
| **YouTube** | *"Metti i Queen"*, *"metti la canzone Bohemian Rhapsody"* | `pkg install yt-dlp`. Parte il primo risultato su 5, *"prossima"* passa al successivo |
| **File della tablet** | *"Metti un po' di musica"*, *"riproduci la mia musica"* | File audio nelle cartelle `MUSICA_CARTELLE` (vedi sotto) |

**Controlli:** *"pausa"*, *"riprendi"*, *"prossima canzone"*, *"canzone precedente"*, *"stop"* / *"spegni la musica"*, *"alza il volume"*, *"abbassa il volume"*, *"volume 40"* (da 0 a 100; i numeri da 1 a 10 valgono come scala di dieci), *"cosa sta suonando?"*.

**Musica che si abbassa da sola ("ducking"):** appena Jarvis sente la wake word (o tocchi la barra di stato), la musica scende a `DUCKING` (di default un quarto) mentre ascolta e risponde, poi torna al volume di prima. Se in quel momento chiedi di cambiare volume, il nuovo livello resta.

> ⚠️ **Limite hardware:** la tablet ha un solo microfono e non cancella l'eco, quindi con la musica ad alto volume il riconoscimento della wake word peggiora. Tieni il volume moderato, oppure usa **tocca per parlare** (barra di stato) o la voce vicino al microfono.

> ⚠️ **YouTube:** la riproduzione passa da `yt-dlp`, che ogni tanto smette di funzionare quando YouTube cambia qualcosa (si risolve aggiornandolo con `pkg upgrade`), ed è una zona grigia rispetto ai termini d'uso di YouTube. Si può disattivare con `MUSICA_YOUTUBE = False`.

#### 🟠 E Amazon Music (o Spotify)?
Amazon **non offre un'API** ai programmi esterni, quindi Jarvis non può dire all'app *"metti questa canzone"*. Quello che si può fare:
* *"Apri Amazon Music"* apre l'app (basta avere `"amazon music": "com.amazon.mp3"` in `LISTA_APP`).
* Per **controllare quello che sta già suonando** (pausa, riprendi, prossima, precedente) Jarvis può inviare i tasti multimediali ad Android tramite `adb`. Serve un'impostazione una tantum (da rifare dopo ogni riavvio della tablet):
  1. Sulla tablet attiva le *Opzioni sviluppatore* e il *Debug USB*.
  2. Collega la tablet al PC con un cavo USB ed esegui sul PC: `adb tcpip 5555`
  3. In Termux sulla tablet: `pkg install android-tools`, poi `adb connect localhost:5555` e accetta la richiesta sullo schermo.
  4. In `config.py` imposta `ADB_DISPOSITIVO = "localhost:5555"`.

  Da quel momento *"pausa"*, *"riprendi"*, *"prossima"* e *"precedente"* controllano l'app che sta suonando quando il lettore interno è fermo. Il **volume** (*"alza il volume"*, *"volume 40"*) usa `termux-volume` e **non** richiede `adb`.

### 🌙 Modalità riposo
La modalità riposo mostra solo l'orologio, attenuato, e silenzia gli annunci del calendario. **Timer e sveglie suonano comunque**, anche in riposo.

* **Notte automatica:** dalle 00:00 alle 08:00 (si cambia con `NOTTE_INIZIO` e `NOTTE_FINE` in `config.py`) Jarvis va in riposo da solo e ne esce da solo. Di notte risponde comunque ai comandi con la wake word.
* **Riposo manuale, quando esci:** *"Jarvis, sto uscendo"*, *"esco di casa"*, *"vado via"*, *"vado a lavorare"*, *"a dopo"*, *"entra in modalità riposo"*, *"riposati"*. Jarvis ferma la musica e passa in riposo. Resta così, anche di giorno, finché non lo risvegli. Mentre sei fuori ascolta **solo** la frase di risveglio (anche in inglese). Lo stato viene salvato: se riavvii lo script, il riposo resta.
* **Risveglio:** dì *"Wake up, daddy's home"* come nel film, oppure *"svegliati"*, *"svegliati, papà è a casa"*, *"papà è tornato"*, *"sono a casa"*, *"sono tornato"*, *"esci dalla modalità riposo"*. Non serve la wake word. Jarvis risponde *"Bentornato a casa, Signore"* e ti dice qual è il prossimo impegno del calendario. In alternativa, **tocca lo schermo**: si risveglia in silenzio.
* **Risvegliarlo di notte:** se lo risvegli durante la notte automatica, resta sveglio fino alle 08:00; la notte dopo torna da solo in riposo.
* **Frasi in inglese:** il riconoscimento vocale è in italiano, e una frase inglese verrebbe storpiata. Per questo, in riposo, ogni frase viene trascritta due volte (italiano e inglese): così *"wake up, daddy's home"* viene capita bene.

### 🤖 Personalità & System Prompt
Il modello AI è configurato con un system prompt dettagliato che definisce il comportamento di J.A.R.V.I.S.:
* Dà del **Lei** e chiama l'utente **"Signore"**
* Tono **colto, elegante, imperturbabile** con ironia britannica sottile
* Risposte **concise** (massimo 1-3 frasi) ottimizzate per la lettura vocale
* Output in **testo semplice** (niente markdown, asterischi o elenchi)
* Per agenda e meteo locale usa i dati forniti dal sistema; per notizie e dati in tempo reale usa la **ricerca web**
* **Mai esce dal personaggio**: non si identifica come modello linguistico

### 📅 Calendario, Meteo e Annunci
* **Aggiornamento:** il calendario viene riletto ogni minuto (`AGGIORNA_CALENDARIO_SEC`) e il meteo ogni 5 minuti, in background e senza mai bloccare l'interfaccia: se aggiungi un evento compare da solo. Nel pannello eventi, l'ora accanto a *AGG.* indica l'ultima lettura riuscita. Se un calendario non risponde, Jarvis tiene gli ultimi eventi noti e segnala che i dati non sono aggiornati.
* **Finestra temporale:** Jarvis legge gli eventi dei prossimi `GIORNI_AVANTI` giorni (di default 60); il pannello li mostra in ordine cronologico finché c'è spazio.
* **Più calendari:** puoi usarne quanti vuoi (es. il tuo e la Formula 1): gli eventi vengono uniti e ordinati per data.
* **Domande a voce:** Jarvis conosce l'agenda (i prossimi 15 eventi) e il meteo locale e risponde senza fare ricerche sul web. Per il meteo di altre città usa invece la ricerca web.
* **Annunci:** a 15 minuti dall'inizio e all'inizio dell'evento (non per gli eventi "tutto il giorno" e non in modalità riposo).

---

## 📂 Struttura del Progetto

```
J.A.R.V.I.S._AI_Assistent/
├── jarvis.py       # Script principale: AI, audio, HUD, collegamento di tutto
├── comandi.py      # Riconoscimento locale dei comandi in italiano
├── musica.py       # Lettore mpv, radio, YouTube, suoneria, tasti di sistema
├── promemoria.py   # Timer e sveglie persistenti
├── riposo.py       # Modalità riposo: notte automatica e riposo manuale
├── config.py       # Chiavi e impostazioni personali (escluso dal repository)
├── .gitignore      # Esclude config.py, __pycache__ e file temporanei
└── README.md       # Documentazione del progetto
```

I dati di timer e sveglie stanno fuori dal repository, in `~/.jarvis/`.

---

## 🚀 Requisiti

* Dispositivo Android (Tablet o Smartphone).
* App Termux (scaricare da F-Droid).
* App Termux:API (scaricare da F-Droid).
* Python 3.9 o superiore (incluso in Termux).
* Connessione Internet.
* Una API Key gratuita di **Groq Cloud**.
* *(Opzionale)* Un account Google Calendar o un feed iCal, per la dashboard degli eventi.
* *(Opzionale)* `yt-dlp` per la musica da YouTube.

---

## 📦 Installazione

**1. Aggiorna i repository e installa le dipendenze di sistema:**
Apri Termux e lancia:

```bash
pkg update && pkg upgrade
pkg install python pulseaudio sox ffmpeg mpv termux-api git
```

Per la musica da YouTube (opzionale):

```bash
pkg install yt-dlp
```

Per usare i file audio della tablet (opzionale), dai a Termux il permesso di leggere la memoria; compare la cartella `~/storage`:

```bash
termux-setup-storage
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

Tutto il resto (calendario, meteo, app, musica, modello) è opzionale: vedi la sezione [Configurazione](#%EF%B8%8F-configurazione-configpy).

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
| `GIORNI_AVANTI` | No | `60` | Quanti giorni in avanti leggere dal calendario |
| `AGGIORNA_CALENDARIO_SEC` | No | `60` | Ogni quanti secondi rileggere il calendario (minimo 15) |
| `CALENDARIO_NOCACHE` | No | `True` | Chiede il feed con un parametro diverso a ogni richiesta, per evitare copie in cache (mettilo a `False` se un server rifiuta l'URL) |
| `METEO_LAT`, `METEO_LON` | No | `41.686`, `12.778` (Velletri) | Coordinate per il meteo |
| `LISTA_APP` | No | Spotify, Orologio, Sveglia, Calendario | App che Jarvis può aprire a voce |
| `RADIO` | No | `{}` | Le tue radio preferite: nome parlato → link dello streaming |
| `RADIO_PREFERITA` | No | `""` | Radio usata da *"metti un po' di musica"* e dalle sveglie *"con la musica"* |
| `MUSICA_CARTELLE` | No | `["~/storage/music"]` | Cartelle con i file audio della tablet |
| `MUSICA_YOUTUBE` | No | `True` | Permette *"metti i Queen"* (ricerca su YouTube, serve `yt-dlp`) |
| `ADB_DISPOSITIVO` | No | `None` | Es. `"localhost:5555"`: abilita i tasti multimediali per Amazon Music e simili |
| `VOLUME_MUSICA` | No | `60` | Volume iniziale del lettore (0-100) |
| `DUCKING` | No | `0.25` | A che frazione scende la musica mentre Jarvis ascolta (0.25 = un quarto) |
| `SVEGLIA_MAX_SEC` | No | `300` | Dopo quanti secondi una sveglia smette da sola di suonare |
| `SNOOZE_MIN` | No | `10` | Minuti di *"rimanda"* |
| `NOTTE_INIZIO`, `NOTTE_FINE` | No | `0`, `8` | Ore della notte automatica (modalità riposo): dalle 00:00 alle 08:00 |
| `DATI_DIR` | No | `"~/.jarvis"` | Dove si salvano timer, sveglie e lo stato di riposo |

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
GIORNI_AVANTI = 60              # giorni da leggere in avanti
AGGIORNA_CALENDARIO_SEC = 60    # ogni quanti secondi rileggere il calendario (minimo 15)

# Meteo (opzionale): coordinate della tua città
METEO_LAT = 41.9028
METEO_LON = 12.4964

# App apribili a voce (opzionale): sostituisce la lista di default
LISTA_APP = {
    "amazon music": "com.amazon.mp3",
    "orologio": "com.android.deskclock",
    "calendario": "com.android.calendar",
}

# Musica (opzionale)
RADIO = {"deejay": "https://IL_TUO_LINK_STREAMING"}   # facoltativo: sostituisce la ricerca per quel nome
RADIO_PREFERITA = "deejay"
MUSICA_CARTELLE = ["~/storage/music", "~/storage/downloads"]
ADB_DISPOSITIVO = "localhost:5555"                      # solo se hai fatto la procedura adb

# Riposo (opzionale): ore della notte automatica
NOTTE_INIZIO = 0
NOTTE_FINE = 8
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

### 📻 Come impostare le radio
* Di norma basta dire il nome: *"metti radio deejay"*. Jarvis cerca la stazione su radio-browser.info, più ascoltata prima.
* Alcuni nomi parlati sono già tradotti (*"rai uno"*, *"rai due"*, *"rai tre"*, *"rtl"*, *"kiss kiss"*, *"capital"*, *"virgin"*).
* Se una stazione non si trova o vuoi un link preciso, mettilo in `RADIO`: `RADIO = {"deejay": "https://..."}`. Un nome presente in `RADIO` ha la precedenza sulla ricerca.
* `RADIO_PREFERITA` è la radio di *"metti un po' di musica"* (se non ci sono file sulla tablet) e delle sveglie *"con la musica"*.

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

Tieni le tue personalizzazioni **solo in `config.py`** (app, calendari, città, modello, musica): è un file non versionato, quindi `git pull` non va mai in conflitto. Se modifichi direttamente `jarvis.py` sulla tablet, il prossimo `git pull` potrebbe rifiutarsi di sovrascriverlo. Dopo l'aggiornamento riavvia lo script e ricarica la pagina.

---

## 🎙️ Comandi Vocali

I comandi segnati ⚡ sono riconosciuti in locale (istantanei); gli altri vanno al modello.

| Tipo | Esempi | Azione |
|---|---|---|
| **Attivazione** | *"Jarvis"*, *"Computer"*, *"Assistente"*, *"Svegliati"* — oppure tocca la barra di stato | Attiva l'ascolto del comando |
| ⚡ **Ora e data** | *"Che ore sono?"*, *"Che giorno è oggi?"* | Risponde subito |
| ⚡ **Timer** | *"Timer di 10 minuti"*, *"timer per la pasta di 8 minuti"*, *"quanto manca?"*, *"cancella il timer della pasta"* | Imposta, controlla, cancella |
| ⚡ **Sveglie** | *"Sveglia alle 7:30 dal lunedì al venerdì"*, *"sveglia domani alle 6"*, *"che sveglie ho?"*, *"cancella la sveglia delle 7"* | Imposta, elenca, cancella |
| ⚡ **Stop / rimanda** | *"Stop"*, *"basta"*, *"rimanda"*, *"snooze"*, *"rimanda di 5 minuti"* | Ferma o rimanda la sveglia che suona (senza wake word) |
| ⚡ **Radio** | *"Metti radio deejay"*, *"accendi la radio"* | Riproduce la radio |
| ⚡ **Musica** | *"Metti i Queen"*, *"metti un po' di musica"* | YouTube o file della tablet |
| ⚡ **Controllo musica** | *"Pausa"*, *"riprendi"*, *"prossima canzone"*, *"canzone precedente"*, *"spegni la musica"*, *"cosa sta suonando?"* | Controlla la riproduzione |
| ⚡ **Volume** | *"Alza il volume"*, *"abbassa il volume"*, *"volume 40"*, *"volume al massimo"* | Regola il volume |
| ⚡ **Apertura App** | *"Apri Amazon Music"* | Lancia l'app Android corrispondente (se in `LISTA_APP`) |
| **Domande AI** | *"Jarvis, chi ha vinto ieri la partita?"* | Elabora con Groq + ricerca web |
| **Agenda e meteo** | *"Che impegni ho domani?"*, *"che tempo fa oggi?"* | Risponde dai tuoi calendari e dal meteo locale |
| ⚡ **Riposo (esco)** | *"Jarvis, sto uscendo"*, *"esco di casa"*, *"vado via"*, *"entra in modalità riposo"* | Ferma la musica e passa in riposo finché non lo risvegli |
| ⚡ **Risveglio** | *"Wake up, daddy's home"*, *"svegliati"*, *"sono a casa"*, *"papà è tornato"* (senza wake word, se è in riposo) | Torna sveglio e dà il bentornato |
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
| Ho aggiunto un evento ma non compare | Google a volte serve il feed `.ics` con ritardo (anche di ore); oppure l'evento è in un calendario non presente in `ICAL_URLS` | Guarda l'ora accanto a *AGG.* nel pannello eventi: se è recente, Jarvis ha riletto il feed e il ritardo è lato Google. Verifica anche che l'evento sia nel calendario di cui hai copiato l'indirizzo |
| Nel terminale compare `[CALENDARIO] errore: ...` | URL errato, calendario non raggiungibile o librerie mancanti | Controlla l'URL; se l'errore è `ModuleNotFoundError`, installa `icalendar`, `recurring-ical-events` e `tzdata` |
| *"Per cercare musica su internet serve yt-dlp"* | `yt-dlp` non è installato (o `MUSICA_YOUTUBE = False`) | `pkg install yt-dlp` |
| *"Non riesco a trovare la radio ..."* | La ricerca non trova il nome, o manca internet | Prova un nome diverso o metti il link in `RADIO` |
| *"Metti i Queen"* non parte, o parte e si ferma subito | `yt-dlp` non aggiornato dopo un cambiamento di YouTube | `pkg upgrade` |
| La musica non si sente | `mpv` o `pulseaudio` non attivi | Prova a mano `mpv --no-video URL_DI_UNA_RADIO`; riavvia Jarvis (avvia da solo pulseaudio) |
| *"Pausa"* o *"prossima"* non controllano Amazon Music | Per Amazon serve la procedura `adb` | Vedi *E Amazon Music?* e imposta `ADB_DISPOSITIVO`; dopo ogni riavvio della tablet rifai `adb connect localhost:5555` |
| *"Stop"* non ferma la sveglia | Il microfono non ti sente sopra i bip | Usa i pulsanti **FERMA** / **RIMANDA** sullo schermo, o parla nella pausa tra i bip |
| La sveglia non è suonata dopo un riavvio | Jarvis era spento all'ora della sveglia | Le sveglie perse non suonano più; quelle ricorrenti si riprogrammano da sole |
| *"Wake up, daddy's home"* non lo risveglia | Il riconoscimento ha sentito male la frase inglese | Prova in italiano: *"svegliati"*, *"papà è tornato"*, *"sono a casa"*; oppure tocca lo schermo |
| Di giorno lo schermo è scuro e c'è scritto RIPOSO | È in riposo manuale (hai detto *"sto uscendo"*) e resta così finché non lo risvegli | Dì *"svegliati"* o tocca lo schermo |
| *"Jarvis"* non viene riconosciuto con la musica alta | Un solo microfono, nessuna cancellazione dell'eco | Tocca la barra di stato per parlare, oppure abbassa la musica |
| `git pull` rifiuta di aggiornare per modifiche locali | Hai modificato `jarvis.py` (o ci sono file `.pyc` versionati) sulla tablet | Sposta le tue impostazioni in `config.py`; poi `cp jarvis.py ~/jarvis_backup.py` e `git restore jarvis.py` prima del `git pull`. Per i `.pyc`: `git rm -r --cached __pycache__` una volta sul PC, poi commit e push |
| `./jarvis.py: Permission denied` | Lo script non è eseguibile | Si avvia sempre con `python jarvis.py` |

---

## 🛠️ Tecnologie Usate

* Python 3.9+
* Flask (Server Web Locale con PWA Manifest)
* **Groq Cloud API** (modello configurabile, con ricerca web integrata)
* **mpv** (musica, radio, voce e suoneria) con controllo via socket IPC
* **radio-browser.info** (ricerca radio) e **yt-dlp** (musica da YouTube, opzionale)
* **Open-Meteo** (meteo, senza chiave)
* **iCalendar** + **recurring-ical-events** (lettura di calendari iCal ed eventi ricorrenti)
* **gTTS** (Google Text-to-Speech)
* PulseAudio & Parecord (Gestione Audio a basso livello)
* SpeechRecognition (Input Vocale tramite Google Speech API)
* Termux:API (Wake Lock, Vibrazione, Volume, Apertura App)

---

## ℹ️ Note

* **Privacy:** per riconoscere la wake word, ogni frase captata dal microfono viene trascritta tramite la Google Speech API, anche se non è rivolta a Jarvis. Tienine conto nel scegliere dove posizionare il dispositivo.
* **Limiti del piano gratuito:** Groq limita richieste e token al minuto. Con la ricerca web una singola richiesta può essere grande: in quel caso Jarvis risponde comunque, ma senza ricerca. I comandi locali (timer, musica, ora...) non consumano il piano.
* **Accesso alla dashboard:** il server web ascolta solo su `localhost` (il browser deve girare sullo stesso dispositivo). Per aprirlo da un altro dispositivo in rete locale, in `run_web_server()` cambia `host='127.0.0.1'` in `host='0.0.0.0'`, sapendo che così chiunque sulla tua rete potrà vederlo.

---

> Progetto realizzato per ridare vita all'hardware datato senza dover comprare componenti esterni come un microcontrollore, un microfono e uno speaker.