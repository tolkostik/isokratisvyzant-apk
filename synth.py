"""
Συνθετική ανθρώπινη φωνή για ισοκράτημα (καθαρή Python).

Κάθε νότα: κυματομορφή ενός κύκλου από αρμονικές που φιλτράρονται με τις
συχνότητες συντονισμού (formants) του φωνήεντος. Πάνω της προστίθενται μικρό, ακανόνιστο
τρέμουλο (vibrato), αργή διακύμανση έντασης, θόρυβος αναπνοής και, προαιρετικά,
τρεις ελαφρά διαφορετικές φωνές (χορωδία). Το αποτέλεσμα γίνεται βρόχος χωρίς ραφή.
"""
import array
import math
import random

SR = 16000          # Hz, αρκετό για ανδρική φωνή ισοκρατήματος
LOOP_SEC = 3.2
XFADE_SEC = 0.6
TABLE = 2048

VOWELS = {
    "Ο (στρογγυλό)": [(500, 90, 1.0), (850, 110, 0.45), (2400, 180, 0.12), (3300, 250, 0.05)],
    "Α (ανοιχτό)": [(730, 100, 1.0), (1090, 120, 0.55), (2440, 180, 0.25), (3400, 250, 0.08)],
    "Ου (κλειστό)": [(320, 70, 1.0), (800, 100, 0.28), (2240, 170, 0.07), (3200, 250, 0.03)],
    "Μμ (σιγοψάλσιμο)": [(250, 60, 1.0), (1050, 220, 0.05), (2200, 260, 0.02), (3000, 300, 0.01)],
}
DEFAULT_VOWEL = "Ο (στρογγυλό)"


def wavetable(f0, vowel):
    formants = VOWELS.get(vowel, VOWELS[DEFAULT_VOWEL])
    kmax = max(1, int(min(SR * 0.45, 5200) / f0))
    rnd = random.Random(int(f0 * 10))
    amps, phases = [], []
    for k in range(1, kmax + 1):
        fk = k * f0
        env = 0.0
        for F, B, g in formants:
            x = (fk - F) / (B / 2)
            env += g / (1 + x * x)
        a = (env + 0.015) * k ** -0.6       # κλίση φάσματος φωνητικών χορδών
        amps.append(a)
        phases.append(rnd.random() * 2 * math.pi)
    tab = [0.0] * TABLE
    w = 2 * math.pi / TABLE
    for k, (a, ph) in enumerate(zip(amps, phases), 1):
        if a < 1e-4:
            continue
        for i in range(TABLE):
            tab[i] += a * math.sin(k * w * i + ph)
    peak = max(abs(x) for x in tab) or 1.0
    return [x / peak for x in tab]


def render(f0, vowel=DEFAULT_VOWEL, chorus=True, seed=1):
    """Επιστρέφει bytes PCM 16-bit mono, βρόχος χωρίς ραφή."""
    rnd = random.Random(seed + int(f0 * 100))
    tab = wavetable(f0, vowel)
    loop_n = int(LOOP_SEC * SR)
    xf = int(XFADE_SEC * SR)
    n = loop_n + xf
    voices = [(0.0, 1.0)] if not chorus else [(0.0, 1.0), (4.0, 0.7), (-5.0, 0.7)]
    out = [0.0] * n
    block = 32
    for detune_cents, gain in voices:
        base = f0 * 2 ** (detune_cents / 1200)
        inc0 = base * TABLE / SR
        vib_rate = rnd.uniform(4.6, 5.6)
        vib_depth = rnd.uniform(0.0010, 0.0018)     # ~2–3 cents
        drift_rate = rnd.uniform(0.07, 0.13)
        drift_depth = rnd.uniform(0.0006, 0.0012)
        amp_rate = rnd.uniform(0.18, 0.35)
        ph_v, ph_d, ph_a = rnd.random() * 6.28, rnd.random() * 6.28, rnd.random() * 6.28
        phase = rnd.random() * TABLE
        jitter = 0.0
        for start in range(0, n, block):
            t = start / SR
            jitter = 0.98 * jitter + 0.02 * rnd.uniform(-1, 1)
            mod = (1 + vib_depth * math.sin(2 * math.pi * vib_rate * t + ph_v)
                   + drift_depth * math.sin(2 * math.pi * drift_rate * t + ph_d) + 0.0008 * jitter)
            inc = inc0 * mod
            amp = gain * (1 + 0.04 * math.sin(2 * math.pi * amp_rate * t + ph_a))
            end = min(n, start + block)
            for i in range(start, end):
                ip = int(phase)
                frac = phase - ip
                a = tab[ip & (TABLE - 1)]
                b = tab[(ip + 1) & (TABLE - 1)]
                out[i] += amp * (a + (b - a) * frac)
                phase += inc
                if phase >= TABLE:
                    phase -= TABLE
    # αναπνοή: χαμηλοπερατός θόρυβος, διαμορφωμένος από την κυματομορφή
    lp = 0.0
    breath = 0.035 * (len(voices) ** 0.5)
    for i in range(n):
        lp += 0.12 * (rnd.uniform(-1, 1) - lp)
        out[i] += breath * lp * (0.6 + 0.4 * abs(out[i]) / (len(voices)))
    # βρόχος χωρίς ραφή: το τέλος περνά ομαλά στην αρχή
    y = out[:loop_n]
    for i in range(xf):
        w = i / xf
        y[i] = out[i] * w + out[loop_n + i] * (1 - w)
    peak = max(abs(v) for v in y) or 1.0
    scale = 0.55 * 32767 / peak
    pcm = array.array("h", (int(v * scale) for v in y))
    return pcm.tobytes()


def to_wav(pcm, path):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)


# ------------------------------------------------------------------ πραγματική φωνή (ηχογράφηση)
import json  # noqa: E402
import os  # noqa: E402

MY_VOICE = "Η φωνή μου"
SAMPLE_DIR = None


def set_sample_dir(path):
    global SAMPLE_DIR
    SAMPLE_DIR = path
    os.makedirs(path, exist_ok=True)


def _meta_path():
    return os.path.join(SAMPLE_DIR, "samples.json")


def samples():
    try:
        with open(_meta_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return []


def samples_version():
    return "-".join(str(s["id"]) for s in samples()) or "0"


def voice_names():
    names = list(VOWELS)
    if samples():
        names.insert(0, MY_VOICE)
    return names


def _rms(seg):
    return (sum(v * v for v in seg) / max(1, len(seg))) ** 0.5


def make_sample(pcm_bytes, pitches, sr=SR):
    """Από ηχογράφηση φτιάχνει βρόχο φωνής. pitches: συχνότητες που μέτρησε το κουρδιστήρι.
    Επιστρέφει (id, συχνότητα) ή σηκώνει ValueError με εξήγηση."""
    a = array.array("h")
    a.frombytes(pcm_bytes[: len(pcm_bytes) // 2 * 2])
    x = [v / 32768 for v in a]
    if len(x) < sr * 2:
        raise ValueError("Πολύ σύντομη ηχογράφηση.")
    good = sorted(p for p in pitches if 55 < p < 600)
    if len(good) < 8:
        raise ValueError("Δεν ακούστηκε σταθερή φωνή. Ψάλε πιο δυνατά και σταθερά ένα φωνήεν.")
    med = good[len(good) // 2]
    near = [p for p in good if abs(p / med - 1) < 0.03]
    if len(near) < 0.6 * len(good):
        raise ValueError("Ο τόνος άλλαζε πολύ. Κράτα μία σταθερή νότα.")
    f0 = sum(near) / len(near)
    # το πιο σταθερό κομμάτι: ~2,6 s με την πιο ομοιόμορφη ένταση
    win = int(0.2 * sr)
    levels = [_rms(x[i:i + win]) for i in range(0, len(x) - win, win)]
    need = int(2.6 * sr) // win
    if len(levels) < need:
        need = len(levels)
    best, best_i = None, 0
    for i in range(0, len(levels) - need + 1):
        seg = levels[i:i + need]
        mean = sum(seg) / len(seg)
        if mean < 0.02:
            continue
        var = sum((l - mean) ** 2 for l in seg) / len(seg)
        score = var / (mean * mean)
        if best is None or score < best:
            best, best_i = score, i
    if best is None:
        raise ValueError("Η φωνή ήταν πολύ σιγανή. Πλησίασε το κινητό.")
    seg = x[best_i * win: best_i * win + need * win]
    xf = int(0.35 * sr)
    loop_n = len(seg) - xf
    y = seg[:loop_n]
    for i in range(xf):
        w = i / xf
        y[i] = seg[i] * w + seg[loop_n + i] * (1 - w)
    peak = max(abs(v) for v in y) or 1.0
    out = array.array("h", (int(v / peak * 0.9 * 32767) for v in y))
    sid = int(__import__("time").time())
    with open(os.path.join(SAMPLE_DIR, f"{sid}.pcm"), "wb") as f:
        f.write(out.tobytes())
    meta = samples()
    meta.append({"id": sid, "f0": round(f0, 2)})
    meta = sorted(meta, key=lambda s: s["f0"])[-3:] if len(meta) > 3 else meta
    with open(_meta_path(), "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return sid, f0


def delete_sample(sid):
    meta = [s for s in samples() if s["id"] != sid]
    with open(_meta_path(), "w", encoding="utf-8") as f:
        json.dump(meta, f)
    try:
        os.remove(os.path.join(SAMPLE_DIR, f"{sid}.pcm"))
    except OSError:
        pass


def render_recorded(f0, chorus=True):
    import math as _m
    meta = samples()
    if not meta:
        return render(f0, DEFAULT_VOWEL, chorus)
    s = min(meta, key=lambda m: abs(_m.log(f0 / m["f0"])))      # η πιο κοντινή ηχογράφηση
    a = array.array("h")
    with open(os.path.join(SAMPLE_DIR, f"{s['id']}.pcm"), "rb") as fh:
        a.frombytes(fh.read())
    src = [v / 32768 for v in a]
    n_src = len(src)
    ratio = f0 / s["f0"]
    loop_n = int(LOOP_SEC * SR)
    xf = int(XFADE_SEC * SR)
    n = loop_n + xf
    voices = [(1.0, 1.0, 0.0)] if not chorus else [(1.0, 1.0, 0.0), (1.0023, 0.6, 0.37), (0.9977, 0.6, 0.71)]
    out = [0.0] * n
    for det, gain, off in voices:
        step = ratio * det
        pos = off * n_src
        for i in range(n):
            ip = int(pos)
            fr = pos - ip
            a0 = src[ip % n_src]
            a1 = src[(ip + 1) % n_src]
            out[i] += gain * (a0 + (a1 - a0) * fr)
            pos += step
            if pos >= n_src:
                pos -= n_src
    y = out[:loop_n]
    for i in range(xf):
        w = i / xf
        y[i] = out[i] * w + out[loop_n + i] * (1 - w)
    peak = max(abs(v) for v in y) or 1.0
    scale = 0.55 * 32767 / peak
    return array.array("h", (int(v * scale) for v in y)).tobytes()


def render_any(f0, voice, chorus=True):
    if voice.startswith(MY_VOICE):
        return render_recorded(f0, chorus)
    return render(f0, voice, chorus)


# ------------------------------------------------------------------ φυσικό ξεκίνημα + ακουστική ναού
INTRO_SEC = 0.6          # παίζει μία φορά στην αρχή (ανάσα, μικρό «γλίστρημα» προς τον τόνο), μετά ο βρόχος
SCOOP_SEC = 0.16
SCOOP_CENTS = 28.0
REVERBS = {"Χωρίς αντήχηση": None, "Μικρό παρεκκλήσι": (1.2, 0.17), "Ενοριακός ναός": (2.3, 0.27),
           "Μεγάλος ναός": (3.6, 0.35)}
DEFAULT_REVERB = "Ενοριακός ναός"


def _scoop(i, scoop_n):
    if i >= scoop_n:
        return 1.0
    t = 1 - i / scoop_n
    return 2 ** (-SCOOP_CENTS * t * t / 1200)


def _synth_signal(f0, vowel, chorus, n, scoop_n, seed=1):
    rnd = random.Random(seed + int(f0 * 100))
    tab = wavetable(f0, vowel)
    voices = [(0.0, 1.0)] if not chorus else [(0.0, 1.0), (4.0, 0.7), (-5.0, 0.7)]
    out = [0.0] * n
    block = 32
    for vi, (detune_cents, gain) in enumerate(voices):
        base = f0 * 2 ** (detune_cents / 1200)
        inc0 = base * TABLE / SR
        vib_rate = rnd.uniform(4.6, 5.6)
        vib_depth = rnd.uniform(0.0010, 0.0018)
        drift_rate = rnd.uniform(0.07, 0.13)
        drift_depth = rnd.uniform(0.0006, 0.0012)
        amp_rate = rnd.uniform(0.18, 0.35)
        ph_v, ph_d, ph_a = rnd.random() * 6.28, rnd.random() * 6.28, rnd.random() * 6.28
        phase = rnd.random() * TABLE
        jitter = 0.0
        vd = vib_depth
        own_scoop = int(scoop_n * (1 + 0.25 * vi))        # οι φωνές της χορωδίας δεν «μπαίνουν» ακριβώς μαζί
        for start in range(0, n, block):
            t = start / SR
            jitter = 0.98 * jitter + 0.02 * rnd.uniform(-1, 1)
            vd = min(vib_depth * 1.6, max(vib_depth * 0.4, vd + rnd.uniform(-1, 1) * vib_depth * 0.03))
            mod = (1 + vd * math.sin(2 * math.pi * vib_rate * t + ph_v)
                   + drift_depth * math.sin(2 * math.pi * drift_rate * t + ph_d) + 0.0008 * jitter)
            inc = inc0 * mod * _scoop(start, own_scoop)
            amp = gain * (1 + 0.04 * math.sin(2 * math.pi * amp_rate * t + ph_a))
            end = min(n, start + block)
            for i in range(start, end):
                ip = int(phase)
                frac = phase - ip
                a = tab[ip & (TABLE - 1)]
                b = tab[(ip + 1) & (TABLE - 1)]
                out[i] += amp * (a + (b - a) * frac)
                phase += inc
                if phase >= TABLE:
                    phase -= TABLE
    lp = 0.0
    breath = 0.035 * (len(voices) ** 0.5)
    onset = int(0.3 * SR)
    for i in range(n):
        lp += 0.12 * (rnd.uniform(-1, 1) - lp)
        b = breath * (1 + 2.0 * max(0.0, 1 - i / onset))          # λίγη περισσότερη ανάσα στο ξεκίνημα
        out[i] += b * lp * (0.6 + 0.4 * abs(out[i]) / len(voices))
    return out


def _recorded_signal(f0, chorus, n, scoop_n):
    import math as _m
    meta = samples()
    s = min(meta, key=lambda m: abs(_m.log(f0 / m["f0"])))
    a = array.array("h")
    with open(os.path.join(SAMPLE_DIR, f"{s['id']}.pcm"), "rb") as fh:
        a.frombytes(fh.read())
    src = [v / 32768 for v in a]
    n_src = len(src)
    ratio = f0 / s["f0"]
    voices = [(1.0, 1.0, 0.0)] if not chorus else [(1.0, 1.0, 0.0), (1.0023, 0.6, 0.37), (0.9977, 0.6, 0.71)]
    out = [0.0] * n
    for vi, (det, gain, off) in enumerate(voices):
        pos = off * n_src
        own_scoop = int(scoop_n * (1 + 0.25 * vi))
        for i in range(n):
            ip = int(pos)
            fr = pos - ip
            a0 = src[ip % n_src]
            a1 = src[(ip + 1) % n_src]
            out[i] += gain * (a0 + (a1 - a0) * fr)
            pos += ratio * det * (_scoop(i, own_scoop) if i < own_scoop else 1.0)
            if pos >= n_src:
                pos -= n_src
    return out


def reverb(x, preset):
    """Αντήχηση τύπου Schroeder (4 χτένες με απόσβεση + 2 allpass). Επιστρέφει μόνο το «υγρό» σήμα."""
    rt60, _mix = preset
    combs = [int(SR * d) for d in (0.0297, 0.0371, 0.0411, 0.0437)]
    n = len(x)
    wet = [0.0] * n
    damp = 0.28
    for d in combs:
        g = 10 ** (-3 * (d / SR) / rt60)
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
            wet[i] += y
    for d, g in ((int(SR * 0.005), 0.7), (int(SR * 0.0017), 0.7)):
        buf = [0.0] * d
        idx = 0
        for i in range(n):
            bo = buf[idx]
            xin = wet[i]
            v = xin + g * bo           # allpass: v[n] = x[n] + g·v[n-d],  y[n] = v[n-d] − g·v[n]
            buf[idx] = v
            wet[i] = bo - g * v
            idx += 1
            if idx == d:
                idx = 0
    return [w * 0.25 for w in wet]


def parse_voice(spec):
    """«φωνή@ακουστική» → (φωνή, ακουστική)."""
    if "@" in spec:
        v, r = spec.split("@", 1)
        return v, r
    return spec, "Χωρίς αντήχηση"


def render_full(f0, spec, chorus=True):
    """Νέα επαγγελματική μηχανή (voice_pro): PSOLA, τράπεζες φωνών, ακουστική βυζαντινού ναού."""
    import voice_pro
    return voice_pro.render(f0, spec, chorus)


def render_full_v1(f0, spec, chorus=True):
    """Επιστρέφει (εισαγωγή, βρόχος) σε bytes PCM 16-bit. Η εισαγωγή παίζει μία φορά και συνεχίζει ομαλά στον βρόχο."""
    voice, room = parse_voice(spec)
    P = int(INTRO_SEC * SR)
    loop_n = int(LOOP_SEC * SR)
    xf = int(XFADE_SEC * SR)
    total = P + loop_n
    scoop_n = int(SCOOP_SEC * SR)
    if voice.startswith(MY_VOICE) and samples():
        out = _recorded_signal(f0, chorus, total, scoop_n)
    else:
        if voice.startswith(MY_VOICE):
            voice = DEFAULT_VOWEL
        out = _synth_signal(f0, voice, chorus, total, scoop_n)
    intro = out[:P]
    loop = out[P:P + loop_n]
    # το τέλος του βρόχου «λιώνει» σε ό,τι προηγείται της αρχής του → συνέχεια και στο πέρασμα εισαγωγή→βρόχος
    for i in range(xf):
        w = i / xf
        loop[loop_n - xf + i] = out[P + loop_n - xf + i] * (1 - w) + out[P - xf + i] * w
    preset = REVERBS.get(room)
    if preset:
        seq = intro + loop + loop
        wet = reverb(seq, preset)
        mix = preset[1]
        intro = [d * (1 - mix * 0.5) + mix * w for d, w in zip(intro, wet[:P])]
        loop = [d * (1 - mix * 0.5) + mix * w for d, w in zip(loop, wet[P + loop_n:P + 2 * loop_n])]
    peak = max(max((abs(v) for v in intro), default=0), max(abs(v) for v in loop)) or 1.0
    scale = 0.55 * 32767 / peak
    return (array.array("h", (int(v * scale) for v in intro)).tobytes(),
            array.array("h", (int(v * scale) for v in loop)).tobytes())
