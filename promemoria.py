"""Timer e sveglie persistenti.

Salvati in un file JSON, cosi' sopravvivono ai riavvii di Jarvis. Supporta timer con nome (anche piu'
di uno insieme), sveglie una tantum o ricorrenti (giorni della settimana) e il "rimanda" (snooze).
Questo modulo non suona nulla: `scattati()` restituisce cosa e' scaduto e se ne occupa Jarvis.
"""
import json
import os
import threading
import uuid
from datetime import datetime, timedelta

# Un promemoria scaduto da piu' di cosi' (Jarvis era spento) non viene piu' fatto suonare
TOLLERANZA_SEC = 120


def prossima_occorrenza(ore, minuti, giorni, da):
    """Primo istante dopo `da` alle ore:minuti, in uno dei `giorni` (0=lunedi) se indicati."""
    for off in range(0, 9):
        d = (da + timedelta(days=off)).replace(hour=ore, minute=minuti, second=0, microsecond=0)
        if d > da and (not giorni or d.weekday() in giorni):
            return d
    return None


class Promemoria:
    def __init__(self, percorso, adesso):
        self.percorso = percorso
        self.adesso = adesso
        self.lock = threading.RLock()
        self.voci = []
        self.carica()

    # -- persistenza ------------------------------------------------------------
    def carica(self):
        with self.lock:
            try:
                with open(self.percorso, encoding="utf-8") as f:
                    dati = json.load(f)
                self.voci = [v for v in dati if isinstance(v, dict) and v.get("quando") and v.get("tipo")]
            except FileNotFoundError:
                self.voci = []
            except (ValueError, OSError):
                try:
                    os.replace(self.percorso, self.percorso + ".corrotto")
                except OSError:
                    pass
                self.voci = []

    def _salva(self):
        os.makedirs(os.path.dirname(self.percorso) or ".", exist_ok=True)
        tmp = self.percorso + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.voci, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.percorso)

    # -- creazione ----------------------------------------------------------------
    def aggiungi_timer(self, secondi, nome=None):
        secondi = max(1, min(int(secondi), 24 * 3600))
        v = {"id": uuid.uuid4().hex[:8], "tipo": "timer", "nome": nome or None,
             "quando": (self.adesso() + timedelta(seconds=secondi)).isoformat(),
             "durata": secondi, "giorni": None, "azione": None}
        with self.lock:
            self.voci.append(v)
            self._salva()
        return dict(v)

    def aggiungi_sveglia(self, ore, minuti, giorni=None, azione=None, quando=None, nome=None):
        """Sveglia ricorrente (giorni) o una tantum. `quando`: istante preciso per le una tantum."""
        giorni = sorted(set(giorni)) if giorni else None
        if quando is None:
            quando = prossima_occorrenza(ore, minuti, giorni, self.adesso())
        v = {"id": uuid.uuid4().hex[:8], "tipo": "sveglia", "nome": nome or None, "quando": quando.isoformat(),
             "ore": ore, "minuti": minuti, "giorni": giorni, "azione": azione}
        with self.lock:
            self.voci.append(v)
            self._salva()
        return dict(v)

    def aggiungi_sveglia_tra(self, secondi, azione=None):
        quando = self.adesso() + timedelta(seconds=max(1, int(secondi)))
        return self.aggiungi_sveglia(quando.hour, quando.minute, None, azione, quando=quando)

    def rimanda(self, voce, minuti):
        """Dopo uno scatto: nuova sveglia una tantum tra `minuti`, con la stessa azione."""
        quando = self.adesso() + timedelta(minutes=max(1, int(minuti)))
        return self.aggiungi_sveglia(quando.hour, quando.minute, None, voce.get("azione"), quando=quando,
                                     nome=voce.get("nome"))

    # -- consultazione ---------------------------------------------------------------
    def elenco(self, tipo=None):
        with self.lock:
            voci = [dict(v) for v in self.voci if not tipo or v["tipo"] == tipo]
        return sorted(voci, key=lambda v: v["quando"])

    def quanto_manca(self):
        """[(timer, secondi rimasti)] in ordine di scadenza."""
        ora = self.adesso()
        return [(v, max(0, int((datetime.fromisoformat(v["quando"]) - ora).total_seconds())))
                for v in self.elenco("timer")]

    def pubblico(self):
        return [{"tipo": v["tipo"], "nome": v.get("nome"), "quando": v["quando"], "giorni": v.get("giorni")}
                for v in self.elenco()]

    # -- cancellazione -----------------------------------------------------------------
    def cancella(self, tipo=None, nome=None, ore=None, minuti=None, qual=None, tutti=False):
        """Rimuove le voci che corrispondono; restituisce quante."""
        if ore is not None and qual is None and 1 <= ore <= 12:
            candidate = {ore % 12, ore % 12 + 12}
        elif ore is not None and qual == "pm" and ore < 12:
            candidate = {ore + 12}
        elif ore is not None:
            candidate = {ore}
        else:
            candidate = None

        def corrisponde(v):
            if tipo and v["tipo"] != tipo:
                return False
            if tutti:
                return True
            if nome:
                return nome in (v.get("nome") or "")
            if candidate is not None:
                return v.get("ore") in candidate and (minuti is None or v.get("minuti") == minuti)
            return False

        with self.lock:
            prima = len(self.voci)
            self.voci = [v for v in self.voci if not corrisponde(v)]
            rimosse = prima - len(self.voci)
            if rimosse:
                self._salva()
        return rimosse

    # -- scadenze ---------------------------------------------------------------------------
    def scattati(self):
        """Voci scadute da far suonare ora. Le ricorrenti vengono riprogrammate, le altre tolte."""
        ora = self.adesso()
        scattate, cambiato = [], False
        with self.lock:
            restanti = []
            for v in self.voci:
                quando = datetime.fromisoformat(v["quando"])
                if quando > ora:
                    restanti.append(v)
                    continue
                cambiato = True
                if (ora - quando).total_seconds() <= TOLLERANZA_SEC:
                    scattate.append(dict(v))
                if v.get("giorni"):
                    prox = prossima_occorrenza(v["ore"], v["minuti"], v["giorni"], ora)
                    if prox:
                        v["quando"] = prox.isoformat()
                        restanti.append(v)
            self.voci = restanti
            if cambiato:
                self._salva()
        return scattate
