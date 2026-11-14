"""Riconoscimento locale dei comandi in italiano.

`interpreta(testo)` restituisce un dizionario con almeno la chiave "tipo", oppure None se la frase
non e' un comando noto: in quel caso Jarvis la passa al modello (Groq). Cosi' timer, sveglie,
musica, volume e "che ore sono" rispondono subito, senza il giro di rete verso il modello.
"""
import re
import unicodedata
from datetime import datetime, timedelta

GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
_RE_GIORNO = "|".join(GIORNI)

WAKE = r"(?:ehi |ehy |hey |ok |senti )?(?:jarvis|giarvis|iarvis|service|servis|services|travis|davis|mavis|harvest|computer|assistente)"


# ---------------------------------------------------------------------------
# Normalizzazione e numeri a parole
# ---------------------------------------------------------------------------

def normalizza(testo):
    t = unicodedata.normalize("NFD", (testo or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("\u2019", "'").replace("`", "'")
    t = re.sub(r"[;!?]", " ", t)
    t = re.sub(r",", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def senza_wake(t):
    return re.sub(r"^(?:" + WAKE + r")\b[ ]*", "", t).strip()


_UNITA = {"zero": 0, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7, "otto": 8, "nove": 9,
          "dieci": 10, "undici": 11, "dodici": 12, "tredici": 13, "quattordici": 14, "quindici": 15,
          "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19}
_DECINE = {"venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50, "sessanta": 60,
           "settanta": 70, "ottanta": 80, "novanta": 90}
_STEM = {"vent": 20, "trent": 30, "quarant": 40, "cinquant": 50, "sessant": 60, "settant": 70, "ottant": 80, "novant": 90}
_COMP = {"uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7, "otto": 8, "nove": 9}
_UNO = {"un", "uno", "una"}
_UNITA_TEMPO = {"ora", "ore", "minuto", "minuti", "secondo", "secondi", "quarto", "quarti"}


def parola_numero(p):
    if p in _UNITA:
        return _UNITA[p]
    if p in _DECINE:
        return _DECINE[p]
    if p == "cento":
        return 100
    for pref, v in list(_DECINE.items()) + list(_STEM.items()):
        if p.startswith(pref) and p[len(pref):] in _COMP:
            return v + _COMP[p[len(pref):]]
    return None


def cifre(t):
    """Sostituisce i numeri scritti a parole con le cifre ("venti minuti" -> "20 minuti")."""
    t = re.sub(r"\bun'ora\b", "1 ora", t)
    t = re.sub(r"\bun'altra ora\b", "1 ora", t)
    t = re.sub(r"\ball'una\b", "alle 1", t)
    t = re.sub(r"\bl'una\b", "1", t)
    tok = t.split(" ")
    out, i = [], 0
    while i < len(tok):
        w = tok[i]
        nxt = tok[i + 1] if i + 1 < len(tok) else ""
        if w in _UNO:
            out.append("1" if nxt in _UNITA_TEMPO else w)
            i += 1
            continue
        n = parola_numero(w)
        if n is None:
            out.append(w)
            i += 1
            continue
        if n >= 20 and n % 10 == 0 and nxt in _COMP:  # "venti cinque" -> 25
            n += _COMP[nxt]
            i += 1
        out.append(str(n))
        i += 1
    return " ".join(out)


# ---------------------------------------------------------------------------
# Durate, orari, giorni
# ---------------------------------------------------------------------------

def estrai_durata(t):
    """Secondi in "10 minuti", "un'ora e mezza", "tre quarti d'ora", "90 secondi"... oppure None."""
    t = cifre(t)
    t = re.sub(r"\bmezz'?\s?ora\b|\bmezza ora\b", "30 minuti", t)
    t = re.sub(r"\b(?:(\d+) )?quart[oi] d'? ?ora\b", lambda m: f"{int(m.group(1) or 1) * 15} minuti", t)
    t = re.sub(r"\b(\d+) or[ae] e mezz[ao]\b", lambda m: f"{int(m.group(1)) * 60 + 30} minuti", t)
    tot, trovato = 0.0, False
    for num, unita in re.findall(r"(\d+(?:[.,]\d+)?)\s*(ore|ora|h|minuti|minuto|min|secondi|secondo|sec)\b", t):
        v = float(num.replace(",", "."))
        trovato = True
        if unita in ("ore", "ora", "h"):
            tot += v * 3600
        elif unita in ("minuti", "minuto", "min"):
            tot += v * 60
        else:
            tot += v
    if trovato:
        return int(round(tot))
    m = re.search(r"\btimer (?:di |da |a )?(\d+)\b", t)  # "timer di 10" = 10 minuti
    return int(m.group(1)) * 60 if m else None


_QUAL_AM = r"\b(?:di|del|della) (?:mattina|mattino)\b|\bstamattina\b|\bam\b"
_QUAL_PM = r"\b(?:di|del|della) (?:pomeriggio|sera)\b|\bstasera\b|\bpm\b|\bdi notte\b|\bdella notte\b"


def estrai_orario(t):
    """{"ore", "minuti", "qual"} da "alle 7:30", "alle sette e mezza", "alle otto meno un quarto"... o None."""
    t = cifre(t)
    t = re.sub(r"\b(?:a )?mezzogiorno\b", "alle 12:00", t)
    t = re.sub(r"\b(?:a )?mezzanotte\b", "alle 0:00", t)
    m = re.search(r"\b(?:alle ore|alle|delle|per le|verso le|ore)\s*(\d{1,2})(?:[:.](\d{2}))?(?!\d)", t)
    if not m:
        return None
    ore = int(m.group(1))
    minuti = int(m.group(2)) if m.group(2) else 0
    resto = t[m.end():]
    if not m.group(2):
        if re.match(r" e mezz[ao]\b", resto):
            minuti = 30
        elif re.match(r" e 1 quarto\b", resto):
            minuti = 15
        elif re.match(r" e 3 quarti\b", resto):
            minuti = 45
        elif re.match(r" meno 1 quarto\b", resto):
            ore, minuti = ore - 1, 45
        else:
            mm = re.match(r" meno (\d{1,2})\b", resto)
            if mm:
                ore, minuti = ore - 1, 60 - int(mm.group(1))
            else:
                mm = re.match(r" e (\d{1,2})\b", resto)
                if mm and int(mm.group(1)) < 60:
                    minuti = int(mm.group(1))
    if ore < 0:
        ore += 24
    if ore > 24 or minuti > 59:
        return None
    ore %= 24
    qual = "am" if re.search(_QUAL_AM, t) else "pm" if re.search(_QUAL_PM, t) else None
    if qual == "pm" and re.search(r"\b(?:di|della) notte\b", t) and ore < 6:
        qual = "am"  # "alle 3 di notte" = 03:00
    return {"ore": ore, "minuti": minuti, "qual": qual}


def ore_ricorrente(ore, qual):
    """Ora 0-23 per una sveglia ricorrente: se e' ambigua (1-12 senza mattina/sera) vale la mattina."""
    if qual == "pm" and ore < 12:
        return ore + 12
    if qual == "am" and ore == 12:
        return 0
    return ore


def istante_sveglia(ore, minuti, qual, adesso, data=None, weekday=None):
    """Prossimo istante (con fuso) per una sveglia una tantum.

    Senza giorno: il primo orario futuro tra mattina e sera se l'ora e' ambigua. Con "domani",
    "dopodomani" o un giorno della settimana: se e' ambigua vale la mattina."""
    if ore > 12 or ore == 0:
        cand = [ore]
    elif qual == "am":
        cand = [0 if ore == 12 else ore]
    elif qual == "pm":
        cand = [12 if ore == 12 else ore + 12]
    else:
        cand = [ore % 12, ore % 12 + 12]

    def a(giorno_offset, h):
        d = (adesso + timedelta(days=giorno_offset)).replace(hour=h, minute=minuti, second=0, microsecond=0)
        return d

    if data == "domani":
        return a(1, cand[0])
    if data == "dopodomani":
        return a(2, cand[0])
    if weekday is not None:
        off = (weekday - adesso.weekday()) % 7
        d = a(off, cand[0])
        return d if d > adesso else a(off + 7, cand[0])
    futuri = sorted(d for d in (a(0, h) for h in cand) if d > adesso)
    return futuri[0] if futuri else a(1, cand[0])


def estrai_giorni(t):
    """(elenco giorni 0=lunedi, ricorrente) per frasi come "ogni giorno", "dal lunedi al venerdi"."""
    if re.search(r"\b(ogni giorno|tutti i giorni|quotidian\w*|ogni mattina|tutte le mattine)\b", t):
        return list(range(7)), True
    if re.search(r"\b(feriali|lavorativ\w+)\b", t):
        return [0, 1, 2, 3, 4], True
    if re.search(r"\b(weekend|fine settimana|sabato e domenica)\b", t):
        return [5, 6], True
    m = re.search(r"\bdal (" + _RE_GIORNO + r") al (" + _RE_GIORNO + r")\b", t)
    if m:
        a, b = GIORNI.index(m.group(1)), GIORNI.index(m.group(2))
        giorni, g = [a], a
        while g != b:
            g = (g + 1) % 7
            giorni.append(g)
        return giorni, True
    nomi = sorted({GIORNI.index(g) for g in re.findall(r"\b(" + _RE_GIORNO + r")\b", t)})
    if not nomi:
        return None, False
    ricorrente = bool(re.search(r"\b(ogni|tutti i|tutte le)\b", t)) or len(nomi) > 1
    return nomi, ricorrente


# ---------------------------------------------------------------------------
# Frasi parlate
# ---------------------------------------------------------------------------

def durata_parlata(sec):
    sec = int(sec)
    ore, resto = divmod(sec, 3600)
    minuti, secondi = divmod(resto, 60)
    parti = []
    if ore:
        parti.append(f"{ore} {'ora' if ore == 1 else 'ore'}")
    if minuti:
        parti.append(f"{minuti} {'minuto' if minuti == 1 else 'minuti'}")
    if secondi or not parti:
        parti.append(f"{secondi} {'secondo' if secondi == 1 else 'secondi'}")
    return " e ".join(parti)


def orario_parlato(ore, minuti):
    if ore == 0 and minuti == 0:
        return "mezzanotte"
    base = "l'una" if ore == 1 else f"le {ore}"
    return base if minuti == 0 else f"{base} e {minuti}"


def giorni_parlati(giorni):
    if not giorni:
        return ""
    s = sorted(giorni)
    if s == list(range(7)):
        return "ogni giorno"
    if s == [0, 1, 2, 3, 4]:
        return "dal lunedì al venerdì"
    if s == [5, 6]:
        return "il sabato e la domenica"
    nomi = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
    return "ogni " + " e ".join(nomi[g] for g in s)


# ---------------------------------------------------------------------------
# Interprete
# ---------------------------------------------------------------------------

_ARTICOLI = r"(?:la |il |lo |l'|le |i |gli |un |una |uno |dei |degli |delle |del |della |dello )?"
_NON_NOMI = {"di", "da", "a", "per", "tra", "fra", "un", "una", "uno", "il", "la", "lo", "le", "i", "gli", "in", "su"}


def _nome_timer(t):
    m = re.search(r"\bricordami (?:di |che )(.+?) (?:tra|fra) \d", cifre(t))
    if m:
        return m.group(1).strip()
    t = cifre(t)
    m = re.search(r"\btimer (?:per |della |del |dello |dei |delle |degli |di )?" + _ARTICOLI +
                  r"([a-z]+(?: (?!(?:di|da|a|tra|fra|per)\b)[a-z]+)?) (?:di |da |a |tra |per )?\d", t)
    if m and m.group(1) not in _NON_NOMI:
        return m.group(1).strip()
    m = re.search(r"\btimer .*?\b(?:per|della|del|dello) " + _ARTICOLI + r"([a-z]+(?: [a-z]+)?)$", t)
    if m and m.group(1) not in _NON_NOMI:
        return m.group(1).strip()
    return None


def _num(t):
    t = cifre(t)
    m = re.search(r"\b(\d{1,3})\b", t)
    return int(m.group(1)) if m else None


_RISVEGLIO = [
    r"\bsvegliati\b", r"\briattivati\b", r"\bwake\s*up\b",
    r"\b(?:wake|weik|ueik|uake|weak|week|uick)\s*(?:up|ap|op)\b",   # "wake up" come lo sente il riconoscimento italiano
    r"\bdadd?y\w*", r"\bpapino\b",
    r"\bpapa\b.{0,14}\b(?:casa|tornato|arrivato|qui|rientrato)\b",
    r"\bsono (?:appena )?(?:a casa|tornato|tornata|rientrato|rientrata|di ritorno|arrivato|arrivata)\b",
    r"\besci dalla modalita(?: di)? riposo\b", r"\bmodalita attiva\b", r"\btorna (?:attivo|operativo)\b",
]
_RIPOSO_ENTRA = [
    r"\bsto (?:per )?uscendo\b", r"\bsto andando via\b",
    r"\bvado (?:a |al |in |all')?(?:lavoro|lavorare|scuola|universita|palestra)\b",
    r"\bmodalita (?:di )?riposo\b", r"\b(?:vai|entra|passa|metti|mettiti|mettimi) in (?:modalita )?riposo\b", r"\briposati\b",
    r"^(?:a dopo|a piu tardi|ci vediamo (?:dopo|piu tardi)|arrivederci)$",
]
_RIPOSO_BREVE = [r"\b(?:esco|esco di casa|vado via|vado fuori|me ne vado)\b"]  # solo se la frase e' molto corta


def _cerca(pattern, t):
    return any(re.search(p, t) for p in pattern)


def e_risveglio(testo, rigido=False):
    """True se la frase e' un "svegliati / wake up, daddy's home / sono a casa".

    rigido=True accetta solo frasi brevi: serve quando Jarvis e' gia' sveglio, per non scambiare
    per un risveglio una frase lunga che contiene "sono a casa". Da riposo si usa la ricerca larga."""
    t = senza_wake(normalizza(testo))
    if rigido and len(t.split()) > 6:
        return False
    return _cerca(_RISVEGLIO, t)


def interpreta(testo, app_note=()):
    """Riconosce un comando locale. `app_note`: nomi delle app apribili (chiavi di LISTA_APP)."""
    t = senza_wake(normalizza(testo))
    if not t:
        return None
    musica_w = r"\b(musica|radio|canzone|brano|brani|riproduzione|playlist|album)\b"

    # --- riposo (prima del resto: "esci dalla modalita riposo" non e' un comando di spegnimento) ---
    if len(t.split()) <= 6 and _cerca(_RISVEGLIO, t):
        return {"tipo": "riposo_esci"}
    if (len(t.split()) <= 7 and _cerca(_RIPOSO_ENTRA, t)) or (len(t.split()) <= 4 and _cerca(_RIPOSO_BREVE, t)):
        return {"tipo": "riposo_entra"}

    # --- ferma suoneria / musica -------------------------------------------------
    if re.search(r"\b(snooze|rimanda\w*|posticipa\w*)\b", t) or re.search(r"\b(?:ancora|altri) \w+ minuti\b", cifre(t)):
        d = estrai_durata(t)
        return {"tipo": "snooze", "minuti": max(1, d // 60) if d else None}
    stop_v = r"\b(stop|basta|fermati|ferma|fermala|fermalo|silenzio|zitto|zitta|spegni|spegnila|spegnilo|smettila|interrompi)\b"
    if re.search(stop_v, t) and not re.search(r"\b(cancella|elimina|annulla|togli|rimuovi)\b", t):
        if re.search(musica_w, t):
            return {"tipo": "musica_stop"}
        if re.fullmatch(r"(?:ok |va bene |e )?(?:stop|basta|fermati|ferma|fermala|silenzio|zitto|zitta|spegni|spegnila|smettila)(?: (?:la sveglia|il timer|tutto|adesso|ora|grazie|per favore))*", t) \
                or re.search(r"\b(sveglia|timer|allarme)\b", t):
            return {"tipo": "stop"}

    # --- timer ----------------------------------------------------------------------
    if re.search(r"\b(cancella|elimina|annulla|togli|rimuovi|ferma)\w* (?:tutti )?(?:il |i |lo |gli )?timer\b", t) \
            or re.search(r"\b(?:cancella|elimina|annulla)\b.*\btimer\b", t):
        nome = None
        m = re.search(r"\btimer (?:della |del |dello |di |per )?" + _ARTICOLI + r"([a-z]+(?: [a-z]+)?)$", t)
        if m and m.group(1) not in _NON_NOMI and m.group(1) not in ("tutti", "tutto"):
            nome = m.group(1)
        return {"tipo": "timer_cancella", "nome": nome, "tutti": bool(re.search(r"\btutti\b", t))}
    if re.search(r"\bquanto (?:manca|resta|rimane|tempo manca|tempo resta|tempo rimane)\b", t) or re.search(r"\bquanto tempo (?:manca|resta|rimane)\b", t):
        return {"tipo": "timer_quanto"}
    if re.search(r"\b(timer|conto alla rovescia)\b", t) or re.search(r"\b(?:avvisami|ricordami)\b.*\b(?:tra|fra) \S+", t):
        d = estrai_durata(t)
        if d:
            return {"tipo": "timer", "secondi": d, "nome": _nome_timer(t)}

    # --- sveglie ----------------------------------------------------------------------
    if re.search(r"\b(?:che|quali|elenco|lista|dimmi le|dimmi quali|ho delle?) sveglie?\b", t) or re.search(r"\bquante sveglie\b", t):
        return {"tipo": "sveglie_elenco"}
    if re.search(r"\b(cancella|elimina|annulla|togli|rimuovi|disattiva)\b", t) and re.search(r"\bsvegli[ae]\b", t):
        o = estrai_orario(t)
        return {"tipo": "sveglia_cancella", "tutte": bool(re.search(r"\btutte\b", t)),
                "ore": o["ore"] if o else None, "minuti": o["minuti"] if o else None, "qual": o["qual"] if o else None}
    if re.search(r"\bsvegli[ae]\b|\bsvegliami\b|\bsvegliarmi\b", t) and not re.search(r"^svegliati$", t):
        radio = None
        m = re.search(r"\bcon (?:la )?radio (.+)$", t)
        if m:
            radio = m.group(1).strip()
        elif re.search(r"\bcon (?:la )?musica\b", t):
            radio = ""
        giorni, ricorrente = estrai_giorni(t)
        data = "dopodomani" if "dopodomani" in t else "domani" if re.search(r"\bdomani\b", t) else None
        o = estrai_orario(t)
        if o:
            return {"tipo": "sveglia", "ore": o["ore"], "minuti": o["minuti"], "qual": o["qual"], "radio": radio,
                    "giorni": giorni if ricorrente else None, "weekday": giorni[0] if (giorni and not ricorrente) else None,
                    "data": data}
        d = estrai_durata(t)
        if d:
            return {"tipo": "sveglia_tra", "secondi": d, "radio": radio}

    # --- ora e data ------------------------------------------------------------------
    if re.search(r"\bche ore (?:sono|fa)\b|\bche ora e\b|\bche ora fa\b|\bdimmi l'ora\b|\bl'ora esatta\b", t):
        return {"tipo": "ora"}
    if re.search(r"\bche giorno e\b|\bche data e\b|\bin che giorno siamo\b|\bche giorno della settimana\b", t):
        return {"tipo": "data"}

    # --- controllo musica ----------------------------------------------------------------
    if re.search(r"\b(cosa|che cosa) sta suonando\b|\bche (?:canzone|musica|brano) e\b|\bcos'e questa (?:canzone|musica)\b|\bche radio e\b", t):
        return {"tipo": "musica_cosa"}
    if re.search(r"\b(?:metti|mettila|mettilo) in pausa\b|^pausa$|\bfai una pausa\b", t):
        return {"tipo": "musica_pausa"}
    if re.search(r"\briprendi\b|\briparti\b|\bcontinua\b|\briavvia la musica\b|^play$|\bfai ripartire\b", t):
        return {"tipo": "musica_riprendi"}
    if re.search(r"\b(prossim[ao]|avanti|salta|successiv[ao]|next)\b", t) and re.search(r"\b(canzone|brano|traccia|musica|salta|avanti|prossim[ao]|successiv[ao]|next)\b", t) \
            and not re.search(r"\b(sveglia|timer|metti|riproduci)\b", t):
        return {"tipo": "musica_prossima"}
    if re.search(r"\b(precedente|indietro|torna indietro|canzone prima|previous)\b", t) and not re.search(r"\b(sveglia|timer|metti)\b", t):
        return {"tipo": "musica_precedente"}
    if re.search(r"\bvolume\b|\b(?:piu|meno) (?:forte|piano|alto|basso)\b|\balza\b.*\bmusica\b|\babbassa\b", t):
        if re.search(r"\b(?:al )?massimo\b", t):
            return {"tipo": "volume_imposta", "valore": 100}
        if re.search(r"\b(?:al )?minimo\b|\bmuto\b", t):
            return {"tipo": "volume_imposta", "valore": 0}
        n = _num(t) if re.search(r"\bvolume\b", t) else None
        if n is not None and not re.search(r"\b(alza|abbassa|aumenta|diminuisci)\b", t):
            return {"tipo": "volume_imposta", "valore": n * 10 if n <= 10 else min(n, 100)}
        if re.search(r"\b(alza|aumenta|piu forte|piu alto|su)\b", t):
            return {"tipo": "volume_delta", "delta": 15}
        if re.search(r"\b(abbassa|diminuisci|piu piano|piu basso|meno forte|giu)\b", t):
            return {"tipo": "volume_delta", "delta": -15}

    # --- avvio musica ------------------------------------------------------------------------
    verbo = r"(?:metti|mettimi|mettimela|accendi|ascolta|riproduci|fai partire|fammi sentire|fammi ascoltare|suona|sintonizzati su|vai su|voglio ascoltare|avvia)"
    m = re.search(r"\b" + verbo + r" (?:la |il |lo |l')?radio (.+)$", t) or re.search(r"\b(?:accendi|apri) (?:la )?radio$", t)
    if m:
        nome = m.group(1).strip() if m.groups() else ""
        return {"tipo": "radio", "nome": nome}
    if re.search(r"\b(?:metti|accendi|fai partire|riproduci|ascolta) (?:un po' di |della |la |my |la mia )?(?:musica|canzoni)(?: a caso| casuale)?$", t) \
            or re.search(r"\b(?:la mia musica|musica casuale|shuffle|in modalita casuale)\b", t):
        return {"tipo": "musica_locale"}
    m = re.search(r"\b" + verbo + r" (?:su )?" + _ARTICOLI + r"(?:canzone |brano |album |playlist |musica di |musica dei |musica degli |musica delle |canzoni di |canzoni dei |musica )?(.+)$", t)
    if m:
        q = m.group(1).strip()
        q = re.sub(r"\b(per favore|per piacere|grazie|adesso|ora)$", "", q).strip()
        if q and not re.search(r"\b(sveglia|timer|volume|app|applicazione)\b", q):
            if q in app_note or any(q == n or q.startswith(n + " ") for n in app_note):
                return {"tipo": "apri_app", "nome": q}
            return {"tipo": "cerca_musica", "query": q}

    # --- apri app --------------------------------------------------------------------------------
    m = re.search(r"^(?:apri|avvia|lancia|aprimi)\s+(?:l'app |l'applicazione |app |applicazione )?(.+)$", t)
    if m:
        return {"tipo": "apri_app", "nome": m.group(1).strip()}
    return None
