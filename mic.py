"""Μικρόφωνο (μόνο Android): ανίχνευση τόνου και ηχογράφηση μέσω της Java κλάσης org.isokratis.Mic."""
from kivy.clock import Clock
from kivy.utils import platform

IS_ANDROID = platform == "android"


class Mic:
    def __init__(self):
        self.j = None

    @staticmethod
    def available():
        return IS_ANDROID

    def start(self, on_ok, on_fail):
        if not IS_ANDROID:
            on_fail("Το μικρόφωνο λειτουργεί μόνο στο κινητό.")
            return
        if self.j is not None:
            on_ok()
            return

        def really_start():
            try:
                from jnius import autoclass
                self.j = autoclass("org.isokratis.Mic")()
                if not self.j.start():
                    self.j = None
                    on_fail("Το μικρόφωνο δεν άνοιξε. Ίσως το χρησιμοποιεί άλλη εφαρμογή.")
                    return
                on_ok()
            except Exception as e:  # noqa: BLE001
                self.j = None
                on_fail(f"Το μικρόφωνο δεν άνοιξε ({str(e)[:60]}).")

        try:
            from android.permissions import Permission, check_permission, request_permissions
            if check_permission(Permission.RECORD_AUDIO):
                really_start()
            else:
                def cb(perms, grants):
                    Clock.schedule_once(lambda dt: really_start() if all(grants) else
                                        on_fail("Δεν δόθηκε άδεια για το μικρόφωνο."))
                request_permissions([Permission.RECORD_AUDIO], cb)
        except Exception:  # noqa: BLE001
            really_start()

    def pitch(self):
        try:
            return float(self.j.getPitch()) if self.j else 0.0
        except Exception:  # noqa: BLE001
            return 0.0

    def level(self):
        try:
            return float(self.j.getLevel()) if self.j else 0.0
        except Exception:  # noqa: BLE001
            return 0.0

    def start_capture(self):
        if self.j:
            self.j.startCapture()

    def stop_capture(self, path):
        return bool(self.j and self.j.stopCapture(path))

    def stop(self):
        if self.j:
            try:
                self.j.stop()
            except Exception:  # noqa: BLE001
                pass
            self.j = None
