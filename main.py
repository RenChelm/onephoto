# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""OnePhoto -- stream the pictures in your OneDrive.

Entry point for both desktop (``python main.py``) and Android, where
buildozer runs this same file.
"""

import os
import threading

from kivy.utils import platform

if platform not in ("android", "ios"):
    # A desktop run gets a phone-shaped window so the three-per-row grid and
    # the bars look the way they will on a device.  Must happen before the
    # window is created.
    from kivy.config import Config
    Config.set("graphics", "width", "412")
    Config.set("graphics", "height", "880")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import (NoTransition, ScreenManager,
                                    SlideTransition)

from onephoto import __version__, theme as T
from onephoto.auth import Authenticator
from onephoto.cache import ImageCache
from onephoto.config import Config
from onephoto.graph import GraphClient
from onephoto.ui.browser import BrowserScreen
from onephoto.ui.login import LoginScreen
from onephoto.ui.settings import PickerScreen, SettingsScreen
from onephoto.ui.viewer import ViewerScreen
from onephoto.ui.widgets import Toast

KEY_BACK = 27


class OnePhotoApp(App):
    title = "OnePhoto"
    version = __version__

    # -- setup -------------------------------------------------------------
    def build(self):
        Window.clearcolor = T.BG
        data_dir = self.user_data_dir
        os.makedirs(data_dir, exist_ok=True)

        self.prefs = Config(os.path.join(data_dir, "settings.json"))
        self.auth = Authenticator(
            client_id=self.prefs.get("client_id"),
            tenant=self.prefs.get("tenant"),
            token_path=os.path.join(data_dir, "token.json"))
        self.graph = GraphClient(self.auth)
        self.images = ImageCache(
            os.path.join(data_dir, "thumbs"),
            headers_provider=self.graph.headers,
            max_bytes=int(self.prefs.get("thumb_cache_mb", 300)) * 1024 * 1024)
        self.account = {}

        self.manager = ScreenManager(transition=NoTransition())
        self.login = LoginScreen(self)
        self.browser = BrowserScreen(self)
        self.viewer = ViewerScreen(self)
        self.settings_screen = SettingsScreen(self)
        self.picker = PickerScreen(self)
        for screen in (self.login, self.browser, self.viewer,
                       self.settings_screen, self.picker):
            self.manager.add_widget(screen)

        if self.auth.signed_in:
            self.browser.reset_to_start()
            self.manager.current = "browser"
            self.refresh_account()
        else:
            self.manager.current = "login"

        Window.bind(on_keyboard=self._on_keyboard)
        return self.manager

    # -- navigation --------------------------------------------------------
    def _slide(self, name, direction="left"):
        self.manager.transition = SlideTransition(direction=direction,
                                                  duration=0.18)
        self.manager.current = name

    def open_viewer(self, items, index):
        self.viewer.load(items, index)
        self._slide("viewer", "up")

    def close_viewer(self):
        self._slide("browser", "down")

    def open_settings(self):
        self._slide("settings", "left")

    def close_settings(self):
        self._slide("browser", "right")

    def open_picker(self):
        self._slide("picker", "left")

    def close_picker(self):
        self._slide("settings", "right")

    # -- session -----------------------------------------------------------
    def on_signed_in(self):
        self.browser.reset_to_start()
        self.manager.transition = NoTransition()
        self.manager.current = "browser"
        self.refresh_account()

    def refresh_account(self):
        def work():
            try:
                account = self.graph.me()
            except Exception:                          # noqa: BLE001
                return
            Clock.schedule_once(
                lambda _dt: setattr(self, "account", account))

        threading.Thread(target=work, daemon=True).start()

    def require_sign_in(self, message=""):
        if message:
            Toast.show(message)
        self.account = {}
        self.manager.transition = NoTransition()
        self.manager.current = "login"

    def sign_out(self):
        self.auth.sign_out()
        self.images.clear()
        self.browser.stack = []
        self.browser.needs_refresh = True
        self.account = {}
        self.manager.transition = NoTransition()
        self.manager.current = "login"
        Toast.show("Signed out")

    # -- platform ----------------------------------------------------------
    def _on_keyboard(self, _window, key, *_args):
        if key != KEY_BACK:
            return False
        screen = self.manager.current_screen
        handler = getattr(screen, "handle_back", None)
        if handler and handler():
            return True
        return False           # let Android close the app

    def on_pause(self):
        return True

    def on_resume(self):
        return True

    def on_stop(self):
        try:
            self.graph.shutdown()
        except Exception:                              # noqa: BLE001
            pass


if __name__ == "__main__":
    OnePhotoApp().run()
