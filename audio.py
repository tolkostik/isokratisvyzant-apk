"""
Αναπαραγωγή ισοκρατημάτων.

Android: AudioTrack σε στατική λειτουργία με σημεία βρόχου (συνεχής ήχος χωρίς κενό).
Υπολογιστής: Kivy SoundLoader με αρχείο WAV (για δοκιμές).
Ομαλές μεταβάσεις: κάθε φωνή έχει δική της καμπύλη έντασης (attack / release).
"""
import collections
import hashlib
import os
import struct
import threading
import time

from kivy.clock import Clock
from kivy.utils import platform

import synth

IS_ANDROID = platform == "android"


class _AndroidTrack:
    """Εισαγωγή (μία φορά) + βρόχος χωρίς κενό, σε στατικό AudioTrack."""

    def __init__(self, data):
        from jnius import autoclass
        intro, loop = data
        pcm = intro + loop
        AudioTrack = autoclass("android.media.AudioTrack")
        AudioManager = autoclass("android.media.AudioManager")
        AudioFormat = autoclass("android.media.AudioFormat")
        self.t = AudioTrack(AudioManager.STREAM_MUSIC, synth.SR, AudioFormat.CHANNEL_OUT_MONO,
                            AudioFormat.ENCODING_PCM_16BIT, len(pcm), AudioTrack.MODE_STATIC)
        self.t.write(pcm, 0, len(pcm))
        self.t.setLoopPoints(len(intro) // 2, len(pcm) // 2, -1)
        self.t.setVolume(0.0)
        self.t.play()

    def volume(self, v):
        self.t.setVolume(float(max(0.0, min(1.0, v))))

    def close(self):
        try:
            self.t.stop()
            self.t.release()
        except Exception:  # noqa: BLE001
            pass


class _DesktopTrack:
    def __init__(self, data, path):
        pcm = data[1] if isinstance(data, tuple) else data
        from kivy.core.audio import SoundLoader
        if not os.path.exists(path):
            synth.to_wav(pcm, path)
        self.s = SoundLoader.load(path)
        if self.s:
            self.s.loop = True
            self.s.volume = 0
            self.s.play()

    def volume(self, v):
        if self.s:
            self.s.volume = max(0.0, min(1.0, v))

    def close(self):
        if self.s:
            self.s.stop()


class Voice:
    """Ένα ισοκράτημα που ηχεί, με τη δική του καμπύλη έντασης."""

    def __init__(self, key, track):
        self.key = key
        self.track = track
        self.level = 0.0
        self.target = 0.0
        self.rate = 1.0       # μονάδες έντασης ανά δευτερόλεπτο
        self.dying = False


class Engine:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.mem = {}
        self.voices = []
        self.master = 0.8
        self.attack = 0.6
        self.release = 1.2
        self.queue = collections.deque()
        self.pending = {}
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.wanted = []
        self.play_time = 0.0
        self._trim_cache()
        threading.Thread(target=self._worker, daemon=True).start()
        Clock.schedule_interval(self._tick, 1 / 40)

    def _trim_cache(self, keep=300):
        try:
            files = sorted((os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir)),
                           key=os.path.getmtime)
            for f in files[:-keep]:
                os.remove(f)
        except OSError:
            pass

    # ---------------------------------------------------------- απόδοση ήχου (σε νήμα)
    @staticmethod
    def key_for(freq, vowel, chorus):
        return f"{freq:.3f}|{vowel}|{int(chorus)}"

    def _path(self, key):
        h = hashlib.md5(key.encode("utf-8")).hexdigest()[:16]
        return os.path.join(self.cache_dir, h)

    def _load_or_render(self, key):
        if key in self.mem:
            return self.mem[key]
        p = self._path(key) + ".pc2"
        data = None
        try:
            with open(p, "rb") as f:
                raw = f.read()
            if raw[:4] == b"ISO2":
                n = struct.unpack("<I", raw[4:8])[0]
                data = (raw[8:8 + n], raw[8 + n:])
        except OSError:
            data = None
        if data is None:
            freq, vowel, chorus = key.split("|")
            data = synth.render_full(float(freq), vowel, chorus == "1")
            try:
                with open(p, "wb") as f:
                    f.write(b"ISO2" + struct.pack("<I", len(data[0])) + data[0] + data[1])
            except OSError:
                pass
        self.mem[key] = data
        if len(self.mem) > 30:
            self.mem.pop(next(iter(self.mem)))
        return data

    def _worker(self):
        while True:
            self.wake.wait()
            while True:
                with self.lock:
                    if not self.queue:
                        self.wake.clear()
                        break
                    key = self.queue.popleft()
                    cbs = self.pending.pop(key, [])
                try:
                    pcm = self._load_or_render(key)
                except Exception:  # noqa: BLE001
                    pcm = None
                for cb in cbs:
                    Clock.schedule_once(lambda dt, c=cb, k=key, d=pcm: c(k, d))

    def request(self, key, callback=None, urgent=True):
        with self.lock:
            if key in self.mem and callback:
                Clock.schedule_once(lambda dt: callback(key, self.mem[key]))
                return
            if key in self.pending:
                if callback:
                    self.pending[key].append(callback)
                if urgent and key in self.queue:
                    self.queue.remove(key)
                    self.queue.appendleft(key)
            else:
                self.pending[key] = [callback] if callback else []
                (self.queue.appendleft if urgent else self.queue.append)(key)
            self.wake.set()

    def prefetch(self, keys):
        for k in keys:
            self.request(k, None, urgent=False)

    # ---------------------------------------------------------- αναπαραγωγή
    def _make_track(self, key, pcm):
        if IS_ANDROID:
            return _AndroidTrack(pcm)
        return _DesktopTrack(pcm, self._path(key) + ".wav")

    def play(self, keys):
        """Κάνει να ηχούν ακριβώς αυτά τα κλειδιά. Οι παλιές φωνές σβήνουν μόλις είναι
        έτοιμες οι νέες, ώστε να μην υπάρχει κενό σιωπής στη μετάβαση."""
        wanted = list(dict.fromkeys(keys))
        self.wanted = wanted
        self.play_time = time.time()
        alive = {v.key for v in self.voices if not v.dying}
        for k in wanted:
            if k in alive:
                continue
            for v in self.voices:      # ξανά-ζωντάνεμα φωνής που έσβηνε
                if v.key == k and v.dying:
                    v.dying = False
                    v.target = 1.0
                    v.rate = 1.0 / max(0.02, self.attack)
                    break
            else:
                self.request(k, self._ready)
        self._reconcile()

    def _reconcile(self, force=False):
        wanted = getattr(self, "wanted", [])
        alive = {v.key for v in self.voices if not v.dying}
        if force or not wanted or all(k in alive for k in wanted):
            for v in self.voices:
                if v.key not in wanted and not v.dying:
                    self._fade_out(v)

    def _ready(self, key, pcm):
        if pcm is None or key not in getattr(self, "wanted", []):
            return
        if any(v.key == key and not v.dying for v in self.voices):
            return
        try:
            tr = self._make_track(key, pcm)
        except Exception:  # noqa: BLE001
            return
        v = Voice(key, tr)
        v.target = 1.0
        v.rate = 1.0 / max(0.02, self.attack)
        self.voices.append(v)
        self._reconcile()

    def _fade_out(self, v):
        v.dying = True
        v.target = 0.0
        v.rate = 1.0 / max(0.02, self.release)

    def stop_all(self):
        self.wanted = []
        for v in self.voices:
            self._fade_out(v)

    def _tick(self, dt):
        if not self.voices:
            return
        if time.time() - getattr(self, "play_time", 0) > 5:
            self._reconcile(force=True)
        active = max(1, sum(1 for v in self.voices if not v.dying))
        per_voice = self.master / active ** 0.5
        keep = []
        for v in self.voices:
            step = v.rate * dt
            if v.level < v.target:
                v.level = min(v.target, v.level + step)
            elif v.level > v.target:
                v.level = max(v.target, v.level - step)
            # καμπύλη «ανάσας»: ομαλό ξεκίνημα και σβήσιμο
            curve = v.level * v.level * (3 - 2 * v.level)
            v.track.volume(curve * per_voice)
            if v.dying and v.level <= 0.0:
                v.track.close()
            else:
                keep.append(v)
        self.voices = keep

    # ---------------------------------------------------------- βοηθητικός ήχος (μετρονόμος)
    def play_aux(self, key, pcm_loop, volume):
        self.stop_aux()
        try:
            self.aux = self._make_track(key, (b"", pcm_loop))
            self.aux.volume(volume)
        except Exception:  # noqa: BLE001
            self.aux = None

    def aux_volume(self, v):
        if getattr(self, "aux", None):
            self.aux.volume(v)

    def stop_aux(self):
        if getattr(self, "aux", None):
            self.aux.close()
        self.aux = None

    def sounding(self):
        return [v.key for v in self.voices if not v.dying]
