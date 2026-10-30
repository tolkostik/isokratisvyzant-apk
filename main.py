"""
Ψηφιακός Ισοκράτης Βυζαντινής Μουσικής.
"""
import json
import os
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.utils import platform

import synth
import voice_pro as V
import theory as T
from audio import Engine
from mic import Mic
from extra import ExtraMixin

IS_ANDROID = platform == "android"
MAX_DRONES = 4

THEMES = {
    "day": {"bg": [0.055, 0.063, 0.082, 1], "btn": [0.13, 0.15, 0.19, 1], "accent": [0.95, 0.71, 0.14, 1],
            "text": [0.93, 0.9, 0.82, 1], "dim": [0.62, 0.64, 0.68, 1], "on_accent": [0.06, 0.07, 0.09, 1],
            "half": [0.25, 0.2, 0.08, 1], "stop": [0.45, 0.12, 0.1, 1]},
    # νυχτερινό: μόνο σκούρο κόκκινο, για να μη «θαμπώνουν» τα μάτια στο σκοτάδι
    "night": {"bg": [0.0, 0.0, 0.0, 1], "btn": [0.1, 0.015, 0.01, 1], "accent": [0.62, 0.08, 0.05, 1],
              "text": [0.7, 0.16, 0.1, 1], "dim": [0.45, 0.1, 0.07, 1], "on_accent": [0.0, 0.0, 0.0, 1],
              "half": [0.22, 0.03, 0.02, 1], "stop": [0.3, 0.03, 0.02, 1]},
}

DEFAULTS = {
    "genus": "Διατονικό", "mode": "Ελεύθερα", "octave": "Μέση", "multi": False,
    "vowel": synth.DEFAULT_VOWEL, "chorus": True, "tempered": False,
    "attack": 0.6, "release": 1.2, "semis": 0, "moria": 0, "volume": 0.8,
    "alter": [0, 0, 0, 0, 0, 0, 0], "attr": [0, 0, 0, 0], "attr_size": 4,
    "favorites": [], "night": False, "pedal": True, "tablet": False,
    "room": V.DEFAULT_ROOM, "programs": [], "drills": [], "bank_name": "Η φωνή μου",
}

KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<Dim@Label>:
    color: app.c_dim
    font_size: sp(13) * app.ui
    halign: 'left'
    valign: 'middle'
    text_size: self.size

<Txt@Label>:
    size_hint_y: None
    markup: True
    color: app.c_text
    halign: 'left'
    valign: 'top'
    text_size: self.width - dp(8), None
    height: self.texture_size[1] + dp(10)

<Flat@Button>:
    background_normal: ''
    background_down: ''
    background_color: app.c_btn
    color: app.c_text
    font_size: sp(15) * app.ui

<Seg@ToggleButton>:
    background_normal: ''
    background_down: ''
    background_color: app.c_accent if self.state == 'down' else app.c_btn
    color: app.c_on_accent if self.state == 'down' else app.c_text
    font_size: sp(14) * app.ui
    bold: True

<DarkSpinner@Spinner>:
    background_normal: ''
    background_color: app.c_btn
    color: app.c_accent
    font_size: sp(15) * app.ui
    option_cls: 'DarkOption'

<DarkOption@SpinnerOption>:
    background_normal: ''
    background_color: app.c_bg
    color: app.c_text
    font_size: sp(15) * app.ui
    height: dp(48) * app.ui

<NoteBtn>:
    background_normal: ''
    background_down: ''
    markup: True
    halign: 'center'
    background_color: self.bg
    color: self.fg

<Root>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: app.c_bg
        Rectangle:
            pos: self.pos
            size: self.size
    ScreenManager:
        id: sm
        Screen:
            name: 'main'
            BoxLayout:
                orientation: 'vertical'
                padding: dp(10), dp(6)
                spacing: dp(6) * app.ui
                BoxLayout:
                    size_hint_y: None
                    height: dp(50) * app.ui
                    spacing: dp(6)
                    Label:
                        text: 'Ισοκράτης'
                        bold: True
                        font_size: sp(21) * app.ui
                        color: app.c_accent
                        halign: 'left'
                        valign: 'middle'
                        text_size: self.size
                        size_hint_x: 0.3
                    Label:
                        id: status
                        font_size: sp(11) * app.ui
                        color: app.c_dim
                        halign: 'right'
                        valign: 'middle'
                        text_size: self.size
                    Seg:
                        id: tablet
                        text: 'Tablet'
                        size_hint_x: None
                        width: dp(74) * app.ui
                        on_release: app.set_tablet(self.state == 'down')
                    Seg:
                        id: night
                        text: 'Νύχτα'
                        size_hint_x: None
                        width: dp(70) * app.ui
                        on_release: app.set_night(self.state == 'down')
                BoxLayout:
                    id: body
                    orientation: 'vertical'
                    spacing: dp(8) * app.ui
                    BoxLayout:
                        id: top_ctrl
                        orientation: 'vertical'
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6) * app.ui
                        BoxLayout:
                            size_hint_y: None
                            height: dp(46) * app.ui
                            spacing: dp(6)
                            DarkSpinner:
                                id: mode
                                on_text: app.set_mode(self.text)
                            DarkSpinner:
                                id: genus
                                on_text: app.set_genus(self.text)
                        DarkSpinner:
                            id: fav
                            size_hint_y: None
                            height: dp(42) * app.ui
                            text: 'Αγαπημένα…'
                            on_text: app.load_favorite(self.text)
                    BoxLayout:
                        id: grid_panel
                        orientation: 'vertical'
                        spacing: dp(6) * app.ui
                        BoxLayout:
                            size_hint_y: None
                            height: dp(42) * app.ui
                            spacing: dp(6)
                            Seg:
                                id: oct_low
                                text: 'Χαμηλά'
                                group: 'oct'
                                allow_no_selection: False
                                on_release: app.set_octave('Χαμηλά')
                            Seg:
                                id: oct_mid
                                text: 'Μέση'
                                group: 'oct'
                                allow_no_selection: False
                                on_release: app.set_octave('Μέση')
                            Seg:
                                id: oct_high
                                text: 'Ψηλά'
                                group: 'oct'
                                allow_no_selection: False
                                on_release: app.set_octave('Ψηλά')
                        GridLayout:
                            id: grid
                            cols: 4
                            spacing: dp(8) * app.ui
                        BoxLayout:
                            id: attr_row
                            size_hint_y: None
                            height: dp(40) * app.ui
                            spacing: dp(4)
                    BoxLayout:
                        id: bottom_ctrl
                        orientation: 'vertical'
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6) * app.ui
                        BoxLayout:
                            size_hint_y: None
                            height: dp(44) * app.ui
                            spacing: dp(6)
                            Seg:
                                id: single
                                text: 'Ένα'
                                group: 'multi'
                                allow_no_selection: False
                                on_release: app.set_multi(False)
                            Seg:
                                id: multi
                                text: 'Έως 4'
                                group: 'multi'
                                allow_no_selection: False
                                on_release: app.set_multi(True)
                            Flat:
                                text: '+ 5η'
                                on_release: app.add_fifth()
                            Flat:
                                text: '+ 8η κάτω'
                                on_release: app.add_octave_below()
                        BoxLayout:
                            size_hint_y: None
                            height: dp(38) * app.ui
                            spacing: dp(8)
                            Dim:
                                text: 'Ένταση'
                                size_hint_x: None
                                width: dp(60) * app.ui
                            Slider:
                                id: volume
                                min: 0
                                max: 1
                                value_track: True
                                value_track_color: app.c_accent
                                on_value: app.set_volume(self.value)
                        Button:
                            text: 'ΣΙΩΠΗ'
                            bold: True
                            font_size: sp(20) * app.ui
                            size_hint_y: None
                            height: dp(58) * app.ui
                            background_normal: ''
                            background_color: app.c_stop
                            color: app.c_text
                            on_release: app.silence()
        Screen:
            name: 'tuner'
            BoxLayout:
                orientation: 'vertical'
                padding: dp(14), dp(10)
                spacing: dp(10)
                Txt:
                    text: '[size=18sp][b]Κουρδιστήρι[/b][/size]\\nΨάλε σταθερά τη βάση σου. Η εφαρμογή ακούει, δείχνει τον φθόγγο και μπορεί να ρυθμίσει μόνη της τη μετατόπιση ώστε ο ισοκράτης να ταιριάζει στη φωνή σου. Όσο ακούει, ο ισοκράτης σωπαίνει.'
                Label:
                    id: tun_note
                    text: '–'
                    font_size: '64sp'
                    bold: True
                    color: app.c_accent
                    size_hint_y: None
                    height: dp(100)
                Label:
                    id: tun_info
                    text: ''
                    markup: True
                    font_size: '18sp'
                    color: app.c_text
                    size_hint_y: None
                    height: dp(70)
                    halign: 'center'
                    text_size: self.width, None
                BoxLayout:
                    size_hint_y: None
                    height: dp(48)
                    spacing: dp(8)
                    Dim:
                        text: 'Ψάλλω τον φθόγγο:'
                    DarkSpinner:
                        id: tun_degree
                        text: 'Πα'
                        values: ['Νη', 'Πα', 'Βου', 'Γα', 'Δι', 'Κε', 'Ζω']
                Button:
                    text: 'ΟΡΙΣΜΟΣ ΒΑΣΗΣ ΑΠΟ ΤΗ ΦΩΝΗ ΜΟΥ'
                    bold: True
                    size_hint_y: None
                    height: dp(56)
                    background_normal: ''
                    background_color: app.c_accent
                    color: app.c_on_accent
                    on_release: app.set_base_from_voice()
                Txt:
                    id: tun_msg
                    text: ''
                Widget:
        Screen:
            name: 'voice'
            ScrollView:
                do_scroll_x: False
                BoxLayout:
                    id: voice_box
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(14), dp(10)
                    spacing: dp(8)
        Screen:
            name: 'hymns'
            ScrollView:
                do_scroll_x: False
                BoxLayout:
                    id: hymns_box
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(14), dp(10)
                    spacing: dp(8)
        Screen:
            name: 'perform'
            BoxLayout:
                id: perform_box
                orientation: 'vertical'
                padding: dp(12), dp(10)
                spacing: dp(10)
        Screen:
            name: 'practice'
            ScrollView:
                do_scroll_x: False
                BoxLayout:
                    id: practice_box
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(14), dp(10)
                    spacing: dp(8)
        Screen:
            name: 'drill'
            ScrollView:
                do_scroll_x: False
                BoxLayout:
                    id: drill_box
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(14), dp(10)
                    spacing: dp(8)
        Screen:
            name: 'metro'
            ScrollView:
                do_scroll_x: False
                BoxLayout:
                    id: metro_box
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(14), dp(10)
                    spacing: dp(10)
        Screen:
            name: 'chantrec'
            ScrollView:
                do_scroll_x: False
                BoxLayout:
                    id: chantrec_box
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(14), dp(10)
                    spacing: dp(8)
        Screen:
            name: 'settings'
            ScrollView:
                do_scroll_x: False
                BoxLayout:
                    id: settings
                    orientation: 'vertical'
                    size_hint_y: None
                    height: self.minimum_height
                    padding: dp(14), dp(10)
                    spacing: dp(8)
    BoxLayout:
        size_hint_y: None
        height: dp(50) * app.ui
        Seg:
            id: nav_main
            text: 'Ισοκράτης'
            group: 'nav'
            state: 'down'
            allow_no_selection: False
            on_release: app.go('main')
        Seg:
            id: nav_hymns
            text: 'Ύμνοι'
            group: 'nav'
            allow_no_selection: False
            on_release: app.go('hymns')
        Seg:
            id: nav_practice
            text: 'Εξάσκηση'
            group: 'nav'
            allow_no_selection: False
            on_release: app.go('practice')
        Seg:
            id: nav_voice
            text: 'Φωνή'
            group: 'nav'
            allow_no_selection: False
            on_release: app.go('voice')
        Seg:
            id: nav_set
            text: 'Ρυθμίσεις'
            group: 'nav'
            allow_no_selection: False
            on_release: app.go('settings')
"""


def wave_error():
    import wave
    return wave.Error


class NoteBtn(Button):
    bg = ListProperty([0.13, 0.15, 0.19, 1])
    fg = ListProperty([0.95, 0.71, 0.14, 1])


class Root(BoxLayout):
    pass


class IsokratisApp(ExtraMixin, App):
    title = "Isokratis"
    c_bg = ListProperty(THEMES["day"]["bg"])
    c_btn = ListProperty(THEMES["day"]["btn"])
    c_accent = ListProperty(THEMES["day"]["accent"])
    c_text = ListProperty(THEMES["day"]["text"])
    c_dim = ListProperty(THEMES["day"]["dim"])
    c_on_accent = ListProperty(THEMES["day"]["on_accent"])
    c_half = ListProperty(THEMES["day"]["half"])
    c_stop = ListProperty(THEMES["day"]["stop"])
    ui = NumericProperty(1.0)
    tablet = BooleanProperty(False)

    def build(self):
        self.cfg_path = os.path.join(self.user_data_dir, "settings.json")
        self.cfg = json.loads(json.dumps(DEFAULTS))
        try:
            with open(self.cfg_path, encoding="utf-8") as f:
                self.cfg.update(json.load(f))
        except Exception:  # noqa: BLE001
            pass
        synth.set_sample_dir(os.path.join(self.user_data_dir, "samples"))
        self._migrate_voice()
        self.engine = Engine(os.path.join(self.user_data_dir, "voices"))
        self.engine.master = self.cfg["volume"]
        self.engine.attack = self.cfg["attack"]
        self.engine.release = self.cfg["release"]
        self.mic = Mic()
        self.pitches = []
        self.recording = False
        self.active = []
        self.last_active = []
        self.perf = None
        self.drill = None
        self.chanting = False
        self.apply_theme(self.cfg["night"])
        self.tablet = bool(self.cfg.get("tablet"))
        self.ui = 1.45 if self.tablet else 1.0
        Builder.load_string(KV)
        self.root_w = Root()
        ids = self.root_w.ids
        self._loading = True
        ids.mode.values = ["Ελεύθερα"] + list(T.MODES)
        ids.mode.text = self.cfg["mode"]
        ids.genus.values = list(T.GENERA)
        ids.genus.text = self.cfg["genus"]
        ids.volume.value = self.cfg["volume"]
        ids.night.state = "down" if self.cfg["night"] else "normal"
        ids.tablet.state = "down" if self.tablet else "normal"
        {"Χαμηλά": ids.oct_low, "Μέση": ids.oct_mid, "Ψηλά": ids.oct_high}[self.cfg["octave"]].state = "down"
        (ids.multi if self.cfg["multi"] else ids.single).state = "down"
        self.note_btns = []
        for d in range(8):
            b = NoteBtn(font_size="26sp")
            b.bind(on_release=lambda w, deg=d: self.press(deg))
            ids.grid.add_widget(b)
            self.note_btns.append(b)
        from kivy.factory import Factory
        self.attr_btns = []
        for i, (name, _, _) in enumerate(T.ATTRACTIONS):
            tb = Factory.Seg(text=name, font_size="12sp", state="down" if self.cfg["attr"][i] else "normal")
            tb.bind(on_release=lambda w, k=i: self.toggle_attr(k, w.state == "down"))
            ids.attr_row.add_widget(tb)
            self.attr_btns.append(tb)
        self._fav_values()
        self._build_settings(ids.settings)
        self._build_voice(ids.voice_box)
        self._loading = False
        Window.bind(on_keyboard=self._on_key)
        Window.bind(size=lambda *a: Clock.schedule_once(lambda dt: self.arrange(), 0))
        self._side = None
        self.arrange()
        self._orientation(self.tablet)
        self.refresh()
        self.prefetch(all_octaves=True)
        if self.cfg["night"]:
            self._brightness(0.12)
        return self.root_w

    def on_pause(self):
        return True       # ο ήχος συνεχίζει αν σβήσει η οθόνη

    def on_stop(self):
        self.mic.stop()

    # ------------------------------------------------------------ θέμα
    def apply_theme(self, night):
        th = THEMES["night" if night else "day"]
        for k, v in th.items():
            setattr(self, "c_" + k, list(v))
        Window.clearcolor = th["bg"]

    def set_night(self, on):
        self.cfg["night"] = on
        self.apply_theme(on)
        self.save()
        self.refresh()
        self._brightness(0.12 if on else -1.0)

    def _brightness(self, value):
        if not IS_ANDROID:
            return
        try:
            from android.runnable import run_on_ui_thread
            from jnius import autoclass

            @run_on_ui_thread
            def setb():
                act = autoclass("org.kivy.android.PythonActivity").mActivity
                win = act.getWindow()
                lp = win.getAttributes()
                lp.screenBrightness = float(value)
                win.setAttributes(lp)
            setb()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ διάταξη tablet
    def set_tablet(self, on):
        self.tablet = bool(on)
        self.cfg["tablet"] = self.tablet
        self.ui = 1.45 if on else 1.0
        self.save()
        self._orientation(on)
        self.arrange()
        self.refresh()

    def arrange(self, *a):
        """Κινητό ή tablet σε όρθια θέση: όλα το ένα κάτω από το άλλο.
        Tablet σε οριζόντια θέση: φθόγγοι αριστερά, χειριστήρια δεξιά."""
        ids = self.root_w.ids
        body = ids.body
        landscape = self.tablet and Window.width > Window.height
        for w in (ids.top_ctrl, ids.grid_panel, ids.bottom_ctrl):
            if w.parent:
                w.parent.remove_widget(w)
        if self._side is not None and self._side.parent:
            self._side.parent.remove_widget(self._side)
        body.clear_widgets()
        if landscape:
            body.orientation = "horizontal"
            ids.grid_panel.size_hint_x = 0.64
            if self._side is None:
                self._side = BoxLayout(orientation="vertical", spacing=dp(10))
            self._side.clear_widgets()
            self._side.size_hint_x = 0.36
            self._side.add_widget(ids.top_ctrl)
            from kivy.uix.widget import Widget
            self._side.add_widget(Widget())
            self._side.add_widget(ids.bottom_ctrl)
            body.add_widget(ids.grid_panel)
            body.add_widget(self._side)
        else:
            body.orientation = "vertical"
            ids.grid_panel.size_hint_x = 1
            body.add_widget(ids.top_ctrl)
            body.add_widget(ids.grid_panel)
            body.add_widget(ids.bottom_ctrl)

    def _orientation(self, free):
        """Tablet: ελεύθερη περιστροφή. Κινητό: όρθια οθόνη."""
        if not IS_ANDROID:
            return
        try:
            from android.runnable import run_on_ui_thread
            from jnius import autoclass

            @run_on_ui_thread
            def seto():
                act = autoclass("org.kivy.android.PythonActivity").mActivity
                act.setRequestedOrientation(4 if free else 1)   # 4 = με αισθητήρα, 1 = όρθια
            seto()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ βοηθητικά
    def save(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.cfg_path, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False)
        except OSError:
            pass

    def alterations(self):
        alt = list(self.cfg["alter"])
        for i, (_, deg, sign) in enumerate(T.ATTRACTIONS):
            if self.cfg["attr"][i]:
                alt[deg] += sign * int(self.cfg["attr_size"])
        return alt

    def freq(self, d, o):
        c = self.cfg
        return T.frequency(d, o, c["genus"], c["semis"], c["moria"], c["tempered"], self.alterations())

    def voice_key(self):
        v = self.cfg["vowel"]
        if v.startswith(V.BANK_PREFIX):
            base = f"{v}#{V.bank_version(v[len(V.BANK_PREFIX):])}-p2"
        else:
            base = f"{v}#v2"
        return f"{base}@{self.cfg.get('room', V.DEFAULT_ROOM)}"

    def _migrate_voice(self):
        """Ρυθμίσεις από παλιότερες εκδόσεις → νέες ονομασίες."""
        v = self.cfg.get("vowel", "")
        if v.startswith(synth.MY_VOICE) or (v.startswith(V.BANK_PREFIX) and v[len(V.BANK_PREFIX):] not in V.banks()):
            self.cfg["vowel"] = (V.BANK_PREFIX + V.banks()[0]) if V.banks() else V.DEFAULT_VOWEL
        elif not v.startswith(V.BANK_PREFIX) and v not in V.VOWELS_V2:
            self.cfg["vowel"] = V.DEFAULT_VOWEL
        if self.cfg.get("room") not in V.ROOMS:
            self.cfg["room"] = {"Μεγάλος ναός": "Μεγάλος βυζαντινός ναός (τρούλος)"}.get(self.cfg.get("room"),
                                                                                          V.DEFAULT_ROOM)

    def key(self, d, o):
        return Engine.key_for(self.freq(d, o), self.voice_key(), self.cfg["chorus"])

    def cur_octave(self):
        return T.OCTAVES[self.cfg["octave"]]

    def apply(self):
        self.engine.play([self.key(d, o) for d, o in self.active])
        if self.active:
            self.last_active = list(self.active)
        self.refresh()

    def prefetch(self, all_octaves=False):
        o = self.cur_octave()
        keys = [self.key(d, o) for d in range(8)]
        if all_octaves:
            keys += [self.key(d, oo) for oo in (-1, 0, 1) if oo != o for d in range(8)]
        self.engine.prefetch(keys)

    def changed(self, prefetch=True):
        if self._loading:
            return
        self.save()
        self.apply()
        if prefetch:
            self.prefetch(all_octaves=True)

    def go(self, name):
        sm = self.root_w.ids.sm
        if sm.current == "tuner" and name != "tuner":
            self.stop_tuner()
        if sm.current == "drill" and name != "drill" and getattr(self, "drill", None):
            self._drill_stop()
        if sm.current == "perform" and name not in ("perform",) and getattr(self, "perf", None):
            self.perf = None
        sm.current = name
        tab = {"tuner": "practice", "drill": "practice", "chantrec": "practice", "metro": "practice",
               "perform": "hymns"}.get(name, name)
        for scr, nid in (("main", "nav_main"), ("hymns", "nav_hymns"), ("practice", "nav_practice"),
                         ("voice", "nav_voice"), ("settings", "nav_set")):
            self.root_w.ids[nid].state = "down" if scr == tab else "normal"
        if name == "tuner":
            self.start_tuner()
        if name == "voice":
            self._build_voice(self.root_w.ids.voice_box)
        if name == "hymns":
            self.show_hymns()
        if name == "practice":
            self.show_practice()
        if name == "drill":
            self.show_drill()
        if name == "chantrec":
            self.show_chantrec()
        if name == "metro":
            self.show_metro()

    # ------------------------------------------------------------ οθόνη
    def refresh(self):
        o = self.cur_octave()
        alt = self.alterations()
        pos = T.positions(self.cfg["genus"], self.cfg["tempered"], alt)
        for d, b in enumerate(self.note_btns):
            on = any(ad == d and ao == o for ad, ao in self.active)
            other = any(ad == d for ad, ao in self.active) and not on
            hz = self.freq(d, o)
            a = alt[d % 7]
            mark = f" [size=12sp]({a:+d})[/size]" if a else ""
            small = int(12 * self.ui)
            b.text = (f"[b]{T.label(d)}[/b]{mark}\n[size={small}sp]{hz:.1f} Hz[/size]").replace(".", ",")
            b.font_size = f"{int(26 * self.ui)}sp"
            b.bg = list(self.c_accent) if on else (list(self.c_half) if other else list(self.c_btn))
            b.fg = list(self.c_on_accent) if on else list(self.c_accent)
        names = " + ".join(f"{T.label(d)}{'' if oo == 0 else (' χαμ.' if oo < 0 else ' ψηλ.')}"
                           for d, oo in self.active)
        base = T.base_name(self.cfg["semis"]) + (f" {self.cfg['moria']:+d}μ" if self.cfg["moria"] else "")
        rec = "[color=#B4461B][b]REC[/b][/color]  " if getattr(self, "chanting", False) else ""
        self.root_w.ids.status.markup = True
        self.root_w.ids.status.text = f"{rec}Νη = {base}\n" + (f"Ηχεί: {names}" if names else "Σιωπή")
        pos7 = pos + [pos[0] + 72]
        steps = " ".join(str(b2 - a2) for a2, b2 in zip(pos7, pos7[1:]))
        if hasattr(self, "steps_lbl"):
            self.steps_lbl.text = f"Διαστήματα (μόρια) Νη→Νη': {steps}"

    # ------------------------------------------------------------ χειρισμός
    def press(self, d):
        o = self.cur_octave()
        item = (d, o)
        if self.cfg["multi"]:
            if item in self.active:
                self.active.remove(item)
            else:
                self.active.append(item)
                if len(self.active) > MAX_DRONES:
                    self.active.pop(0)
        else:
            self.active = [] if self.active == [item] else [item]
        self.apply()

    def step(self, delta):
        """Πεντάλ: επόμενος/προηγούμενος φθόγγος από αυτόν που ηχεί."""
        o = self.cur_octave()
        if self.active:
            d, o = self.active[-1]
            if d == 7:
                d, o = 0, o + 1
        else:
            mode = T.MODES.get(self.cfg["mode"])
            d = mode[1] if mode else 0
            delta = 0
        idx = d + o * 7 + delta
        nd, no = idx % 7, idx // 7
        no = max(-2, min(2, no))
        self.active = [(nd, no)] if not self.cfg["multi"] else (self.active[:-1] + [(nd, no)])
        self.apply()

    def add_fifth(self):
        if not self.active:
            return
        d, o = self.active[-1]
        if d == 7:
            d, o = 0, o + 1
        nd, no = d + 4, o
        if nd >= 7:
            nd, no = nd - 7, o + 1
        self._add((nd, no))

    def add_octave_below(self):
        if not self.active:
            return
        d, o = self.active[-1]
        self._add((d, o - 1))

    def _add(self, item):
        if not self.cfg["multi"]:
            self.cfg["multi"] = True
            self.root_w.ids.multi.state = "down"
            self.root_w.ids.single.state = "normal"
        if item not in self.active:
            self.active.append(item)
            if len(self.active) > MAX_DRONES:
                self.active.pop(0)
        self.changed(prefetch=False)

    def silence(self):
        self.active = []
        self.engine.stop_all()
        self.refresh()

    def toggle_attr(self, i, on):
        a = list(self.cfg["attr"])
        a[i] = 1 if on else 0
        self.cfg["attr"] = a
        self.changed()

    def set_mode(self, m):
        if self._loading:
            return
        self.cfg["mode"] = m
        if m in T.MODES:
            genus, deg = T.MODES[m]
            self.cfg["genus"] = genus
            self.root_w.ids.genus.text = genus
            self.active = [(deg, self.cur_octave())]
            self.root_w.ids.tun_degree.text = T.NAMES[deg]
        self.changed()

    def set_genus(self, g):
        if self._loading or g not in T.GENERA:
            return
        self.cfg["genus"] = g
        self.changed()

    def set_octave(self, name):
        self.cfg["octave"] = name
        self.save()
        self.refresh()

    def set_multi(self, on):
        self.cfg["multi"] = on
        if not on and len(self.active) > 1:
            self.active = self.active[-1:]
            self.apply()
        self.save()

    def set_volume(self, v):
        self.cfg["volume"] = float(v)
        self.engine.master = float(v)
        if not self._loading:
            self.save()

    # ------------------------------------------------------------ πεντάλ / πληκτρολόγιο Bluetooth
    def _on_key(self, window, key, scancode=None, codepoint=None, modifier=None, *args):
        if key == 27 or not self.cfg.get("pedal", True):
            return False                       # το «πίσω» του Android μένει ως έχει
        if hasattr(self, "pedal_lbl"):
            self.pedal_lbl.text = f"Τελευταίο πλήκτρο που πατήθηκε: κωδικός {key}"
        if getattr(self, "perf", None) and self.root_w.ids.sm.current == "perform":
            if key in (275, 274, 281, 1073741902, 1073741905, 13, 271):
                self.perform_step(+1)
                return True
            if key in (276, 273, 280, 1073741899, 1073741906):
                self.perform_step(-1)
                return True
            if key == 32:
                self.perform_toggle()
                return True
        if key in (275, 274, 281, 1073741902, 1073741905):        # δεξί, κάτω, Page Down
            self.step(+1)
        elif key in (276, 273, 280, 1073741899, 1073741906):      # αριστερό, πάνω, Page Up
            self.step(-1)
        elif key in (32, 13, 271):                                 # Space / Enter
            if self.active:
                self.silence()
            elif self.last_active:
                self.active = list(self.last_active)
                self.apply()
        elif 49 <= key <= 56:                                      # πλήκτρα 1–8
            self.press(key - 49)
        else:
            return False
        return True

    # ------------------------------------------------------------ κουρδιστήρι
    def start_tuner(self):
        ids = self.root_w.ids
        ids.tun_msg.text = ""
        self.pitches = []
        if not Mic.available():
            ids.tun_info.text = "Το κουρδιστήρι λειτουργεί μόνο στο κινητό."
            return
        self.silence()

        def ok():
            self._tun_ev = Clock.schedule_interval(self._tuner_tick, 0.1)

        self.mic.start(ok, lambda msg: setattr(ids.tun_info, "text", msg))

    def stop_tuner(self):
        ev = getattr(self, "_tun_ev", None)
        if ev:
            ev.cancel()
            self._tun_ev = None
        if not self.recording and not getattr(self, "chanting", False):
            self.mic.stop()

    def _tuner_tick(self, dt):
        ids = self.root_w.ids
        f = self.mic.pitch()
        if f <= 0:
            ids.tun_note.text = "–"
            ids.tun_info.text = "Ψάλε σταθερά ένα φωνήεν…"
            return
        self.pitches = (self.pitches + [f])[-15:]
        c = self.cfg
        d, octv, dev = T.nearest_degree(f, c["genus"], c["semis"], c["moria"], c["tempered"], self.alterations())
        ids.tun_note.text = T.NAMES[d]
        col = "0F9B57" if abs(dev) <= 1 else ("C98A00" if abs(dev) <= 3 else "B4461B")
        where = {-2: "πολύ χαμηλά", -1: "χαμηλά", 0: "μέση", 1: "ψηλά"}.get(octv, "")
        ids.tun_info.text = (f"{f:.1f} Hz · {where}\n[color=#{col}][b]{dev:+.1f} μόρια[/b][/color]"
                             .replace(".", ","))

    def set_base_from_voice(self):
        ids = self.root_w.ids
        ps = sorted(p for p in self.pitches if p > 0)
        if len(ps) < 5:
            ids.tun_msg.text = "Ψάλε σταθερά τον φθόγγο για 1–2 δευτερόλεπτα και ξαναπάτα."
            return
        f = ps[len(ps) // 2]
        deg = T.NAMES.index(ids.tun_degree.text)
        semis, mor, octv = T.base_for_voice(f, deg, self.cfg["genus"], self.cfg["tempered"], self.alterations())
        self.cfg["semis"], self.cfg["moria"] = semis, mor
        oname = {-2: "Χαμηλά", -1: "Χαμηλά", 0: "Μέση", 1: "Ψηλά"}[octv]
        self.cfg["octave"] = oname
        {"Χαμηλά": ids.oct_low, "Μέση": ids.oct_mid, "Ψηλά": ids.oct_high}[oname].state = "down"
        for w in (ids.oct_low, ids.oct_mid, ids.oct_high):
            if w.text != oname:
                w.state = "normal"
        if hasattr(self, "semis_slider"):
            self._loading = True
            self.semis_slider.value = semis
            self.moria_slider.value = mor
            self._loading = False
        self.save()
        self.refresh()
        self.prefetch(all_octaves=True)
        hz = f"{f:.1f}".replace(".", ",")
        ids.tun_msg.text = (f"Έτοιμο: Νη = {T.base_name(semis)}{f' {mor:+d} μόρια' if mor else ''}. "
                            f"Ο {ids.tun_degree.text} είναι τώρα στη φωνή σου ({hz} Hz), περιοχή «{oname}».")

    # ------------------------------------------------------------ η φωνή μου (ηχογράφηση)
    def _build_voice(self, box):
        from kivy.factory import Factory
        box.clear_widgets()
        box.add_widget(Factory.Txt(text=(
            "[size=18sp][b]Φωνές[/b][/size]\nΗ πιο φυσική, βυζαντινή απόδοση έρχεται από [b]πραγματική φωνή[/b]. "
            "Ηχογράφησε έναν ισοκράτη (εσένα, τον πρωτοψάλτη, τον δάσκαλό σου) ή εισήγαγε αρχείο WAV. Η εφαρμογή "
            "κρατά τη χροιά του ίδια σε όλους τους φθόγγους (τεχνική PSOLA).")))
        box.add_widget(Factory.Txt(text=(
            "[b]Για επαγγελματικό αποτέλεσμα:[/b] ήσυχος χώρος · σταθερό «νε» ή «ο» για 6 δευτερόλεπτα · κινητό σε "
            "μια παλάμη απόσταση · ηχογράφησε την ίδια φωνή σε 2–3 ύψη (χαμηλά, μέση, ψηλά) στην ίδια τράπεζα.")))
        row = BoxLayout(size_hint_y=None, height=dp(48) * self.ui, spacing=dp(6))
        row.add_widget(Label(text="Τράπεζα:", color=self.c_text, size_hint_x=0.3))
        self.bank_in = Factory.TextInput(text=self.cfg.get("bank_name", "Η φωνή μου"), multiline=False)
        row.add_widget(self.bank_in)
        box.add_widget(row)
        self.rec_btn = Button(text="ΗΧΟΓΡΑΦΗΣΗ (6 δευτερόλεπτα)", bold=True, size_hint_y=None, height=dp(58) * self.ui,
                              background_normal="", background_color=self.c_accent, color=self.c_on_accent)
        self.rec_btn.bind(on_release=lambda *a: self.record())
        box.add_widget(self.rec_btn)
        imp = Factory.Flat(text="ΕΙΣΑΓΩΓΗ ΑΡΧΕΙΟΥ WAV", size_hint_y=None, height=dp(50) * self.ui)
        imp.bind(on_release=lambda *a: self.import_wav())
        box.add_widget(imp)
        self.rec_msg = Factory.Txt(text="")
        box.add_widget(self.rec_msg)
        for bank in V.banks():
            smp = V.bank_samples(bank)
            notes = ", ".join(f"{T.NAMES[T.nearest_degree(d['f0'], self.cfg['genus'], self.cfg['semis'], self.cfg['moria'])[0]]}"
                              f" ({d['f0']:.0f} Hz)" for d in smp)
            active = self.cfg["vowel"] == V.BANK_PREFIX + bank
            box.add_widget(Factory.Txt(text=f"[b]{bank}[/b]{'  [color=#0F9B57](σε χρήση)[/color]' if active else ''}\n"
                                            f"[size=13sp]{len(smp)} ηχογραφήσεις: {notes}[/size]"))
            r = BoxLayout(size_hint_y=None, height=dp(46) * self.ui, spacing=dp(6))
            use = Factory.Flat(text="Χρήση")
            use.bind(on_release=lambda w, b_=bank: self._use_bank(b_))
            dl = Factory.Flat(text="Διαγραφή τράπεζας")
            dl.bind(on_release=lambda w, b_=bank: self._delete_bank(b_))
            r.add_widget(use)
            r.add_widget(dl)
            box.add_widget(r)
        if not Mic.available():
            self.rec_msg.text = "Η ηχογράφηση και η εισαγωγή λειτουργούν στο κινητό."

    def _bank(self):
        name = V.clean_bank(getattr(self, "bank_in", None).text if getattr(self, "bank_in", None) else "")
        self.cfg["bank_name"] = name
        self.save()
        return name

    def _use_bank(self, bank):
        self.cfg["vowel"] = V.BANK_PREFIX + bank
        if hasattr(self, "voice_spinner"):
            self.voice_spinner.values = V.voice_names()
            self.voice_spinner.text = self.cfg["vowel"]
        self.changed()
        self._build_voice(self.root_w.ids.voice_box)
        self.rec_msg.text = f"Ο ισοκράτης χρησιμοποιεί τώρα τη φωνή «{bank}»."

    def _use_my_voice(self):
        self._use_bank(self._bank())

    def _delete_bank(self, bank):
        V.delete_bank(bank)
        if self.cfg["vowel"] == V.BANK_PREFIX + bank:
            self.cfg["vowel"] = V.DEFAULT_VOWEL
        if hasattr(self, "voice_spinner"):
            self.voice_spinner.values = V.voice_names()
            self.voice_spinner.text = self.cfg["vowel"]
        self.changed()
        self._build_voice(self.root_w.ids.voice_box)

    def record(self):
        if self.recording or not Mic.available():
            return
        self.silence()
        self.pitches_rec = []
        self._rec_bank = self._bank()

        def ok():
            self.recording = True
            self.mic.start_capture()
            self.rec_start = time.time()
            self._rec_ev = Clock.schedule_interval(self._rec_tick, 0.1)

        self.mic.start(ok, lambda msg: setattr(self.rec_msg, "text", msg))

    def _rec_tick(self, dt):
        el = time.time() - self.rec_start
        f = self.mic.pitch()
        if f > 0:
            self.pitches_rec.append(f)
        lvl = min(1.0, self.mic.level() * 6)
        bar = "|" * int(lvl * 30)
        warn = "  (πολύ δυνατά!)" if self.mic.level() > 0.5 else ""
        self.rec_btn.text = f"Ηχογράφηση… {max(0, 6 - el):.0f}″  {bar}{warn}"
        if el < 6:
            return
        self._rec_ev.cancel()
        path = os.path.join(self.user_data_dir, "last_recording.pcm")
        ok = self.mic.stop_capture(path)
        self.recording = False
        if self.root_w.ids.sm.current != "tuner":
            self.mic.stop()
        self.rec_btn.text = "Επεξεργασία…"
        pitches = list(self.pitches_rec)
        bank = self._rec_bank

        def work():
            try:
                if not ok:
                    raise ValueError("Η ηχογράφηση δεν αποθηκεύτηκε.")
                with open(path, "rb") as fh:
                    data = fh.read()
                sid, f0 = V.add_sample(data, pitches, bank)
                msg = (f"Έτοιμο! Προστέθηκε στη «{bank}» ({f0:.0f} Hz).", True, bank)
            except Exception as e:  # noqa: BLE001
                msg = (str(e), False, bank)
            Clock.schedule_once(lambda dt: self._rec_done(*msg))

        threading.Thread(target=work, daemon=True).start()

    def _rec_done(self, msg, ok, bank=None):
        self._build_voice(self.root_w.ids.voice_box)
        if ok:
            self._use_bank(bank or self._bank())
        self.rec_msg.text = msg

    # ------------------------------------------------------------ εισαγωγή WAV
    def import_wav(self):
        if not IS_ANDROID:
            self.rec_msg.text = "Η εισαγωγή λειτουργεί στο κινητό."
            return
        try:
            from android import activity
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            i = Intent(Intent.ACTION_GET_CONTENT)
            i.setType("audio/*")
            i.addCategory(Intent.CATEGORY_OPENABLE)
            self._imp_bank = self._bank()
            activity.bind(on_activity_result=self._on_import)
            autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(i, 4242)
        except Exception as e:  # noqa: BLE001
            self.rec_msg.text = f"Δεν άνοιξε η επιλογή αρχείου: {str(e)[:80]}"

    def _on_import(self, req, res, intent):
        if req != 4242:
            return
        try:
            from android import activity
            activity.unbind(on_activity_result=self._on_import)
        except Exception:  # noqa: BLE001
            pass
        if res != -1 or intent is None:
            return
        path = os.path.join(self.user_data_dir, "import.wav")
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            ins = act.getContentResolver().openInputStream(intent.getData())
            outs = autoclass("java.io.FileOutputStream")(path)
            autoclass("android.os.FileUtils").copy(ins, outs)
            ins.close()
            outs.close()
        except Exception as e:  # noqa: BLE001
            Clock.schedule_once(lambda dt: setattr(self.rec_msg, "text",
                                                   f"Δεν διαβάστηκε το αρχείο (χρειάζεται Android 10+): {str(e)[:60]}"))
            return
        bank = self._imp_bank
        Clock.schedule_once(lambda dt: setattr(self.rec_msg, "text", "Ανάλυση αρχείου…"))

        def work():
            try:
                data = V.read_wav_mono16k(path)
                pitches = V.estimate_pitches(data)
                sid, f0 = V.add_sample(data, pitches, bank)
                msg = (f"Έτοιμο! Το αρχείο μπήκε στη «{bank}» ({f0:.0f} Hz).", True, bank)
            except wave_error() as e:
                msg = (f"Μόνο αρχεία WAV υποστηρίζονται ({str(e)[:50]}).", False, bank)
            except Exception as e:  # noqa: BLE001
                msg = (str(e)[:160], False, bank)
            Clock.schedule_once(lambda dt: self._rec_done(*msg))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ αγαπημένα
    FAV_KEYS = ("genus", "mode", "semis", "moria", "alter", "attr", "attr_size", "vowel", "chorus", "tempered",
                "octave", "multi", "room")

    def _fav_values(self):
        self.root_w.ids.fav.values = [f["name"] for f in self.cfg["favorites"]] or ["(κανένα ακόμα)"]

    def save_favorite(self, name):
        name = name.strip() or f"Αγαπημένο {len(self.cfg['favorites']) + 1}"
        fav = {k: self.cfg[k] for k in self.FAV_KEYS}
        fav["name"] = name
        fav["active"] = [list(x) for x in (self.active or self.last_active)]
        self.cfg["favorites"] = [f for f in self.cfg["favorites"] if f["name"] != name] + [fav]
        self.save()
        self._fav_values()
        self._fav_list()

    def load_favorite(self, name):
        fav = next((f for f in self.cfg["favorites"] if f["name"] == name), None)
        if not fav or self._loading:
            return
        ids = self.root_w.ids
        self._loading = True
        for k in self.FAV_KEYS:
            if k in fav:
                self.cfg[k] = fav[k]
        self._migrate_voice()
        ids.mode.text = self.cfg["mode"]
        ids.genus.text = self.cfg["genus"]
        for w, n in ((ids.oct_low, "Χαμηλά"), (ids.oct_mid, "Μέση"), (ids.oct_high, "Ψηλά")):
            w.state = "down" if self.cfg["octave"] == n else "normal"
        ids.multi.state = "down" if self.cfg["multi"] else "normal"
        ids.single.state = "normal" if self.cfg["multi"] else "down"
        for i, tb in enumerate(self.attr_btns):
            tb.state = "down" if self.cfg["attr"][i] else "normal"
        self._sync_settings_widgets()
        self._loading = False
        self.active = [tuple(x) for x in fav.get("active", [])]
        ids.fav.text = "Αγαπημένα…"
        self.changed()

    def delete_favorite(self, name):
        self.cfg["favorites"] = [f for f in self.cfg["favorites"] if f["name"] != name]
        self.save()
        self._fav_values()
        self._fav_list()

    def _fav_list(self):
        from kivy.factory import Factory
        box = self.fav_box
        box.clear_widgets()
        for f in self.cfg["favorites"]:
            row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
            row.add_widget(Label(text=f["name"], color=self.c_text, halign="left", valign="middle",
                                 text_size=(Window.width * 0.55, None)))
            dl = Factory.Flat(text="Διαγραφή", size_hint_x=None, width=dp(100))
            dl.bind(on_release=lambda w, n=f["name"]: self.delete_favorite(n))
            row.add_widget(dl)
            box.add_widget(row)

    # ------------------------------------------------------------ ρυθμίσεις
    def _build_settings(self, box):
        from kivy.factory import Factory

        def title(t):
            box.add_widget(Factory.Txt(text=f"[size=17sp][b]{t}[/b][/size]"))

        def line(label, widget, h=48):
            row = BoxLayout(size_hint_y=None, height=dp(h), spacing=dp(8))
            row.add_widget(Factory.Dim(text=label, size_hint_x=0.42, font_size="14sp"))
            widget.size_hint_x = 0.58
            row.add_widget(widget)
            box.add_widget(row)

        def slider(label, mn, mx, val, step, fmt, cb):
            row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
            lab = Factory.Dim(text=label + ": " + fmt(val), size_hint_x=0.42, font_size="14sp")
            s = Factory.Slider(min=mn, max=mx, value=val, step=step, size_hint_x=0.58, value_track=True,
                               value_track_color=self.c_accent)

            def on_val(w, v):
                lab.text = label + ": " + fmt(v)
                cb(v)
            s.bind(value=on_val)
            row.add_widget(lab)
            row.add_widget(s)
            box.add_widget(row)
            return s

        title("Φωνή")
        self.voice_spinner = Factory.DarkSpinner(text=self.cfg["vowel"], values=V.voice_names())
        self.voice_spinner.bind(text=lambda w, v: self._set("vowel", v))
        line("Χροιά", self.voice_spinner)
        self.chorus_btn = Factory.Seg(text="Χορωδία (3 φωνές)", state="down" if self.cfg["chorus"] else "normal")
        self.chorus_btn.bind(state=lambda w, st: self._set("chorus", st == "down"))
        line("Ήχος", self.chorus_btn)
        self.room_spinner = Factory.DarkSpinner(text=self.cfg.get("room", V.DEFAULT_ROOM), values=list(V.ROOMS))
        self.room_spinner.bind(text=lambda w, v: self._set("room", v))
        line("Ακουστική", self.room_spinner)
        slider("Attack", 0.05, 3.0, self.cfg["attack"], 0.05, lambda v: f"{v:.2f} s".replace(".", ","),
               lambda v: self._env("attack", v))
        slider("Release", 0.05, 4.0, self.cfg["release"], 0.05, lambda v: f"{v:.2f} s".replace(".", ","),
               lambda v: self._env("release", v))

        title("Κλίμακα και τονικότητα")
        self.temp_btn = Factory.Seg(text="Συγκερασμένη (ευρωπαϊκή)",
                                    state="down" if self.cfg["tempered"] else "normal")
        self.temp_btn.bind(state=lambda w, st: self._set("tempered", st == "down"))
        line("Κλίμακα", self.temp_btn)
        self.semis_slider = slider("Νη (ημιτόνια)", -12, 12, self.cfg["semis"], 1, lambda v: T.base_name(int(v)),
                                   lambda v: self._set("semis", int(v), delay=True))
        self.moria_slider = slider("Λεπτή ρύθμιση", -6, 6, self.cfg["moria"], 1, lambda v: f"{int(v):+d} μόρια",
                                   lambda v: self._set("moria", int(v), delay=True))
        self.steps_lbl = Factory.Txt(text="", font_size="13sp", color=self.c_dim)
        box.add_widget(self.steps_lbl)

        title("Χρόες")
        box.add_widget(Factory.Txt(text="Εφαρμόζονται πάνω στο διατονικό γένος. Οι τιμές σε μόρια είναι "
                                        "προτεινόμενες: αν το βιβλίο ή ο δάσκαλός σου ορίζει άλλες, διόρθωσέ τες "
                                        "από τις Φθορές και σώσ' τες στα Αγαπημένα.", font_size="13sp",
                                   color=self.c_dim))
        for name, alt in T.CHROES.items():
            b = Factory.Flat(text=name, size_hint_y=None, height=dp(46))
            b.bind(on_release=lambda w, a=alt: self.apply_chroa(a))
            box.add_widget(b)

        title("Έλξεις")
        sz = Factory.DarkSpinner(text=str(self.cfg["attr_size"]), values=["2", "4", "6", "8"])
        sz.bind(text=lambda w, v: self._set("attr_size", int(v)))
        line("Μέγεθος έλξης (μόρια)", sz)
        box.add_widget(Factory.Txt(text="Τα κουμπιά Ζω ύφεση, Βου ύφεση, Γα δίεση, Δι δίεση βρίσκονται στην κύρια "
                                        "οθόνη για άμεση χρήση.", font_size="13sp", color=self.c_dim))

        title("Φθορές (αλλοίωση φθόγγων)")
        self.alter_lbls = []
        for i, name in enumerate(T.NAMES):
            row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
            row.add_widget(Label(text=name, bold=True, font_size="18sp", color=self.c_accent, size_hint_x=0.25))
            minus = Factory.Flat(text="−", font_size="24sp", size_hint_x=0.22)
            lab = Label(text="", color=self.c_text, font_size="16sp", size_hint_x=0.31)
            plus = Factory.Flat(text="+", font_size="24sp", size_hint_x=0.22)
            minus.bind(on_release=lambda w, k=i: self._alter(k, -2))
            plus.bind(on_release=lambda w, k=i: self._alter(k, +2))
            for w in (minus, lab, plus):
                row.add_widget(w)
            box.add_widget(row)
            self.alter_lbls.append(lab)
        reset = Factory.Flat(text="Μηδενισμός φθορών και χρόας", size_hint_y=None, height=dp(46))
        reset.bind(on_release=lambda w: self._alter(None, 0))
        box.add_widget(reset)
        self._alter_labels()

        title("Αγαπημένα")
        box.add_widget(Factory.Txt(text="Σώζει ήχο, γένος, βάση, φθορές, χρόα, έλξεις, φωνή και ποιοι φθόγγοι "
                                        "ηχούν. Τα ανακαλείς από την κύρια οθόνη με ένα πάτημα.", font_size="13sp",
                                   color=self.c_dim))
        fr = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        name_in = Factory.TextInput(hint_text="Όνομα, π.χ. Χερουβικό Β'", multiline=False)
        sv = Factory.Flat(text="Αποθήκευση", size_hint_x=None, width=dp(120))
        sv.bind(on_release=lambda *a: (self.save_favorite(name_in.text), setattr(name_in, "text", "")))
        fr.add_widget(name_in)
        fr.add_widget(sv)
        box.add_widget(fr)
        self.fav_box = BoxLayout(orientation="vertical", size_hint_y=None)
        self.fav_box.bind(minimum_height=self.fav_box.setter("height"))
        box.add_widget(self.fav_box)
        self._fav_list()

        title("Πεντάλ / τηλεχειριστήριο Bluetooth")
        pd = Factory.Seg(text="Ενεργό", state="down" if self.cfg.get("pedal", True) else "normal")
        pd.bind(state=lambda w, st: self._set_plain("pedal", st == "down"))
        line("Χειρισμός με πεντάλ", pd)
        box.add_widget(Factory.Txt(text=(
            "Σύνδεσε από το Bluetooth του κινητού ένα πεντάλ γυρίσματος σελίδων ή ένα μικρό πληκτρολόγιο:\n"
            "• Δεξί / κάτω βέλος / Page Down: επόμενος φθόγγος\n"
            "• Αριστερό / πάνω βέλος / Page Up: προηγούμενος φθόγγος\n"
            "• Space / Enter: σιωπή ή ξανά ο τελευταίος φθόγγος\n"
            "• Πλήκτρα 1–8: Νη έως Νη'"), font_size="13sp", color=self.c_dim))
        self.pedal_lbl = Factory.Txt(text="Πάτα ένα πλήκτρο του πεντάλ για δοκιμή.", font_size="13sp")
        box.add_widget(self.pedal_lbl)

        title("Αντίγραφο ασφαλείας")
        box.add_widget(Factory.Txt(text="Στείλε όλες τις ρυθμίσεις, τα προγράμματα ύμνων και τα αγαπημένα σε email ή "
                                        "Drive, για ασφάλεια ή για μεταφορά σε άλλο κινητό/tablet. (Οι ηχογραφημένες "
                                        "φωνές δεν περιλαμβάνονται.)", font_size="13sp", color=self.c_dim))
        bk = Factory.Flat(text="Αποστολή αντιγράφου", size_hint_y=None, height=dp(48))
        bk.bind(on_release=lambda *a: self.share_text(self.backup_text(), "Αντίγραφο Ισοκράτη"))
        box.add_widget(bk)
        rest_in = Factory.TextInput(hint_text="Επικόλλησε εδώ το αντίγραφο για επαναφορά", multiline=True,
                                    size_hint_y=None, height=dp(90))
        box.add_widget(rest_in)
        rest_msg = Factory.Txt(text="")
        rb = Factory.Flat(text="Επαναφορά", size_hint_y=None, height=dp(48))

        def do_restore(*a):
            try:
                self.restore_text(rest_in.text)
                rest_msg.text = "Έγινε επαναφορά. Κλείσε και άνοιξε την εφαρμογή."
            except Exception as e:  # noqa: BLE001
                rest_msg.text = f"Δεν έγινε επαναφορά: {str(e)[:80]}"
        rb.bind(on_release=do_restore)
        box.add_widget(rb)
        box.add_widget(rest_msg)

        title("Έξοδοι ήχου")
        box.add_widget(Factory.Txt(text=(
            "• Ακουστικά / καλώδιο: έξοδος ήχου ή USB-C (με αντάπτορα).\n"
            "• Bluetooth: σύνδεσε το ηχείο από τις ρυθμίσεις του κινητού.\n"
            "• Κονσόλα ναού (balanced XLR): από την έξοδο του κινητού σε DI box ή κάρτα ήχου USB και από εκεί "
            "με XLR στην κονσόλα.\n• Η οθόνη μένει αναμμένη όσο η εφαρμογή είναι ανοιχτή. Το «Νύχτα» χαμηλώνει "
            "και τη φωτεινότητα."), font_size="13sp", color=self.c_dim))

    def _sync_settings_widgets(self):
        if hasattr(self, "voice_spinner"):
            self.voice_spinner.values = V.voice_names()
            self.voice_spinner.text = self.cfg["vowel"]
            self.chorus_btn.state = "down" if self.cfg["chorus"] else "normal"
            self.temp_btn.state = "down" if self.cfg["tempered"] else "normal"
            self.semis_slider.value = self.cfg["semis"]
            self.moria_slider.value = self.cfg["moria"]
            self._alter_labels()

    def apply_chroa(self, alt):
        self.cfg["genus"] = "Διατονικό"
        self.root_w.ids.genus.text = "Διατονικό"
        self.cfg["alter"] = list(alt)
        self._alter_labels()
        self.changed()

    def _set(self, k, v, delay=False):
        if self._loading or self.cfg.get(k) == v:
            return
        self.cfg[k] = v
        if delay:
            if getattr(self, "_job", None):
                self._job.cancel()
            self._job = Clock.schedule_once(lambda dt: self.changed(), 0.35)
            self.refresh()
        else:
            self.changed()

    def _set_plain(self, k, v):
        self.cfg[k] = v
        self.save()

    def _env(self, k, v):
        self.cfg[k] = float(v)
        setattr(self.engine, k, float(v))
        self.save()

    def _alter(self, idx, delta):
        if idx is None:
            self.cfg["alter"] = [0] * 7
        else:
            a = list(self.cfg["alter"])
            a[idx] = max(-12, min(12, a[idx] + delta))
            self.cfg["alter"] = a
        self._alter_labels()
        self.changed()

    def _alter_labels(self):
        for i, lab in enumerate(getattr(self, "alter_lbls", [])):
            v = self.cfg["alter"][i]
            lab.text = "0" if v == 0 else (f"δίεση +{v}" if v > 0 else f"ύφεση {v}")


if __name__ == "__main__":
    IsokratisApp().run()
