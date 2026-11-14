"""Musica per Jarvis: un lettore `mpv` pilotato a voce, piu' la suoneria delle sveglie.

* `Lettore`: tiene un mpv acceso in background e lo controlla via IPC (pausa, prossima, volume...).
* Sorgenti: radio (ricerca su radio-browser.info), YouTube (via yt-dlp), file locali.
* "Ducking": abbassa il volume mentre Jarvis ascolta e parla, cosi' sente meglio la tua voce.
* `Suoneria`: bip ripetuti per sveglie e timer, in un processo mpv separato.
* `tasto_sistema` / `volume_sistema`: controllo di quello che gia' suona sulla tablet (es. Amazon Music).
"""
import itertools
import json
import math
import os
import random
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import wave
from contextlib import contextmanager

import requests

ESTENSIONI = (".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav", ".aac")
RADIO_SERVER = ["https://de1.api.radio-browser.info", "https://nl1.api.radio-browser.info",
                "https://fi1.api.radio-browser.info"]
# nomi parlati -> nome da cercare
ALIAS_RADIO = {"rai uno": "rai radio 1", "radio uno": "rai radio 1", "rai radio uno": "rai radio 1",
               "rai due": "rai radio 2", "radio due": "rai radio 2", "rai radio due": "rai radio 2",
               "rai tre": "rai radio 3", "radio tre": "rai radio 3", "rai radio tre": "rai radio 3",
               "rtl": "rtl 102.5", "kiss kiss": "radio kiss kiss", "capital": "radio capital", "virgin": "virgin radio"}


# ---------------------------------------------------------------------------
# Sorgenti
# ---------------------------------------------------------------------------

def cerca_radio(nome, get=requests.get, paese="IT", limite=5):
    """[(nome stazione, url)] dalle stazioni piu' ascoltate che contengono `nome`."""
    nome = ALIAS_RADIO.get(nome.strip().lower(), nome.strip())
    for cc in (paese, None):
        for base in RADIO_SERVER:
            params = {"name": nome, "hidebroken": "true", "order": "clickcount", "reverse": "true", "limit": limite}
            if cc:
                params["countrycode"] = cc
            try:
                r = get(base + "/json/stations/search", params=params, headers={"User-Agent": "JARVIS-Termux/1.0"}, timeout=8)
                r.raise_for_status()
                dati = r.json()
            except Exception:
                continue
            ris = [(s.get("name", "").strip() or nome, s.get("url_resolved") or s.get("url"))
                   for s in dati if s.get("url_resolved") or s.get("url")]
            if ris:
                return ris
    return []


def youtube_disponibile():
    return shutil.which("yt-dlp") is not None


def sorgente_youtube(query, n=5):
    """mpv espande la ricerca in una lista di n risultati: "prossima" passa al successivo."""
    return f"ytdl://ytsearch{n}:{query}"


def trova_musica(cartelle, max_file=300):
    """File audio nelle cartelle (anche annidate), mescolati."""
    files = []
    for c in cartelle:
        for root, _, nomi in os.walk(os.path.expanduser(c)):
            files += [os.path.join(root, n) for n in nomi if n.lower().endswith(ESTENSIONI)]
            if len(files) > 5000:
                break
    random.shuffle(files)
    return files[:max_file]


# ---------------------------------------------------------------------------
# Lettore (mpv via IPC)
# ---------------------------------------------------------------------------

class Lettore:
    def __init__(self, sock=None, mpv="mpv", extra=None, volume_iniziale=60):
        self.sock = sock or os.path.join(tempfile.gettempdir(), "jarvis-mpv.sock")
        self.mpv = mpv
        self.extra = list(extra or [])
        self.volume_iniziale = volume_iniziale
        self.proc = None
        self.titolo_sorgente = None
        self.lock = threading.RLock()
        self._rid = itertools.count(1)
        self._duck = 0
        self._vol_prima = None
        self._fattore = 0.25

    # -- processo ------------------------------------------------------------------
    def _vivo(self):
        return self.proc is not None and self.proc.poll() is None

    def avvia(self):
        with self.lock:
            if self._vivo() and os.path.exists(self.sock):
                return True
            try:
                os.remove(self.sock)
            except FileNotFoundError:
                pass
            args = [self.mpv, "--no-terminal", "--idle=yes", "--no-video", "--force-window=no", "--audio-display=no",
                    "--ytdl-format=bestaudio/best", f"--volume={self.volume_iniziale}",
                    f"--input-ipc-server={self.sock}"] + self.extra
            try:
                self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (FileNotFoundError, OSError):
                self.proc = None
                return False
            for _ in range(60):
                if os.path.exists(self.sock):
                    return True
                time.sleep(0.1)
            return False

    def chiudi(self):
        with self.lock:
            if self._vivo():
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None

    # -- IPC -------------------------------------------------------------------------------
    def _cmd(self, *args, timeout=3):
        """(riuscito, dato). Se mpv non c'e' restituisce (False, None) senza lanciarlo."""
        if not os.path.exists(self.sock):
            return False, None
        rid = next(self._rid)
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(self.sock)
            s.sendall((json.dumps({"command": list(args), "request_id": rid}) + "\n").encode())
            buf = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    return False, None
                buf += chunk
                while b"\n" in buf:
                    riga, buf = buf.split(b"\n", 1)
                    try:
                        r = json.loads(riga)
                    except ValueError:
                        continue
                    if r.get("request_id") == rid:
                        return r.get("error") == "success", r.get("data")
        except (OSError, socket.timeout):
            return False, None
        finally:
            try:
                s.close()
            except Exception:
                pass

    # -- riproduzione ------------------------------------------------------------------------
    def riproduci(self, sorgente, titolo=None):
        if not self.avvia():
            return False
        ok, _ = self._cmd("loadfile", sorgente, "replace")
        self._cmd("set_property", "pause", False)
        self.titolo_sorgente = titolo
        return ok

    def riproduci_lista(self, sorgenti, titolo=None):
        if not sorgenti or not self.avvia():
            return False
        ok, _ = self._cmd("loadfile", sorgenti[0], "replace")
        for s in sorgenti[1:]:
            self._cmd("loadfile", s, "append")
        self._cmd("set_property", "pause", False)
        self.titolo_sorgente = titolo
        return ok

    def attivo(self):
        ok, v = self._cmd("get_property", "idle-active")
        return bool(ok and v is False)

    def in_pausa(self):
        ok, v = self._cmd("get_property", "pause")
        return bool(ok and v)

    def pausa(self):
        return self._cmd("set_property", "pause", True)[0]

    def riprendi(self):
        return self._cmd("set_property", "pause", False)[0]

    def stop(self):
        self.titolo_sorgente = None
        return self._cmd("stop")[0]

    def prossima(self):
        return self._cmd("playlist-next")[0]

    def precedente(self):
        return self._cmd("playlist-prev")[0]

    def posizione(self):
        ok, v = self._cmd("get_property", "playlist-pos")
        return v if ok else None

    # -- volume ---------------------------------------------------------------------------------
    def _volume_reale(self):
        ok, v = self._cmd("get_property", "volume")
        return float(v) if ok and v is not None else None

    def _set_vol(self, valore):
        return self._cmd("set_property", "volume", max(0, min(100, int(round(valore)))))[0]

    def volume(self):
        """Livello scelto dall'utente (non quello temporaneamente abbassato dal ducking)."""
        with self.lock:
            if self._duck and self._vol_prima is not None:
                return self._vol_prima
        return self._volume_reale()

    def imposta_volume(self, valore):
        valore = max(0, min(100, int(valore)))
        with self.lock:
            if self._duck and self._vol_prima is not None:
                self._vol_prima = valore
                return self._set_vol(valore * self._fattore)
        return self._set_vol(valore)

    def volume_delta(self, delta):
        v = self.volume()
        if v is None:
            return None
        nuovo = max(0, min(100, int(v + delta)))
        self.imposta_volume(nuovo)
        return nuovo

    # -- cosa suona ------------------------------------------------------------------------------
    def titolo(self):
        ok, meta = self._cmd("get_property", "metadata")
        if ok and isinstance(meta, dict):
            m = {k.lower(): v for k, v in meta.items()}
            if m.get("icy-title"):
                return m["icy-title"]
            if m.get("title"):
                return (m.get("artist") + " - " if m.get("artist") else "") + m["title"]
        ok, t = self._cmd("get_property", "media-title")
        if self.titolo_sorgente and (not ok or not t or t.startswith(("http", "ytdl:"))):
            return self.titolo_sorgente
        return t if ok and t else self.titolo_sorgente

    def stato(self):
        if not self.attivo():
            return {"attiva": False, "pausa": False, "titolo": None}
        return {"attiva": True, "pausa": self.in_pausa(), "titolo": self.titolo()}

    # -- ducking ----------------------------------------------------------------------------------
    def abbassa(self, fattore=0.25):
        """Abbassa il volume (annidabile). Si ripristina con ripristina()."""
        with self.lock:
            self._duck += 1
            if self._duck == 1:
                v = self._volume_reale() if self.attivo() else None
                self._vol_prima = v
                self._fattore = fattore
                if v is not None:
                    self._set_vol(v * fattore)

    def ripristina(self):
        with self.lock:
            if self._duck == 0:
                return
            self._duck -= 1
            if self._duck == 0 and self._vol_prima is not None:
                self._set_vol(self._vol_prima)
                self._vol_prima = None

    @contextmanager
    def ducking(self, fattore=0.25):
        self.abbassa(fattore)
        try:
            yield
        finally:
            self.ripristina()


# ---------------------------------------------------------------------------
# Suoneria di sveglie e timer
# ---------------------------------------------------------------------------

def crea_suoneria(percorso, frequenza=1000, rate=22050):
    """Tre bip e una pausa, da ripetere: nella pausa il microfono riesce a sentire "stop"."""
    os.makedirs(os.path.dirname(percorso) or ".", exist_ok=True)

    def bip(durata=0.18):
        n = int(rate * durata)
        fade = int(rate * 0.012)
        out = []
        for i in range(n):
            a = 0.6 * math.sin(2 * math.pi * frequenza * i / rate)
            a *= min(1.0, i / fade, (n - i) / fade)
            out.append(int(a * 32767))
        return out

    muto = lambda d: [0] * int(rate * d)
    campioni = []
    for _ in range(3):
        campioni += bip() + muto(0.14)
    campioni += muto(1.1)
    with wave.open(percorso, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", c) for c in campioni))
    return percorso


class Suoneria:
    def __init__(self, mpv="mpv", extra=None):
        self.mpv = mpv
        self.extra = list(extra or [])
        self.proc = None

    def attiva(self):
        return self.proc is not None and self.proc.poll() is None

    def avvia(self, wav, volume=85):
        self.ferma()
        try:
            self.proc = subprocess.Popen([self.mpv, "--no-terminal", "--no-video", "--loop-file=inf",
                                          f"--volume={volume}"] + self.extra + [wav],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except (FileNotFoundError, OSError):
            self.proc = None
            return False

    def ferma(self):
        if self.attiva():
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


# ---------------------------------------------------------------------------
# Controllo di cio' che suona sul sistema (es. Amazon Music)
# ---------------------------------------------------------------------------

KEYCODE = {"riprendi": "KEYCODE_MEDIA_PLAY", "pausa": "KEYCODE_MEDIA_PAUSE", "prossima": "KEYCODE_MEDIA_NEXT",
           "precedente": "KEYCODE_MEDIA_PREVIOUS", "stop": "KEYCODE_MEDIA_STOP"}


def tasto_sistema(azione, dispositivo, run=subprocess.run):
    """Invia un tasto multimediale ad Android via adb (serve `adb connect` una tantum)."""
    if not dispositivo or azione not in KEYCODE:
        return False
    try:
        r = run(["adb", "-s", dispositivo, "shell", "input", "keyevent", KEYCODE[azione]],
                capture_output=True, timeout=8)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def volume_sistema(delta=None, valore=None, run=subprocess.run):
    """Volume multimediale di Android (in %) con termux-volume. Restituisce il nuovo livello o None."""
    try:
        out = run(["termux-volume"], capture_output=True, text=True, timeout=5).stdout
        musica = next(s for s in json.loads(out) if s.get("stream") == "music")
        mx, cur = int(musica["max_volume"]), int(musica["volume"])
        if valore is not None:
            nuovo = round(max(0, min(100, valore)) / 100 * mx)
        else:
            passo = max(1, round(abs(delta) / 100 * mx))
            nuovo = cur + (passo if delta > 0 else -passo)
        nuovo = max(0, min(mx, nuovo))
        run(["termux-volume", "music", str(nuovo)], capture_output=True, timeout=5)
        return int(nuovo / mx * 100)
    except (FileNotFoundError, StopIteration, ValueError, KeyError, subprocess.TimeoutExpired, OSError):
        return None
