# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""Sign-in screen driving the OAuth device code flow."""

import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from .. import theme as T
from ..auth import AuthError, AuthPending
from ..device import copy_text, open_url
from .base import Page
from .widgets import Body, Field, Icon, RoundedButton, Toast

DEFAULT_VERIFY_URL = "https://microsoft.com/devicelogin"
SETUP_HELP = ("Register a free app in the Azure portal (App registrations ->"
              " New registration -> Accounts in any organizational directory"
              " and personal Microsoft accounts), turn on \"Allow public"
              " client flows\", then paste its Application (client) ID here.")


class LoginScreen(Page):
    def __init__(self, app, **kwargs):
        super().__init__(name="login", **kwargs)
        self.app = app
        self._flow = None
        self._poll_event = None
        self._stop = threading.Event()
        self._asking_for_id = False

        scroll = ScrollView(do_scroll_x=False)
        root = BoxLayout(orientation="vertical", padding=(dp(24), dp(28)),
                         spacing=dp(14), size_hint_y=None)
        root.bind(minimum_height=root.setter("height"))

        root.add_widget(Icon(icon="cloud", color=T.ACCENT, size_hint_y=None,
                             height=dp(64), icon_scale=0.75))
        root.add_widget(Body(text="OnePhoto", halign="center", bold=True,
                             font_size=T.FONT_XL, size_hint_y=None,
                             height=dp(34)))
        root.add_widget(Body(text="Stream the pictures in your OneDrive",
                             halign="center", color=T.TEXT_DIM,
                             font_size=T.FONT_MD, size_hint_y=None,
                             height=dp(26)))
        root.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # -- client id (only needed until one is stored) --------------------
        self.client_box = BoxLayout(orientation="vertical", spacing=dp(8),
                                    size_hint_y=None, height=dp(140))
        self.client_box.add_widget(Body(
            text="Application (client) ID", color=T.TEXT_DIM,
            font_size=T.FONT_SM, size_hint_y=None, height=dp(20)))
        self.client_field = Field(
            hint_text="00000000-0000-0000-0000-000000000000")
        self.client_box.add_widget(self.client_field)
        self.client_box.add_widget(Body(
            text=SETUP_HELP, color=T.TEXT_FAINT, font_size=T.FONT_XS,
            size_hint_y=None, height=dp(64)))
        root.add_widget(self.client_box)

        # -- device code panel ---------------------------------------------
        self.code_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                  size_hint_y=None, height=dp(0), opacity=0)
        self.verify_label = Body(
            text="1.  Open the sign-in page", color=T.TEXT_DIM,
            font_size=T.FONT_SM, size_hint_y=None, height=dp(22))
        self.code_box.add_widget(self.verify_label)
        self.code_box.add_widget(Body(
            text="2.  Enter this code", color=T.TEXT_DIM,
            font_size=T.FONT_SM, size_hint_y=None, height=dp(22)))
        self.code_label = Body(text="", halign="center", bold=True,
                               font_size=T.FONT_XL, color=T.ACCENT,
                               size_hint_y=None, height=dp(46))
        self.code_box.add_widget(self.code_label)
        root.add_widget(self.code_box)

        self.status = Body(text="", halign="center", color=T.TEXT_DIM,
                           font_size=T.FONT_SM, size_hint_y=None, height=dp(38))
        root.add_widget(self.status)

        self.primary = RoundedButton(text="Sign in with Microsoft",
                                     icon="cloud")
        self.primary.bind(on_release=lambda *_a: self.start())
        root.add_widget(self.primary)

        self.secondary = RoundedButton(text="Open sign-in page", outline=True,
                                       opacity=0, disabled=True, height=0)
        self.secondary.bind(on_release=lambda *_a: self._open_page())
        root.add_widget(self.secondary)

        self.copy_button = RoundedButton(text="Copy code", outline=True,
                                         opacity=0, disabled=True, height=0)
        self.copy_button.bind(on_release=lambda *_a: self._copy())
        root.add_widget(self.copy_button)

        # Personal and work accounts complete on different Microsoft pages,
        # and there is no way to tell which the user has before they start.
        self.kind_button = RoundedButton(text="", outline=True, height=dp(44))
        self.kind_button.bind(on_release=lambda *_a: self.toggle_account_kind())
        root.add_widget(self.kind_button)

        scroll.add_widget(root)
        self.add_widget(scroll)

    # -- lifecycle ---------------------------------------------------------
    @property
    def work_account(self):
        return self.app.prefs.get("tenant") == "organizations"

    def toggle_account_kind(self):
        """Swap between the personal and work/school sign-in authorities."""
        tenant = "consumers" if self.work_account else "organizations"
        self.app.prefs.set("tenant", tenant)
        self.app.auth.tenant = tenant
        self.cancel()
        self._reset()
        Toast.show("Ready for a %s account" %
                   ("work or school" if self.work_account else "personal"))

    def _reset(self):
        """Back to the untouched state, ready to start a fresh flow."""
        self.code_box.height = 0
        self.code_box.opacity = 0
        self.code_label.text = ""
        for button in (self.secondary, self.copy_button):
            button.opacity = 0
            button.disabled = True
            button.height = 0          # collapse, do not just fade
        self.status.text = ""
        self.status.color = T.TEXT_DIM
        self.primary.text = "Sign in with Microsoft"
        self.primary.disabled = False
        self.kind_button.text = ("Use a personal account instead"
                                 if self.work_account else
                                 "Use a work or school account instead")

    def on_pre_enter(self, *_args):
        # A build that carries its own client id shows one button and
        # nothing else; the paste field is only for builds without one.
        needs_id = not self.app.prefs.get("client_id", "")
        self.client_field.text = "" if self.app.prefs.client_id_is_builtin \
            else self.app.prefs.get("client_id", "")
        self._show_client_box(needs_id)
        self._reset()

    def on_leave(self, *_args):
        self.cancel()

    def cancel(self):
        self._stop.set()
        if self._poll_event is not None:
            self._poll_event.cancel()
            self._poll_event = None

    def _show_client_box(self, visible):
        self._asking_for_id = visible
        self.client_box.height = dp(140) if visible else 0
        self.client_box.opacity = 1 if visible else 0
        self.client_box.disabled = not visible

    def _show_code(self, code):
        self.code_label.text = code
        self.code_box.height = dp(96)
        self.code_box.opacity = 1
        for button in (self.secondary, self.copy_button):
            button.opacity = 1
            button.disabled = False
            button.height = dp(46)

    # -- flow --------------------------------------------------------------
    def start(self):
        if self._asking_for_id:
            typed = (self.client_field.text or "").strip()
            if typed:
                self.app.prefs.set("client_id", typed)
        self.app.auth.client_id = self.app.prefs.get("client_id", "")
        if not self.app.auth.client_id:
            self._show_client_box(True)
            self.status.text = "Paste an Application (client) ID first."
            self.status.color = T.DANGER
            return

        self._stop = threading.Event()
        self.primary.disabled = True
        self.primary.text = "Contacting Microsoft..."
        self.status.color = T.TEXT_DIM
        self.status.text = "Requesting a sign-in code..."
        threading.Thread(target=self._begin, daemon=True).start()

    def _begin(self):
        try:
            flow = self.app.auth.begin_device_flow()
        except Exception as exc:                       # noqa: BLE001
            Clock.schedule_once(lambda _dt, e=exc: self._fail(str(e)))
            return
        Clock.schedule_once(lambda _dt: self._flow_started(flow))

    def _flow_started(self, flow):
        self._flow = flow
        self._show_client_box(False)
        self._show_code(flow.get("user_code", ""))
        self.primary.text = "Waiting for sign-in..."
        # Microsoft returns a different page for personal accounts than for
        # work ones, so always show the one it actually handed us.
        url = flow.get("verification_uri") or DEFAULT_VERIFY_URL
        pretty = url.split("://", 1)[-1]
        self.verify_label.text = "1.  Open %s" % pretty
        self.status.text = "Open %s in a browser and enter the code." % pretty
        open_url(url)
        interval = float(flow.get("interval", 5))
        self._poll_event = Clock.schedule_interval(self._poll, interval)

    def _poll(self, _dt):
        if self._stop.is_set():
            return False
        threading.Thread(target=self._poll_once, daemon=True).start()

    def _poll_once(self):
        try:
            done = self.app.auth.poll_device_flow(self._flow)
        except AuthPending:
            return
        except Exception as exc:                       # noqa: BLE001
            Clock.schedule_once(lambda _dt, e=exc: self._fail(str(e)))
            return
        if done:
            Clock.schedule_once(lambda _dt: self._succeed())

    def _succeed(self):
        self.cancel()
        self.status.color = T.TEXT_DIM
        self.status.text = "Signed in."
        self.primary.text = "Signed in"
        self.app.on_signed_in()

    def _fail(self, message):
        self.cancel()
        self.primary.disabled = False
        self.primary.text = "Try again"
        self.status.color = T.DANGER
        self.status.text = message
        # Only offer the paste field to builds that have no id of their own,
        # otherwise a transient error would expose it to end users.
        if not self.app.prefs.client_id_is_builtin and (
                "client" in message.lower() or
                "application" in message.lower()):
            self._show_client_box(True)

    # -- helpers -----------------------------------------------------------
    def _open_page(self):
        url = (self._flow or {}).get("verification_uri") or DEFAULT_VERIFY_URL
        if not open_url(url):
            copy_text(url)
            Toast.show("Link copied: %s" % url)

    def _copy(self):
        code = self.code_label.text
        if code and copy_text(code):
            Toast.show("Code copied")


__all__ = ["LoginScreen", "AuthError"]
