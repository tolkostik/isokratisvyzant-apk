"""
Επαγγελματική μηχανή φωνής του Ισοκράτη.

  • Τράπεζες φωνών από πραγματικές ηχογραφήσεις (μικρόφωνο ή αρχείο WAV).
  • PSOLA: αλλαγή τονικού ύψους που ΚΡΑΤΑ τη χροιά (οι συχνότητες συντονισμού της φωνής δεν μετακινούνται),
    ώστε μία ηχογράφηση να ακούγεται φυσική σε όλους τους φθόγγους.
  • Συνθετική φωνή v2 (όταν δεν υπάρχει ηχογράφηση): φωνήεν «Νε», ανάσες χορωδίας σε διαφορετικές στιγμές.
  • Ακουστική βυζαντινού ναού: πρώτες ανακλάσεις + πυκνή αντήχηση με «σκούρο» χρώμα.
"""
import array
import json
import math
import os
import random
import time
import wave

import synth as S

SR = S.SR
LOOP_SEC = 6.0           # μεγαλύτερος βρόχος: δεν ακούγεται η επανάληψη
XFADE_SEC = 0.8
INTRO_SEC = 0.6
BANK_PREFIX = "Φωνή: "

ROOMS = {
    "Χωρίς αντήχηση": None,
    # (RT60 σε s, ποσοστό αντήχησης, απόσβεση ψηλών, πρώτες ανακλάσεις σε ms)
    "Μικρό παρεκκλήσι": (1.1, 0.16, 0.25, (5, 9, 13, 18)),
    "Ενοριακός ναός": (2.4, 0.26, 0.32, (9, 15, 23, 31, 40)),
    "Μονή – καθολικό": (3.3, 0.31, 0.38, (11, 19, 28, 37, 49, 61)),
    "Μεγάλος βυζαντινός ναός (τρούλος)": (5.0, 0.38, 0.45, (15, 26, 38, 52, 67, 85, 104)),
}
DEFAULT_ROOM = "Ενοριακός ναός"

VOWELS_V2 = {
    "Νε (ε)": [(530, 80, 1.0), (1840, 120, 0.45), (2480, 160, 0.3), (3350, 250, 0.08)],
    "Ο (στρογγυλό)": [(500, 80, 1.0), (850, 100, 0.45), (2400, 170, 0.12), (3300, 250, 0.05)],
    "Α (ανοιχτό)": [(730, 90, 1.0), (1090, 110, 0.55), (2440, 170, 0.25), (3400, 250, 0.08)],
    "Ου (κλειστό)": [(320, 60, 1.0), (800, 90, 0.28), (2240, 160, 0.07), (3200, 250, 0.03)],
    "Μμ (σιγοψάλσιμο)": [(250, 55, 1.0), (1050, 200, 0.05), (2200, 250, 0.02), (3000, 300, 0.01)],
}
DEFAULT_VOWEL = "Νε (ε)"


# ================================================================== τράπεζες φωνών
def _meta():
    try:
        with open(os.path.join(S.SAMPLE_DIR, "samples.json"), encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001
        data = []
    for d in data:
        d.setdefault("bank", "Η φωνή μου")
    return data


def _save_meta(data):
    with open(os.path.join(S.SAMPLE_DIR, "samples.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def banks():
    out = []
    for d in _meta():
        if d["bank"] not in out:
            out.append(d["bank"])
    return out


def bank_samples(bank):
    return sorted([d for d in _meta() if d["bank"] == bank], key=lambda d: d["f0"])


def bank_version(bank):
    return "-".join(str(d["id"]) for d in bank_samples(bank)) or "0"


def voice_names():
    return [BANK_PREFIX + b for b in banks()] + list(VOWELS_V2)


def clean_bank(name):
    name = "".join(ch for ch in (name or "").strip() if ch not in "|@#\n")[:30]
    return name or "Η φωνή μου"


def add_sample(pcm_bytes, pitches, bank):
    """Νέα ηχογράφηση σε τράπεζα. Χρησιμοποιεί τον έλεγχο ποιότητας του synth.make_sample."""
    before = _meta()
    sid, f0 = S.make_sample(pcm_bytes, pitches)
    # το synth.make_sample κρατά μόνο 3 συνολικά: ξαναχτίζουμε τα μεταδεδομένα με όλες τις τράπεζες
    new = [d for d in before if d["id"] != sid]
    new.append({"id": sid, "f0": round(f0, 2), "bank": clean_bank(bank)})
    same = sorted([d for d in new if d["bank"] == clean_bank(bank)], key=lambda d: d["f0"])
    if len(same) > 4:                               # έως 4 ανά τράπεζα
        drop = same[0] if abs(same[0]["f0"] - f0) > abs(same[-1]["f0"] - f0) else same[-1]
        new = [d for d in new if d["id"] != drop["id"]]
    _save_meta(new[-16:])
    return sid, f0


def delete_bank(bank):
    for d in bank_samples(bank):
        try:
            os.remove(os.path.join(S.SAMPLE_DIR, f"{d['id']}.pcm"))
        except OSError:
            pass
    _save_meta([d for d in _meta() if d["bank"] != bank])


def delete_one(sid):
    try:
        os.remove(os.path.join(S.SAMPLE_DIR, f"{sid}.pcm"))
    except OSError:
        pass
    _save_meta([d for d in _meta() if d["id"] != sid])


# ================================================================== εισαγωγή WAV & ανίχνευση τόνου
def read_wav_mono16k(path):
    with wave.open(path, "rb") as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if sw != 2:
            raise ValueError("Υποστηρίζονται αρχεία WAV 16-bit (το πιο συνηθισμένο).")
        raw = w.readframes(min(n, rate * 60))
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if ch > 1:
        a = array.array("h", (int(sum(a[i:i + ch]) / ch) for i in range(0, len(a) - ch + 1, ch)))
    if rate != SR:
        ratio = rate / SR
        n_out = int(len(a) / ratio)
        a = array.array("h", (a[min(len(a) - 1, int(i * ratio))] for i in range(n_out)))
    return a.tobytes()


def estimate_pitches(pcm_bytes):
    """Συχνότητες ανά τμήμα (αυτοσυσχέτιση σε 8 kHz). Για εισαγόμενα αρχεία, χωρίς μικρόφωνο."""
    a = array.array("h")
    a.frombytes(pcm_bytes[: len(pcm_bytes) // 2 * 2])
    x = [a[i] / 32768 for i in range(0, len(a), 2)]          # 8 kHz
    sr = SR // 2
    out = []
    frame = 1024
    lo, hi = sr // 450, sr // 60
    step = max(frame, len(x) // 30)
    for start in range(0, len(x) - frame - hi, step):
        seg = x[start:start + frame + hi]
        e = sum(v * v for v in seg[:frame])
        if e / frame < 1e-4:
            continue
        best, best_lag = 0.0, 0
        for lag in range(lo, hi):
            c = 0.0
            for i in range(0, frame, 2):
                c += seg[i] * seg[i + lag]
            if c > best:
                best, best_lag = c, lag
        if best_lag and best > 0.3 * (e / 2):
            # μικρή διόρθωση οκτάβας: αν και το μισό lag ταιριάζει πολύ, προτιμάμε το μισό
            half = best_lag // 2
            if half >= lo:
                c2 = sum(seg[i] * seg[i + half] for i in range(0, frame, 2))
                if c2 > 0.85 * best:
                    best_lag = half
            out.append(sr / best_lag)
    return out


# ================================================================== PSOLA
def _marks(src, period):
    """Σημεία κορυφών ανά περίοδο (για ανάκληση κόκκων σε φάση)."""
    n = len(src)
    P = int(period)
    first = max(range(min(P, n)), key=lambda i: src[i])
    marks = [first]
    pos = first
    w = max(2, int(P * 0.15))
    while pos + P + w < n:
        guess = pos + P
        lo, hi = guess - w, guess + w
        best = max(range(lo, hi), key=lambda i: src[i])
        marks.append(best)
        pos = best
    return marks


def psola(src, f_src, f_out, n_out, offset=0.0):
    """Επιστρέφει n_out δείγματα με τόνο f_out, κρατώντας τη χροιά της ηχογράφησης."""
    P = SR / f_src
    Pi = int(round(P))
    marks = _marks(src, P)
    n_src = len(src)
    if len(marks) < 4:
        return [0.0] * n_out
    win = [0.5 - 0.5 * math.cos(2 * math.pi * i / (2 * Pi)) for i in range(2 * Pi)]
    out = [0.0] * (n_out + 2 * Pi)
    Po = SR / f_out
    t = 0.0
    span = marks[-1] - marks[0]
    k = 0
    start = offset * span
    while t < n_out:
        # χρόνος στην πηγή (ίδια διάρκεια, κυκλικά) → πλησιέστερο σημείο
        st = marks[0] + (start + t) % span
        while k + 1 < len(marks) and marks[k + 1] <= st:
            k += 1
        while k > 0 and marks[k] > st:
            k -= 1
        m = marks[k] if (k + 1 >= len(marks) or st - marks[k] <= marks[k + 1] - st) else marks[k + 1]
        base = int(t) - Pi
        for i in range(2 * Pi):
            j = base + i
            if 0 <= j < len(out):
                out[j] += src[(m - Pi + i) % n_src] * win[i]
        t += Po
    return out[:n_out]


def _bank_signal(bank, f0, chorus, n):
    smp = bank_samples(bank)
    if not smp:
        return None
    s = min(smp, key=lambda d: abs(math.log(f0 / d["f0"])))
    a = array.array("h")
    with open(os.path.join(S.SAMPLE_DIR, f"{s['id']}.pcm"), "rb") as fh:
        a.frombytes(fh.read())
    src = [v / 32768 for v in a]
    rnd = random.Random(int(f0 * 10))
    voices = [(1.0, 1.0, 0.0)] if not chorus else [(1.0, 1.0, 0.0), (1.0025, 0.65, 0.31), (0.9978, 0.65, 0.67)]
    out = [0.0] * n
    for vi, (det, gain, off) in enumerate(voices):
        sig = psola(src, s["f0"], f0 * det, n, off)
        dips = _breath_dips(n, rnd) if vi > 0 else []
        for i in range(n):
            out[i] += gain * sig[i] * _dip_gain(i, dips)
    return out


# ================================================================== συνθετική φωνή v2
def _breath_dips(n, rnd):
    """Μία-δύο ανάσες μέσα στον βρόχο (σε διαφορετική στιγμή για κάθε φωνή της χορωδίας)."""
    dips = []
    for _ in range(rnd.choice((1, 1, 2))):
        c = rnd.uniform(0.15, 0.85) * n
        dips.append((c, rnd.uniform(0.35, 0.6) * SR))
    return dips


def _dip_gain(i, dips):
    g = 1.0
    for c, w in dips:
        d = abs(i - c)
        if d < w:
            g = min(g, 0.25 + 0.75 * (d / w) ** 2)
    return g


def _wavetable_v2(f0, vowel, shift=1.0):
    formants = VOWELS_V2.get(vowel, VOWELS_V2[DEFAULT_VOWEL])
    kmax = max(1, int(min(SR * 0.45, 5200) / f0))
    rnd = random.Random(int(f0 * 10) + int(shift * 1000))
    table = S.TABLE
    tab = [0.0] * table
    w = 2 * math.pi / table
    for k in range(1, kmax + 1):
        fk = k * f0
        env = 0.0
        for F, B, g in formants:
            x = (fk - F * shift) / (B / 2)
            env += g / (1 + x * x)
        a = (env + 0.012) * k ** -0.75
        if a < 1e-4:
            continue
        ph = rnd.random() * 2 * math.pi
        for i in range(table):
            tab[i] += a * math.sin(k * w * i + ph)
    peak = max(abs(v) for v in tab) or 1.0
    return [v / peak for v in tab]


def _synth_v2(f0, vowel, chorus, n, scoop_n):
    rnd = random.Random(int(f0 * 100) + 7)
    table = S.TABLE
    voices = [(0.0, 1.0, 1.0)] if not chorus else [(0.0, 1.0, 1.0), (5.0, 0.7, 1.04), (-6.0, 0.7, 0.96)]
    out = [0.0] * n
    for vi, (cents, gain, fshift) in enumerate(voices):
        tab = _wavetable_v2(f0, vowel, fshift)       # κάθε ψάλτης με λίγο διαφορετική χροιά
        inc0 = f0 * 2 ** (cents / 1200) * table / SR
        vib_rate = rnd.uniform(4.4, 5.4)
        vib_depth = rnd.uniform(0.0008, 0.0016)
        ph_v, ph_a = rnd.random() * 6.28, rnd.random() * 6.28
        phase = rnd.random() * table
        jit, shim = 0.0, 0.0
        dips = _breath_dips(n, rnd) if vi > 0 else []
        own = int(scoop_n * (1 + 0.3 * vi))
        for start in range(0, n, 32):
            t = start / SR
            jit = 0.97 * jit + 0.03 * rnd.uniform(-1, 1)
            shim = 0.95 * shim + 0.05 * rnd.uniform(-1, 1)
            mod = 1 + vib_depth * math.sin(2 * math.pi * vib_rate * t + ph_v) + 0.0012 * jit
            inc = inc0 * mod * S._scoop(start, own)
            amp = gain * (1 + 0.035 * math.sin(2 * math.pi * 0.23 * t + ph_a) + 0.03 * shim) * _dip_gain(start, dips)
            for i in range(start, min(n, start + 32)):
                ip = int(phase)
                fr = phase - ip
                a = tab[ip & (table - 1)]
                b = tab[(ip + 1) & (table - 1)]
                out[i] += amp * (a + (b - a) * fr)
                phase += inc
                if phase >= table:
                    phase -= table
    lp = 0.0
    for i in range(n):
        lp += 0.1 * (rnd.uniform(-1, 1) - lp)
        out[i] += 0.03 * lp * (1 + 2 * max(0.0, 1 - i / (0.3 * SR)))
    return out


# ================================================================== ακουστική ναού
def church_reverb(x, preset):
    rt60, _mix, damp, er = preset
    n = len(x)
    wet = [0.0] * n
    # πρώτες ανακλάσεις (τοίχοι, κίονες, τρούλος)
    for k, ms in enumerate(er):
        d = int(SR * ms / 1000)
        g = 0.55 * (0.82 ** k)
        for i in range(d, n):
            wet[i] += g * x[i - d]
    # πυκνή ουρά: 6 χτένες με απόσβεση ψηλών (ζεστό, «πέτρινο» χρώμα)
    tail = [0.0] * n
    for dsec in (0.0297, 0.0341, 0.0371, 0.0411, 0.0437, 0.0473):
        d = int(SR * dsec)
        g = 10 ** (-3 * dsec / rt60)
        buf = [0.0] * d
        idx = 0
        lp = 0.0
        for i in range(n):
            y = buf[idx]
            lp = y * (1 - damp) + lp * damp
            buf[idx] = x[i] + g * lp
            idx += 1
            if idx == d:
                idx = 0
            tail[i] += y
    for dsec, g in ((0.0050, 0.7), (0.0017, 0.7), (0.0011, 0.65)):
        d = max(1, int(SR * dsec))
        buf = [0.0] * d
        idx = 0
        for i in range(n):
            bo = buf[idx]
            v = tail[i] + g * bo
            buf[idx] = v
            tail[i] = bo - g * v
            idx += 1
            if idx == d:
                idx = 0
    for i in range(n):
        wet[i] = 0.35 * wet[i] + 0.16 * tail[i]
    return wet


# ================================================================== απόδοση
def render(f0, spec, chorus=True):
    """(εισαγωγή, βρόχος) σε PCM 16-bit. spec = «φωνή@αίθουσα»."""
    voice, room = S.parse_voice(spec)
    voice = voice.split("#")[0]
    P = int(INTRO_SEC * SR)
    loop_n = int(LOOP_SEC * SR)
    xf = int(XFADE_SEC * SR)
    total = P + loop_n
    scoop_n = int(S.SCOOP_SEC * SR)
    out = None
    if voice.startswith(BANK_PREFIX):
        out = _bank_signal(voice[len(BANK_PREFIX):], f0, chorus, total)
        if out is not None:
            # «ανάσα» στην αρχή και για την ηχογραφημένη φωνή
            for i in range(min(scoop_n, total)):
                out[i] *= 0.4 + 0.6 * (i / scoop_n)
    if out is None:
        if voice not in VOWELS_V2:
            voice = DEFAULT_VOWEL if not voice.startswith(BANK_PREFIX) else DEFAULT_VOWEL
        out = _synth_v2(f0, voice, chorus, total, scoop_n)
    intro = out[:P]
    loop = out[P:P + loop_n]
    for i in range(xf):
        w = i / xf
        loop[loop_n - xf + i] = out[P + loop_n - xf + i] * (1 - w) + out[P - xf + i] * w
    preset = ROOMS.get(room)
    if preset:
        wet = church_reverb(intro + loop + loop, preset)
        mix = preset[1]
        intro = [d * (1 - mix * 0.5) + mix * w for d, w in zip(intro, wet[:P])]
        loop = [d * (1 - mix * 0.5) + mix * w for d, w in zip(loop, wet[P + loop_n:P + 2 * loop_n])]
    peak = max(max((abs(v) for v in intro), default=0), max(abs(v) for v in loop)) or 1.0
    scale = 0.55 * 32767 / peak
    return (array.array("h", (int(v * scale) for v in intro)).tobytes(),
            array.array("h", (int(v * scale) for v in loop)).tobytes())


# ================================================================== μετρονόμος
def metronome_loop(bpm, beats):
    """Ένα μέτρο ως βρόχος: τονισμένο πρώτο χτύπημα, ήπια τα υπόλοιπα (ήχος σαν ξύλινο τάλαντο)."""
    beat_n = int(SR * 60 / max(30, bpm))
    n = beat_n * max(1, beats)
    out = [0.0] * n
    for b in range(max(1, beats)):
        f, amp = (1500, 0.9) if (b == 0 and beats > 1) else (1000, 0.55)
        for i in range(int(0.06 * SR)):
            t = i / SR
            env = math.exp(-t * 70)
            out[b * beat_n + i] += amp * env * (math.sin(2 * math.pi * f * t) + 0.4 * math.sin(2 * math.pi * f * 2.7 * t))
    return array.array("h", (int(max(-1, min(1, v)) * 26000) for v in out)).tobytes()


_ = time
