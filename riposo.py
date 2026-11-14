"""Modalita' riposo di Jarvis.

Due modi per andare in riposo:
* **notte** automatica: dalle `inizio` alle `fine` (di default 00:00-08:00);
* **manuale**: quando lo chiedi tu ("sto uscendo") e fino a quando lo risvegli.

Se ti risvegli durante la notte automatica, Jarvis resta sveglio fino alla fine di quella notte.
Il riposo manuale viene salvato su file, cosi' sopravvive a un riavvio dello script.
"""
import json
import os
import threading
from datetime import datetime, timedelta


class Riposo:
    def __init__(self, percorso, adesso, inizio=0, fine=8):
        self.percorso = percorso
        self.adesso = adesso
        self.inizio = int(inizio) % 24
        self.fine = int(fine) % 24
        self.lock = threading.RLock()
        self.manuale = False
        self.sveglio_fino = None
        self._carica()

    # -- persistenza -------------------------------------------------------------
    def _carica(self):
        try:
            with open(self.percorso, encoding="utf-8") as f:
                dati = json.load(f)
            self.manuale = bool(dati.get("manuale"))
            if dati.get("sveglio_fino"):
                self.sveglio_fino = datetime.fromisoformat(dati["sveglio_fino"])
        except (OSError, ValueError, AttributeError, TypeError):
            self.manuale, self.sveglio_fino = False, None

    def _salva(self):
        try:
            os.makedirs(os.path.dirname(self.percorso) or ".", exist_ok=True)
            tmp = self.percorso + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"manuale": self.manuale,
                           "sveglio_fino": self.sveglio_fino.isoformat() if self.sveglio_fino else None}, f)
            os.replace(tmp, self.percorso)
        except OSError:
            pass  # il riposo funziona comunque, solo non sopravvive a un riavvio

    # -- notte ----------------------------------------------------------------------
    def e_notte(self, ora=None):
        h = (ora or self.adesso()).hour
        if self.inizio == self.fine:
            return False
        if self.inizio < self.fine:
            return self.inizio <= h < self.fine
        return h >= self.inizio or h < self.fine

    def fine_notte(self, ora=None):
        ora = ora or self.adesso()
        fine = ora.replace(hour=self.fine, minute=0, second=0, microsecond=0)
        return fine if fine > ora else fine + timedelta(days=1)

    # -- stato -------------------------------------------------------------------------
    def stato(self, ora=None):
        """"manuale", "notte" oppure None (Jarvis e' sveglio)."""
        ora = ora or self.adesso()
        with self.lock:
            if self.manuale:
                return "manuale"
            if self.e_notte(ora) and not (self.sveglio_fino and ora < self.sveglio_fino):
                return "notte"
            return None

    def entra(self):
        """Riposo manuale ("sto uscendo")."""
        with self.lock:
            self.manuale = True
            self.sveglio_fino = None
            self._salva()

    def esci(self):
        """Risveglio. Restituisce lo stato che aveva prima (None se era gia' sveglio)."""
        ora = self.adesso()
        with self.lock:
            prima = self.stato(ora)
            self.manuale = False
            self.sveglio_fino = self.fine_notte(ora) if self.e_notte(ora) else None
            self._salva()
            return prima
