"""
Πρόσθετα του Ισοκράτη:
  • Προγράμματα ισοκρατημάτων ανά ύμνο (με εκτέλεση βήμα-βήμα και πεντάλ).
  • Εξάσκηση τονισμού (μετρά πόσο καθαρά ψάλλεις κάθε φθόγγο, σε μόρια).
  • Ηχογράφηση της ψαλμωδίας (ακρόαση και αποστολή).
"""
import datetime
import math
import os
import random
import threading
import time
import wave

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.utils import platform

import synth
import theory as T

IS_ANDROID = platform == "android"
SCALE_KEYS = ("genus", "mode", "semis", "moria", "alter", "attr", "attr_size", "tempered")
DRILL_MODES = ["Ένας φθόγγος", "Κλίμακα ανιούσα (Νη→Νη')", "Κλίμακα κατιούσα (Νη'→Νη)", "Τυχαίοι φθόγγοι (8)"]


def step_name(step):
    if not step:
        return "Σιωπή"
    return " + ".join(T.label(d) + ("" if o == 0 else (" χαμ." if o < 0 else " ψηλ.")) for d, o in step)


class ExtraMixin:
    # ================================================================== βοηθητικά
    def _box(self, sid):
        b = self.root_w.ids[sid]
        b.clear_widgets()
        return b

    def _f(self, name):
        from kivy.factory import Factory
        return getattr(Factory, name)

    def _txt(self, box, text, **kw):
        w = self._f("Txt")(text=text, **kw)
        box.add_widget(w)
        return w

    def _big(self, box, text, cb, accent=True, h=58, **kw):
        b = self._f("Flat")(text=text, size_hint_y=None, height=dp(h) * self.ui, bold=True, **kw)
        if accent:
            b.background_color = self.c_accent
            b.color = self.c_on_accent
        b.bind(on_release=lambda *a: cb())
        box.add_widget(b)
        return b

    # ================================================================== ύμνοι (προγράμματα)
    def show_hymns(self):
        box = self._box("hymns_box")
        self._txt(box, "[size=18sp][b]Ύμνοι[/b][/size]\nΕτοίμασε από πριν τη σειρά των ισοκρατημάτων ενός ύμνου. "
                       "Στην ακολουθία προχωράς βήμα-βήμα με το μεγάλο κουμπί ή με το πεντάλ.")
        self._big(box, "+ ΝΕΟ ΠΡΟΓΡΑΜΜΑ", lambda: self.edit_program(None))
        for i, pr in enumerate(self.cfg.get("programs", [])):
            card = self._txt(box, f"[b]{pr['name']}[/b]\n[size=13sp]{len(pr['steps'])} βήματα · "
                                  f"{pr.get('scale', {}).get('mode', '')} · {pr.get('scale', {}).get('genus', '')}"
                                  f"[/size]")
            card.color = self.c_text
            row = BoxLayout(size_hint_y=None, height=dp(50) * self.ui, spacing=dp(6))
            for label, cb in (("ΕΝΑΡΞΗ", lambda k=i: self.start_perform(k)),
                              ("Επεξεργασία", lambda k=i: self.edit_program(k)),
                              ("Διαγραφή", lambda k=i: self._del_program(k))):
                b = self._f("Flat")(text=label, bold=label == "ΕΝΑΡΞΗ")
                if label == "ΕΝΑΡΞΗ":
                    b.background_color = self.c_accent
                    b.color = self.c_on_accent
                b.bind(on_release=lambda w, c=cb: c())
                row.add_widget(b)
            box.add_widget(row)

    def _del_program(self, i):
        progs = list(self.cfg.get("programs", []))
        if 0 <= i < len(progs):
            progs.pop(i)
        self.cfg["programs"] = progs
        self.save()
        self.show_hymns()

    def edit_program(self, idx):
        progs = self.cfg.setdefault("programs", [])
        pr = progs[idx] if idx is not None else {"name": "", "steps": [], "scale": {}}
        self._ed = {"idx": idx, "name": pr["name"], "steps": [list(map(list, s)) for s in pr["steps"]],
                    "octave": 0, "double": False}
        if pr.get("scale"):
            self._apply_scale(pr["scale"])
        self._render_editor()

    def _render_editor(self):
        ed = self._ed
        box = self._box("hymns_box")
        self._txt(box, "[size=18sp][b]Πρόγραμμα ύμνου[/b][/size]\nΤο πρόγραμμα κρατά και τον τωρινό ήχο, γένος, βάση "
                       "και φθορές. Ρύθμισέ τα πρώτα στην καρτέλα «Ισοκράτης».")
        name = self._f("TextInput")(text=ed["name"], hint_text="Όνομα, π.χ. Δοξαστικό Εσπερινού Πλ. Α'",
                                    multiline=False, size_hint_y=None, height=dp(46) * self.ui)
        name.bind(text=lambda w, v: ed.__setitem__("name", v))
        box.add_widget(name)
        steps = "   ".join(f"{i + 1}. {step_name(s)}" for i, s in enumerate(ed["steps"])) or "(κανένα βήμα ακόμα)"
        self._txt(box, f"[b]Βήματα:[/b] {steps}")
        orow = BoxLayout(size_hint_y=None, height=dp(44) * self.ui, spacing=dp(4))
        for label, o in (("Χαμηλά", -1), ("Μέση", 0), ("Ψηλά", 1)):
            b = self._f("Seg")(text=label, group="ed_oct", allow_no_selection=False,
                                state="down" if ed["octave"] == o else "normal")
            b.bind(on_release=lambda w, oo=o: ed.__setitem__("octave", oo))
            orow.add_widget(b)
        dbl = self._f("Seg")(text="Διπλό", state="down" if ed["double"] else "normal")
        dbl.bind(state=lambda w, st: ed.__setitem__("double", st == "down"))
        orow.add_widget(dbl)
        box.add_widget(orow)
        from kivy.uix.gridlayout import GridLayout
        grid = GridLayout(cols=4, size_hint_y=None, height=dp(120) * self.ui, spacing=dp(6))
        for d in range(8):
            b = self._f("Flat")(text=T.label(d), font_size=f"{int(22 * self.ui)}sp", bold=True)
            b.color = self.c_accent
            b.bind(on_release=lambda w, dd=d: self._ed_add(dd))
            grid.add_widget(b)
        box.add_widget(grid)
        self._txt(box, "[size=12sp]Πάτα φθόγγο για νέο βήμα. Με «Διπλό» πατημένο, ο φθόγγος προστίθεται στο "
                       "τελευταίο βήμα (π.χ. Νη + Δι).[/size]")
        row = BoxLayout(size_hint_y=None, height=dp(48) * self.ui, spacing=dp(6))
        for label, cb in (("Σιωπή", lambda: (ed["steps"].append([]), self._render_editor())),
                          ("Ό,τι ηχεί τώρα", lambda: (ed["steps"].append([list(x) for x in self.active]),
                                                     self._render_editor()) if self.active else None),
                          ("Αφαίρεση τελευταίου", lambda: (ed["steps"].pop() if ed["steps"] else None,
                                                          self._render_editor()))):
            b = self._f("Flat")(text=label, font_size="13sp")
            b.bind(on_release=lambda w, c=cb: c())
            row.add_widget(b)
        box.add_widget(row)
        self._big(box, "ΑΠΟΘΗΚΕΥΣΗ", self._save_program)
        self._big(box, "Άκυρο", self.show_hymns, accent=False, h=46)

    def _ed_add(self, d):
        ed = self._ed
        item = [d, ed["octave"]]
        if ed["double"] and ed["steps"] and ed["steps"][-1] is not None and len(ed["steps"][-1]) < 4:
            if item not in ed["steps"][-1]:
                ed["steps"][-1].append(item)
        else:
            ed["steps"].append([item])
        self._render_editor()

    def _save_program(self):
        ed = self._ed
        if not ed["steps"]:
            return
        pr = {"name": ed["name"].strip() or f"Ύμνος {len(self.cfg.get('programs', [])) + 1}",
              "steps": ed["steps"], "scale": {k: self.cfg[k] for k in SCALE_KEYS}}
        progs = self.cfg.setdefault("programs", [])
        if ed["idx"] is None:
            progs.append(pr)
        else:
            progs[ed["idx"]] = pr
        self.save()
        self.show_hymns()

    def _apply_scale(self, sc):
        self._loading = True
        for k, v in sc.items():
            self.cfg[k] = v
        ids = self.root_w.ids
        ids.mode.text = self.cfg["mode"]
        ids.genus.text = self.cfg["genus"]
        for i, tb in enumerate(self.attr_btns):
            tb.state = "down" if self.cfg["attr"][i] else "normal"
        self._loading = False
        self.save()
        self.refresh()

    # ------------------------------------------------------------------ εκτέλεση στην ακολουθία
    def start_perform(self, i):
        pr = self.cfg["programs"][i]
        self._apply_scale(pr.get("scale", {}))
        self.perf = {"prog": pr, "pos": 0, "muted": False}
        self.engine.prefetch([self.key(d, o) for s in pr["steps"] for d, o in s])
        self.root_w.ids.sm.current = "perform"
        self._perform_play()

    def _perform_play(self):
        p = self.perf
        step = p["prog"]["steps"][p["pos"]]
        self.active = [tuple(x) for x in step]
        if p["muted"] or not step:
            self.engine.stop_all()
            self.active = [] if not step else self.active
        else:
            self.engine.play([self.key(d, o) for d, o in step])
        self.refresh()
        self._render_perform()

    def perform_step(self, delta):
        p = getattr(self, "perf", None)
        if not p:
            return
        n = len(p["prog"]["steps"])
        p["pos"] = max(0, min(n - 1, p["pos"] + delta))
        p["muted"] = False
        self._perform_play()

    def perform_toggle(self):
        p = getattr(self, "perf", None)
        if not p:
            return
        p["muted"] = not p["muted"]
        self._perform_play()

    def stop_perform(self):
        self.perf = None
        self.silence()
        self.go("hymns")

    def _render_perform(self):
        p = self.perf
        box = self._box("perform_box")
        steps = p["prog"]["steps"]
        cur = steps[p["pos"]]
        nxt = steps[p["pos"] + 1] if p["pos"] + 1 < len(steps) else None
        Factory_Label = Label
        box.add_widget(Factory_Label(text=p["prog"]["name"], color=self.c_dim, font_size=f"{int(15 * self.ui)}sp",
                                     size_hint_y=None, height=dp(30) * self.ui))
        box.add_widget(Factory_Label(text=f"{p['pos'] + 1} / {len(steps)}", color=self.c_dim,
                                     font_size=f"{int(18 * self.ui)}sp", size_hint_y=None, height=dp(34) * self.ui))
        big = step_name(cur) if not p["muted"] else f"({step_name(cur)}) σιωπή"
        box.add_widget(Factory_Label(text=big, bold=True, color=self.c_accent, font_size=f"{int(64 * self.ui)}sp",
                                     halign="center", valign="middle", text_size=(Window.width - dp(20), None)))
        box.add_widget(Factory_Label(text=f"Επόμενο: {step_name(nxt)}" if nxt is not None else "Τελευταίο βήμα",
                                     color=self.c_text, font_size=f"{int(20 * self.ui)}sp", size_hint_y=None,
                                     height=dp(44) * self.ui))
        row = BoxLayout(size_hint_y=None, height=dp(110) * self.ui, spacing=dp(8))
        prev = self._f("Flat")(text="<", font_size=f"{int(34 * self.ui)}sp", size_hint_x=0.3)
        prev.bind(on_release=lambda *a: self.perform_step(-1))
        nx = self._f("Flat")(text="ΕΠΟΜΕΝΟ >", bold=True, font_size=f"{int(28 * self.ui)}sp")
        nx.background_color = self.c_accent
        nx.color = self.c_on_accent
        nx.bind(on_release=lambda *a: self.perform_step(+1))
        row.add_widget(prev)
        row.add_widget(nx)
        box.add_widget(row)
        row2 = BoxLayout(size_hint_y=None, height=dp(56) * self.ui, spacing=dp(8))
        mute = self._f("Flat")(text="Συνέχεια" if p["muted"] else "Σιωπή (προσωρινά)")
        mute.bind(on_release=lambda *a: self.perform_toggle())
        end = self._f("Flat")(text="Τέλος")
        end.bind(on_release=lambda *a: self.stop_perform())
        row2.add_widget(mute)
        row2.add_widget(end)
        box.add_widget(row2)
        box.add_widget(Factory_Label(text="Πεντάλ: δεξί/Page Down = επόμενο · αριστερό/Page Up = προηγούμενο · "
                                          "Space = σιωπή/συνέχεια", color=self.c_dim, font_size="12sp",
                                     size_hint_y=None, height=dp(36), text_size=(Window.width - dp(20), None),
                                     halign="center"))

    # ================================================================== εξάσκηση (κεντρική)
    def show_practice(self):
        box = self._box("practice_box")
        self._txt(box, "[size=18sp][b]Εξάσκηση[/b][/size]")
        self._big(box, "ΚΟΥΡΔΙΣΤΗΡΙ", lambda: self.go("tuner"), h=70)
        self._txt(box, "Δες τον φθόγγο που ψάλλεις και ρύθμισε τη βάση του ισοκράτη στη φωνή σου.")
        self._big(box, "ΑΣΚΗΣΗ ΤΟΝΙΣΜΟΥ", lambda: self.go("drill"), h=70)
        self._txt(box, "Ψάλλε φθόγγους ή κλίμακες και δες πόσο καθαρά τους πετυχαίνεις, σε μόρια.")
        self._big(box, "ΗΧΟΓΡΑΦΗΣΗ ΨΑΛΜΩΔΙΑΣ", lambda: self.go("chantrec"), h=70)
        self._txt(box, "Ηχογράφησε τον εαυτό σου με τον ισοκράτη, άκουσε και στείλε το στον δάσκαλό σου.")
        self._big(box, "ΜΕΤΡΟΝΟΜΟΣ (ΧΡΟΝΟΙ)", lambda: self.go("metro"), h=70)
        self._txt(box, "Σταθερός ρυθμός για δίσημο, τρίσημο ή τετράσημο μέτρο, μαζί με τον ισοκράτη.")

    # ================================================================== άσκηση τονισμού
    def show_drill(self):
        self.drill = None
        box = self._box("drill_box")
        self._txt(box, "[size=18sp][b]Άσκηση τονισμού[/b][/size]\nΗ εφαρμογή ακούει και μετρά πόσα μόρια πάνω ή κάτω "
                       "ψάλλεις κάθε φθόγγο, στο γένος και τη βάση που έχεις ρυθμίσει. Χρησιμοποίησε ακουστικά ή "
                       "κράτα τον ισοκράτη σιωπηλό, για να ακούει μόνο τη φωνή σου.")
        row = BoxLayout(size_hint_y=None, height=dp(48) * self.ui, spacing=dp(6))
        mode = self._f("DarkSpinner")(text=DRILL_MODES[1], values=DRILL_MODES)
        deg = self._f("DarkSpinner")(text="Πα", values=T.NAMES + ["Νη'"], size_hint_x=0.35)
        row.add_widget(mode)
        row.add_widget(deg)
        box.add_widget(row)
        ref = self._f("Seg")(text="Άκουσε πρώτα κάθε φθόγγο", state="down")
        ref.size_hint_y = None
        ref.height = dp(46) * self.ui
        box.add_widget(ref)
        self._big(box, "ΕΝΑΡΞΗ", lambda: self.start_drill(mode.text, deg.text, ref.state == "down"), h=64)
        hist = self.cfg.get("drills", [])
        if hist:
            last = hist[-10:]
            bars = "\n".join(f"{h['date']}  {'|' * int(round(h['avg']))}  {h['avg']:.1f}".replace(".", ",")
                             for h in last)
            self._txt(box, "[b]Πρόοδος (τελευταίες ασκήσεις)[/b]\n" + bars)
            tend = {}
            for h in hist[-20:]:
                for name, dev in h.get("devs", {}).items():
                    tend.setdefault(name, []).append(dev)
            if tend:
                lines = []
                for name in T.NAMES + ["Νη'"]:
                    if name in tend:
                        m = sum(tend[name]) / len(tend[name])
                        if abs(m) >= 1:
                            lines.append(f"{name}: συνήθως {'ψηλά' if m > 0 else 'χαμηλά'} κατά "
                                         f"{abs(m):.1f} μόρια".replace(".", ","))
                if lines:
                    self._txt(box, "[b]Τάσεις σου[/b]\n" + "\n".join(lines))

    def start_drill(self, mode, deg_name, reference):
        if mode == DRILL_MODES[0]:
            targets = [T.NAMES.index(deg_name) if deg_name in T.NAMES else 7] * 3
        elif mode == DRILL_MODES[1]:
            targets = list(range(8))
        elif mode == DRILL_MODES[2]:
            targets = list(range(7, -1, -1))
        else:
            targets = [random.randint(0, 7) for _ in range(8)]
        self.silence()
        self.drill = {"targets": targets, "i": 0, "ref": reference, "state": "start", "t": time.time(),
                      "frames": [], "results": [], "mode": mode}

        def ok():
            self._drill_ev = Clock.schedule_interval(self._drill_tick, 0.1)
            self._drill_next()

        def fail(msg):
            box = self._box("drill_box")
            self._txt(box, msg)
            self._big(box, "Πίσω", self.show_drill)
        if not IS_ANDROID:
            fail("Η άσκηση λειτουργεί μόνο στο κινητό (χρειάζεται μικρόφωνο).")
            return
        self.mic.start(ok, fail)

    def _drill_target_freqs(self, d):
        return [self.freq(d, o) for o in (-2, -1, 0, 1)]

    def _drill_next(self):
        dr = self.drill
        if dr["i"] >= len(dr["targets"]):
            return self._drill_finish()
        d = dr["targets"][dr["i"]]
        dr["frames"] = []
        if dr["ref"]:
            dr["state"] = "ref"
            dr["t"] = time.time()
            self.engine.play([self.key(d, self.cur_octave())])
        else:
            dr["state"] = "listen"
            dr["t"] = time.time()
        self._render_drill()

    def _drill_tick(self, dt):
        dr = getattr(self, "drill", None)
        if not dr:
            return False
        now = time.time()
        if dr["state"] == "ref":
            if now - dr["t"] > 1.6:
                self.engine.stop_all()
                dr["state"] = "gap"
                dr["t"] = now
            return
        if dr["state"] == "gap":
            if now - dr["t"] > 0.8:
                dr["state"] = "listen"
                dr["t"] = now
                self._render_drill()
            return
        if dr["state"] == "result":
            if now - dr["t"] > 1.8:
                dr["i"] += 1
                self._drill_next()
            return
        if dr["state"] != "listen":
            return
        f = self.mic.pitch()
        d = dr["targets"][dr["i"]]
        if f > 0:
            dev = min((72 * math.log2(f / ft) for ft in self._drill_target_freqs(d)), key=abs)
            dr["frames"].append(dev)
            dr["frames"] = dr["frames"][-14:]
            if hasattr(self, "_drill_live"):
                self._drill_live.text = f"{dev:+.1f} μόρια".replace(".", ",")
            fr = dr["frames"]
            if len(fr) >= 12 and max(fr[-12:]) - min(fr[-12:]) < 4:
                med = sorted(fr[-12:])[6]
                self._drill_result(med)
        if now - dr["t"] > 12 and dr["state"] == "listen":
            self._drill_result(None)

    def _drill_result(self, dev):
        dr = self.drill
        d = dr["targets"][dr["i"]]
        score = 0.0 if dev is None else max(0.0, round(10 - 1.2 * abs(dev), 1))
        dr["results"].append((d, dev, score))
        dr["state"] = "result"
        dr["t"] = time.time()
        self._render_drill(last=(d, dev, score))

    def _render_drill(self, last=None):
        dr = self.drill
        box = self._box("drill_box")
        d = dr["targets"][min(dr["i"], len(dr["targets"]) - 1)]
        self._txt(box, f"[size=14sp]{dr['mode']} · {dr['i'] + 1}/{len(dr['targets'])}[/size]")
        msg = {"ref": "Άκου τον φθόγγο…", "gap": "Ετοιμάσου…", "listen": "Ψάλλε τώρα σταθερά",
               "result": "", "start": ""}[dr["state"]]
        box.add_widget(Label(text=T.label(d), bold=True, font_size=f"{int(80 * self.ui)}sp", color=self.c_accent,
                             size_hint_y=None, height=dp(130) * self.ui))
        self._txt(box, f"[size=18sp]{msg}[/size]")
        self._drill_live = Label(text="", font_size=f"{int(26 * self.ui)}sp", color=self.c_text, size_hint_y=None,
                                 height=dp(50) * self.ui)
        box.add_widget(self._drill_live)
        if last:
            dd, dev, score = last
            if dev is None:
                t = "[color=#B4461B]Δεν ακούστηκε σταθερή φωνή[/color]"
            else:
                col = "0F9B57" if abs(dev) <= 1 else ("C98A00" if abs(dev) <= 3 else "B4461B")
                word = "ακριβώς" if abs(dev) <= 1 else ("ψηλά" if dev > 0 else "χαμηλά")
                t = (f"[color=#{col}][b]{dev:+.1f} μόρια · {word}[/b][/color]  ·  βαθμός {score:.1f}/10"
                     .replace(".", ","))
            self._txt(box, f"[size=18sp]{t}[/size]")
        self._big(box, "Διακοπή", self._drill_stop, accent=False, h=48)

    def _drill_stop(self):
        ev = getattr(self, "_drill_ev", None)
        if ev:
            ev.cancel()
        self.engine.stop_all()
        if not getattr(self, "chanting", False):
            self.mic.stop()
        self.show_drill()

    def _drill_finish(self):
        dr = self.drill
        ev = getattr(self, "_drill_ev", None)
        if ev:
            ev.cancel()
        if not getattr(self, "chanting", False):
            self.mic.stop()
        res = dr["results"]
        scores = [s for _, _, s in res]
        avg = sum(scores) / len(scores) if scores else 0
        devs = {}
        for d, dev, _ in res:
            if dev is not None:
                devs.setdefault(T.label(d), []).append(dev)
        devs = {k: sum(v) / len(v) for k, v in devs.items()}
        hist = self.cfg.setdefault("drills", [])
        hist.append({"date": datetime.datetime.now().strftime("%d/%m %H:%M"), "avg": round(avg, 1),
                     "genus": self.cfg["genus"], "devs": devs})
        self.cfg["drills"] = hist[-50:]
        self.save()
        self.drill = None
        box = self._box("drill_box")
        self._txt(box, f"[size=20sp][b]Βαθμός: {avg:.1f}/10[/b][/size]".replace(".", ","))
        lines = []
        byz = T.positions(self.cfg["genus"], False, self.alterations())
        tmp = T.positions(self.cfg["genus"], True, self.alterations())
        for d, dev, score in res:
            if dev is None:
                lines.append(f"{T.label(d)}: δεν ακούστηκε")
                continue
            col = "0F9B57" if abs(dev) <= 1 else ("C98A00" if abs(dev) <= 3 else "B4461B")
            line = f"{T.label(d)}: [color=#{col}][b]{dev:+.1f}[/b][/color] μόρια".replace(".", ",")
            k = d % 7
            gap = tmp[k] - byz[k]
            if abs(gap) >= 2 and abs(dev - gap) <= 1.2 and not self.cfg["tempered"]:
                line += "  [size=12sp](μάλλον τον ψάλλεις ευρωπαϊκά, συγκερασμένα)[/size]"
            lines.append(line)
        self._txt(box, "\n".join(lines))
        self._txt(box, "[size=12sp]Θετικό = ψηλά, αρνητικό = χαμηλά. Έως ±1 μόριο θεωρείται ακριβές.[/size]")
        self._big(box, "ΞΑΝΑ", self.show_drill)

    # ================================================================== ηχογράφηση ψαλμωδίας
    def _rec_dir(self):
        p = os.path.join(self.user_data_dir, "recordings")
        os.makedirs(p, exist_ok=True)
        return p

    def show_chantrec(self):
        box = self._box("chantrec_box")
        self._txt(box, "[size=18sp][b]Ηχογράφηση ψαλμωδίας[/b][/size]\nΞεκίνα την ηχογράφηση και μετά, από την "
                       "καρτέλα «Ισοκράτης» ή «Ύμνοι», βάλε τον ισοκράτη και ψάλε. Για να ακούγεται και ο ισοκράτης, "
                       "παίξε τον από το ηχείο του κινητού (όχι ακουστικά). Μέγιστη διάρκεια 15 λεπτά.")
        if getattr(self, "chanting", False):
            el = int(time.time() - self.chant_start)
            self._chant_lbl = self._txt(box, f"[size=22sp][color=#B4461B][b]REC · Ηχογράφηση {el // 60}:{el % 60:02d}"
                                             f"[/b][/color][/size]")
            self._big(box, "ΣΤΟΠ ΚΑΙ ΑΠΟΘΗΚΕΥΣΗ", self.stop_chant, h=70)
        else:
            self._big(box, "ΕΝΑΡΞΗ ΗΧΟΓΡΑΦΗΣΗΣ", self.start_chant, h=70)
        self._chant_msg = self._txt(box, "")
        files = sorted((f for f in os.listdir(self._rec_dir()) if f.endswith(".wav")), reverse=True)
        if files:
            self._txt(box, "[b]Οι ηχογραφήσεις μου[/b]")
        for fname in files[:30]:
            path = os.path.join(self._rec_dir(), fname)
            try:
                with wave.open(path) as w:
                    dur = w.getnframes() / w.getframerate()
            except Exception:  # noqa: BLE001
                dur = 0
            self._txt(box, f"{fname[:-4].replace('_', ' ')} · {int(dur) // 60}:{int(dur) % 60:02d}")
            row = BoxLayout(size_hint_y=None, height=dp(46) * self.ui, spacing=dp(6))
            for label, cb in (("Ακρόαση", lambda p=path: self.play_rec(p)),
                              ("Αποστολή", lambda p=path: self.share_rec(p)),
                              ("Διαγραφή", lambda p=path: (os.remove(p), self.show_chantrec()))):
                b = self._f("Flat")(text=label)
                b.bind(on_release=lambda w, c=cb: c())
                row.add_widget(b)
            box.add_widget(row)

    def start_chant(self):
        if not IS_ANDROID:
            self._chant_msg.text = "Η ηχογράφηση λειτουργεί μόνο στο κινητό."
            return

        def ok():
            self.mic.start_capture()
            self.chanting = True
            self.chant_start = time.time()
            self._chant_ev = Clock.schedule_interval(self._chant_tick, 1)
            self.show_chantrec()
            self.refresh()
        self.mic.start(ok, lambda m: setattr(self._chant_msg, "text", m))

    def _chant_tick(self, dt):
        el = int(time.time() - self.chant_start)
        lbl = getattr(self, "_chant_lbl", None)
        if lbl is not None:
            lbl.text = f"[size=22sp][color=#B4461B][b]REC · Ηχογράφηση {el // 60}:{el % 60:02d}[/b][/color][/size]"
        if el >= 15 * 60:
            self.stop_chant()

    def stop_chant(self):
        if not getattr(self, "chanting", False):
            return
        ev = getattr(self, "_chant_ev", None)
        if ev:
            ev.cancel()
        raw = os.path.join(self._rec_dir(), "_capture.pcm")
        ok = self.mic.stop_capture(raw)
        self.chanting = False
        if self.root_w.ids.sm.current not in ("tuner",) and not getattr(self, "drill", None):
            self.mic.stop()
        name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M") + ".wav"
        dest = os.path.join(self._rec_dir(), name)

        def work():
            msg = "Η ηχογράφηση αποθηκεύτηκε."
            try:
                if not ok:
                    raise OSError("δεν αποθηκεύτηκε")
                with open(raw, "rb") as fh, wave.open(dest, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(16000)
                    while True:
                        chunk = fh.read(1 << 16)
                        if not chunk:
                            break
                        w.writeframes(chunk)
                os.remove(raw)
            except Exception as e:  # noqa: BLE001
                msg = f"Πρόβλημα στην αποθήκευση: {str(e)[:60]}"
            Clock.schedule_once(lambda dt: (self.show_chantrec(), setattr(self._chant_msg, "text", msg),
                                            self.refresh()))
        threading.Thread(target=work, daemon=True).start()

    def play_rec(self, path):
        try:
            from kivy.core.audio import SoundLoader
            if getattr(self, "_rec_sound", None):
                self._rec_sound.stop()
            self._rec_sound = SoundLoader.load(path)
            if self._rec_sound:
                self._rec_sound.play()
        except Exception:  # noqa: BLE001
            pass

    def share_rec(self, path):
        """Αποθηκεύει αντίγραφο στις Λήψεις (Download/Isokratis) και ανοίγει την αποστολή (Viber, email…)."""
        if not IS_ANDROID:
            self._chant_msg.text = path
            return
        try:
            from jnius import autoclass, cast
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            sdk = autoclass("android.os.Build$VERSION").SDK_INT
            name = os.path.basename(path)
            with open(path, "rb") as fh:
                data = fh.read()
            if sdk >= 29:
                ContentValues = autoclass("android.content.ContentValues")
                Downloads = autoclass("android.provider.MediaStore$Downloads")
                Cols = autoclass("android.provider.MediaStore$MediaColumns")
                v = ContentValues()
                v.put(Cols.DISPLAY_NAME, name)
                v.put(Cols.MIME_TYPE, "audio/wav")
                v.put(Cols.RELATIVE_PATH, "Download/Isokratis")
                resolver = act.getContentResolver()
                uri = resolver.insert(Downloads.EXTERNAL_CONTENT_URI, v)
                out = resolver.openOutputStream(uri)
                out.write(data)
                out.close()
                Intent = autoclass("android.content.Intent")
                String = autoclass("java.lang.String")
                i = Intent(Intent.ACTION_SEND)
                i.setType("audio/wav")
                i.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
                i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                act.startActivity(Intent.createChooser(i, cast("java.lang.CharSequence", String("Αποστολή"))))
                self._chant_msg.text = "Αντίγραφο αποθηκεύτηκε και στις Λήψεις / Isokratis."
            else:
                Env = autoclass("android.os.Environment")
                folder = os.path.join(Env.getExternalStoragePublicDirectory(Env.DIRECTORY_DOWNLOADS).getAbsolutePath(),
                                      "Isokratis")
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, name), "wb") as fh:
                    fh.write(data)
                self._chant_msg.text = ("Αποθηκεύτηκε στις Λήψεις / Isokratis. Επισύναψέ το από εκεί στο Viber ή "
                                        "στο email.")
        except Exception as e:  # noqa: BLE001
            self._chant_msg.text = f"Δεν έγινε η αποστολή: {str(e)[:80]}"

    # ================================================================== μετρονόμος
    METRES = {"Απλός (χωρίς τονισμό)": 1, "Δίσημος": 2, "Τρίσημος": 3, "Τετράσημος": 4}

    def show_metro(self):
        import voice_pro as V
        box = self._box("metro_box")
        m = self.cfg.setdefault("metro", {"bpm": 72, "metre": "Δίσημος", "vol": 0.7})
        on = getattr(self, "metro_on", False)
        self._txt(box, "[size=18sp][b]Μετρονόμος[/b][/size]\nΣτον βυζαντινό ρυθμό ο χρόνος μετρά σε θέσεις: αργός "
                       "(≈ 50–70), μέτριος (≈ 70–100), γρήγορος (≈ 100–140) χτύποι το λεπτό.")
        big = Label(text=f"{m['bpm']}", bold=True, font_size=f"{int(72 * self.ui)}sp", color=self.c_accent,
                    size_hint_y=None, height=dp(110) * self.ui)
        box.add_widget(big)
        sl = self._f("Slider")(min=40, max=180, step=1, value=m["bpm"], size_hint_y=None, height=dp(48),
                                value_track=True, value_track_color=self.c_accent)

        def on_bpm(w, v):
            m["bpm"] = int(v)
            big.text = str(int(v))
            if getattr(self, "metro_on", False):
                if getattr(self, "_metro_job", None):
                    self._metro_job.cancel()
                self._metro_job = Clock.schedule_once(lambda dt: self._metro_start(), 0.3)
        sl.bind(value=on_bpm)
        box.add_widget(sl)
        quick = BoxLayout(size_hint_y=None, height=dp(44) * self.ui, spacing=dp(6))
        for label, bpm in (("Αργός", 60), ("Μέτριος", 84), ("Γρήγορος", 116)):
            b = self._f("Flat")(text=label)
            b.bind(on_release=lambda w, v=bpm: setattr(sl, "value", v))
            quick.add_widget(b)
        box.add_widget(quick)
        row = BoxLayout(size_hint_y=None, height=dp(48) * self.ui, spacing=dp(6))
        row.add_widget(Label(text="Μέτρο", color=self.c_text, size_hint_x=0.3))
        sp = self._f("DarkSpinner")(text=m["metre"], values=list(self.METRES))

        def on_metre(w, v):
            m["metre"] = v
            if getattr(self, "metro_on", False):
                self._metro_start()
        sp.bind(text=on_metre)
        row.add_widget(sp)
        box.add_widget(row)
        vrow = BoxLayout(size_hint_y=None, height=dp(48) * self.ui, spacing=dp(6))
        vrow.add_widget(Label(text="Ένταση", color=self.c_text, size_hint_x=0.3))
        vs = self._f("Slider")(min=0, max=1, value=m.get("vol", 0.7), value_track=True, value_track_color=self.c_accent)

        def on_vol(w, v):
            m["vol"] = float(v)
            self.engine.aux_volume(float(v))
        vs.bind(value=on_vol)
        vrow.add_widget(vs)
        box.add_widget(vrow)
        self._big(box, "ΣΤΟΠ" if on else "ΕΝΑΡΞΗ", self._metro_toggle, h=70)
        _ = V

    def _metro_start(self):
        import voice_pro as V
        m = self.cfg["metro"]
        beats = self.METRES.get(m["metre"], 2)
        self.engine.play_aux(f"metro|{m['bpm']}|{beats}", V.metronome_loop(m["bpm"], beats), m.get("vol", 0.7))
        self.metro_on = True
        self.save()

    def _metro_toggle(self):
        if getattr(self, "metro_on", False):
            self.engine.stop_aux()
            self.metro_on = False
        else:
            self._metro_start()
        self.show_metro()

    # ================================================================== αντίγραφο ασφαλείας
    def share_text(self, text, subject="Ισοκράτης"):
        if not IS_ANDROID:
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(text)
            except Exception:  # noqa: BLE001
                pass
            return
        try:
            from jnius import autoclass, cast
            Intent = autoclass("android.content.Intent")
            String = autoclass("java.lang.String")
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            i = Intent(Intent.ACTION_SEND)
            i.setType("text/plain")
            i.putExtra(Intent.EXTRA_SUBJECT, cast("java.lang.CharSequence", String(subject)))
            i.putExtra(Intent.EXTRA_TEXT, cast("java.lang.CharSequence", String(text)))
            act.startActivity(Intent.createChooser(i, cast("java.lang.CharSequence", String(subject))))
        except Exception:  # noqa: BLE001
            pass

    def backup_text(self):
        import json
        return "ISOKRATIS-BACKUP-1\n" + json.dumps(self.cfg, ensure_ascii=False)

    def restore_text(self, text):
        import json
        body = text.strip()
        if body.startswith("ISOKRATIS-BACKUP-1"):
            body = body.split("\n", 1)[1]
        data = json.loads(body)
        if not isinstance(data, dict) or "genus" not in data:
            raise ValueError("Δεν είναι αντίγραφο του Ισοκράτη.")
        self.cfg.update(data)
        self._migrate_voice()
        self.save()

    _ = synth
