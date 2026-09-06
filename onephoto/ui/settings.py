# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""Settings screen and the folder picker used to choose the startup folder."""

import threading

from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from .. import theme as T
from ..config import VIEW_FOLDERS, VIEW_PHOTOS
from ..device import human_size, plural
from ..graph import ROOT_ID
from .base import BottomSheet, Page
from .tiles import EntryList
from .widgets import (Body, Icon, ProgressStrip, RoundedButton,
                      SegmentedControl, Toast, TopBar)


class Card(BoxLayout):
    """Rounded panel grouping related settings."""

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("padding", (0, dp(4)))
        super().__init__(**kwargs)
        self.bind(minimum_height=self.setter("height"), pos=self._redraw,
                  size=self._redraw)
        self._redraw()

    def _redraw(self, *_args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*T.SURFACE)
            RoundedRectangle(pos=self.pos, size=self.size,
                             radius=[dp(16)] * 4)


class SettingRow(ButtonBehavior, BoxLayout):
    """Title plus current value, optionally tappable."""

    def __init__(self, icon, title, value="", danger=False, chevron=True,
                 **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(60))
        kwargs.setdefault("spacing", dp(14))
        kwargs.setdefault("padding", (dp(16), dp(8)))
        super().__init__(**kwargs)
        tint = T.DANGER if danger else T.TEXT
        self.add_widget(Icon(icon=icon, color=tint, size_hint=(None, 1),
                             width=dp(22), icon_scale=0.85))
        text = BoxLayout(orientation="vertical")
        self._title = Body(text=title, color=tint, font_size=T.FONT_MD,
                           shorten=True, shorten_from="right", max_lines=1)
        self._value = Body(text=value, color=T.TEXT_DIM, font_size=T.FONT_XS,
                           shorten=True, shorten_from="left", max_lines=1)
        text.add_widget(self._title)
        text.add_widget(self._value)
        self.add_widget(text)
        self._chevron = Icon(icon="chevron", color=T.TEXT_FAINT,
                             size_hint=(None, 1), width=dp(18),
                             icon_scale=0.55,
                             opacity=1 if chevron else 0)
        self.add_widget(self._chevron)
        self.bind(state=self._redraw, pos=self._redraw, size=self._redraw)

    @property
    def value(self):
        return self._value.text

    @value.setter
    def value(self, text):
        self._value.text = text
        self._value.opacity = 1 if text else 0

    @property
    def title(self):
        return self._title.text

    @title.setter
    def title(self, text):
        self._title.text = text

    def _redraw(self, *_args):
        self.canvas.before.clear()
        if self.state == "down":
            with self.canvas.before:
                Color(*T.SURFACE_HI)
                RoundedRectangle(pos=self.pos, size=self.size,
                                 radius=[dp(10)] * 4)


def _section(text):
    return Body(text=text.upper(), color=T.TEXT_FAINT, font_size=T.FONT_XS,
                bold=True, size_hint_y=None, height=dp(28),
                padding=(dp(6), 0))


class SettingsScreen(Page):
    def __init__(self, app, **kwargs):
        super().__init__(name="settings", **kwargs)
        self.app = app

        root = BoxLayout(orientation="vertical")
        self.bar = TopBar(title="Settings", on_back=app.close_settings)
        root.add_widget(self.bar)

        scroll = ScrollView(do_scroll_x=False)
        body = BoxLayout(orientation="vertical", size_hint_y=None,
                         padding=(T.PAGE_PAD, dp(6), T.PAGE_PAD, dp(24)),
                         spacing=dp(6))
        body.bind(minimum_height=body.setter("height"))

        # -- account --------------------------------------------------------
        body.add_widget(_section("Account"))
        account = Card()
        self.account_row = SettingRow("cloud", "OneDrive", "Loading account...",
                                      chevron=False)
        account.add_widget(self.account_row)
        self.usage_row = SettingRow("photos", "Storage used", "",
                                    chevron=False)
        account.add_widget(self.usage_row)
        sign_out = SettingRow("signout", "Sign out", "", danger=True,
                              chevron=False)
        sign_out.bind(on_release=lambda *_a: self._confirm_sign_out())
        account.add_widget(sign_out)
        body.add_widget(account)

        # -- browsing -------------------------------------------------------
        body.add_widget(_section("Browsing"))
        browsing = Card()
        self.start_row = SettingRow("pin", "Startup folder", "")
        self.start_row.bind(on_release=lambda *_a: app.open_picker())
        browsing.add_widget(self.start_row)
        reset_row = SettingRow("home", "Use the top of my OneDrive", "",
                               chevron=False)
        reset_row.bind(on_release=lambda *_a: self._reset_start())
        browsing.add_widget(reset_row)

        mode_box = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=dp(84), padding=(dp(16), dp(8)),
                             spacing=dp(6))
        mode_box.add_widget(Body(text="Default view", color=T.TEXT,
                                 font_size=T.FONT_MD, size_hint_y=None,
                                 height=dp(22)))
        self.mode_segment = SegmentedControl(
            [(VIEW_FOLDERS, "Folders", "list"),
             (VIEW_PHOTOS, "Photos", "grid")],
            on_change=self._set_mode, height=dp(40))
        mode_box.add_widget(self.mode_segment)
        browsing.add_widget(mode_box)
        body.add_widget(browsing)

        # -- storage --------------------------------------------------------
        body.add_widget(_section("Storage"))
        storage = Card()
        self.cache_row = SettingRow("trash", "Clear cached pictures",
                                    "Measuring...", chevron=False)
        self.cache_row.bind(on_release=lambda *_a: self._clear_cache())
        storage.add_widget(self.cache_row)
        body.add_widget(storage)

        body.add_widget(_section("About"))
        about = Card()
        about.add_widget(SettingRow("image", "OnePhoto",
                                    "Version %s" % app.version,
                                    chevron=False))
        body.add_widget(about)
        body.add_widget(Widget(size_hint_y=None, height=dp(8)))

        scroll.add_widget(body)
        root.add_widget(scroll)
        self.add_widget(root)

    # -- lifecycle ---------------------------------------------------------
    def on_pre_enter(self, *_args):
        start = self.app.prefs.start_folder
        self.start_row.value = start["path"] or start["name"]
        self.start_row.title = "Startup folder: %s" % start["name"]
        self.mode_segment.value = self.app.prefs.get("view_mode")
        account = self.app.account or {}
        if account:
            self.account_row.title = account.get("name", "OneDrive")
            self.account_row.value = account.get("email", "")
        threading.Thread(target=self._load_stats, daemon=True).start()

    def _load_stats(self):
        size = self.app.images.usage()
        Clock.schedule_once(
            lambda _dt: setattr(self.cache_row, "value",
                                "%s on this device" % human_size(size)))
        try:
            usage = self.app.graph.drive_usage()
        except Exception:                              # noqa: BLE001
            return
        text = "%s of %s" % (human_size(usage["used"]),
                             human_size(usage["total"]))
        Clock.schedule_once(lambda _dt: setattr(self.usage_row, "value", text))

    def handle_back(self):
        self.app.close_settings()
        return True

    # -- actions -----------------------------------------------------------
    def _set_mode(self, mode):
        self.app.prefs.set("view_mode", mode)
        self.app.browser.mode = mode
        self.app.browser.segment.value = mode
        self.app.browser.photo_folder = None
        self.app.browser.needs_refresh = True

    def _reset_start(self):
        self.app.prefs.set_start_folder(ROOT_ID, "OneDrive", "/")
        self.on_pre_enter()
        self.app.browser.reset_to_start()
        Toast.show("Startup folder reset to the top of your OneDrive")

    def _clear_cache(self):
        self.app.images.clear()
        self.cache_row.value = "0 B on this device"
        Toast.show("Cached pictures removed")

    def _confirm_sign_out(self):
        BottomSheet("Sign out of OneDrive?", [
            ("signout", "Sign out", self.app.sign_out, True),
            ("close", "Cancel", None),
        ]).open()


class PickerScreen(Page):
    """Browse folders only, to choose which one opens on startup."""

    def __init__(self, app, **kwargs):
        super().__init__(name="picker", **kwargs)
        self.app = app
        self.stack = [{"id": ROOT_ID, "name": "OneDrive", "path": "/"}]
        self._token = 0
        self._folders = []

        root = BoxLayout(orientation="vertical")
        self.bar = TopBar(title="Choose folder", on_back=self.go_back)
        root.add_widget(self.bar)
        self.progress = ProgressStrip()
        root.add_widget(self.progress)
        self.list = EntryList()
        self.list.select_callback = self.on_entry
        root.add_widget(self.list)

        footer = BoxLayout(size_hint_y=None, height=dp(74),
                           padding=(T.PAGE_PAD, dp(12)), spacing=dp(10))
        self.use_button = RoundedButton(text="Open this folder on startup",
                                        icon="pin")
        self.use_button.bind(on_release=lambda *_a: self._choose())
        footer.add_widget(self.use_button)
        root.add_widget(footer)
        self.add_widget(root)

    @property
    def current(self):
        return self.stack[-1]

    def on_pre_enter(self, *_args):
        start = self.app.prefs.start_folder
        self.stack = [{"id": ROOT_ID, "name": "OneDrive", "path": "/"}]
        if start["id"] != ROOT_ID:
            self.stack.append(dict(id=start["id"], name=start["name"],
                                   path=start["path"]))
        self.refresh()

    def refresh(self):
        self._token += 1
        token = self._token
        self.progress.active = True
        self.bar.title = self.current["name"]
        self.bar.subtitle = self.current["path"]
        self.bar.show_back(True)
        threading.Thread(target=self._load, args=(token,), daemon=True).start()

    def _load(self, token):
        try:
            folders, _files = self.app.graph.list_folder(self.current["id"])
        except Exception as exc:                        # noqa: BLE001
            Clock.schedule_once(lambda _dt, e=exc: self._failed(token, str(e)))
            return
        Clock.schedule_once(lambda _dt: self._show(token, folders))

    def _show(self, token, folders):
        if token != self._token:
            return
        self.progress.active = False
        self._folders = folders
        self.list.data = [{
            "item_id": folder.id,
            "title": folder.name,
            "subtitle": plural(folder.child_count, "item"),
            "kind": "folder",
            "thumb_key": "",
            "thumb_url": "",
            "index": index,
        } for index, folder in enumerate(folders)]

    def _failed(self, token, message):
        if token != self._token:
            return
        self.progress.active = False
        Toast.show(message)

    def on_entry(self, index):
        if 0 <= index < len(self._folders):
            folder = self._folders[index]
            self.stack.append({"id": folder.id, "name": folder.name,
                               "path": folder.path})
            self.refresh()

    def go_back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self.refresh()
            return True
        self.app.close_picker()
        return True

    def handle_back(self):
        return self.go_back()

    def _choose(self):
        target = self.current
        self.app.prefs.set_start_folder(target["id"], target["name"],
                                         target["path"])
        self.app.browser.reset_to_start()
        Toast.show("\"%s\" opens on startup" % target["name"])
        self.app.close_picker()


__all__ = ["SettingsScreen", "PickerScreen"]
