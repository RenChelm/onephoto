"""Screen base class and the bottom sheet used for contextual menus."""

from kivy.animation import Animation
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import Screen

from .. import theme as T
from .widgets import Body, Icon


class Page(Screen):
    """Screen painted with the app background colour."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._color = Color(*T.BG)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

    def _sync_bg(self, *_args):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def handle_back(self):
        """Return True if the screen consumed the Android back gesture."""
        return False


class SheetItem(ButtonBehavior, BoxLayout):
    def __init__(self, icon, label, danger=False, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(54))
        kwargs.setdefault("spacing", dp(14))
        kwargs.setdefault("padding", (dp(18), 0))
        super().__init__(**kwargs)
        tint = T.DANGER if danger else T.TEXT
        self.add_widget(Icon(icon=icon, color=tint, size_hint=(None, 1),
                             width=dp(22), icon_scale=0.85))
        self.add_widget(Body(text=label, color=tint, font_size=T.FONT_MD))
        self.bind(state=self._redraw, pos=self._redraw, size=self._redraw)

    def _redraw(self, *_args):
        self.canvas.before.clear()
        if self.state == "down":
            with self.canvas.before:
                Color(*T.SURFACE_HI)
                Rectangle(pos=self.pos, size=self.size)


class BottomSheet(ModalView):
    """Slide-up menu; each entry is (icon, label, callback, danger)."""

    def __init__(self, title, items, **kwargs):
        kwargs.setdefault("size_hint", (1, None))
        kwargs.setdefault("auto_dismiss", True)
        kwargs.setdefault("background_color", (0, 0, 0, 0.55))
        kwargs.setdefault("background", "")
        kwargs.setdefault("overlay_color", T.SCRIM)
        super().__init__(**kwargs)
        body = BoxLayout(orientation="vertical", padding=(0, dp(10), 0, dp(18)))
        header = Body(text=title, color=T.TEXT_DIM, font_size=T.FONT_SM,
                      size_hint_y=None, height=dp(34),
                      padding=(dp(18), 0))
        body.add_widget(header)
        for entry in items:
            icon, label, callback = entry[0], entry[1], entry[2]
            danger = entry[3] if len(entry) > 3 else False
            row = SheetItem(icon, label, danger=danger)
            row.bind(on_release=lambda _w, cb=callback: self._pick(cb))
            body.add_widget(row)
        self.height = dp(44) + dp(54) * len(items) + dp(18)
        self.add_widget(body)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _pick(self, callback):
        self.dismiss()
        if callback:
            callback()

    def _redraw(self, *_args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*T.SURFACE)
            RoundedRectangle(pos=self.pos, size=self.size,
                             radius=[dp(20), dp(20), 0, 0])

    def _align_center(self, *_args):
        # ModalView centres itself; this sheet belongs at the bottom edge.
        self.center_x = Window.width / 2.0
        self.width = Window.width
        if getattr(self, "_is_open", False):
            self.y = 0

    def open(self, *args, **kwargs):
        result = super().open(*args, **kwargs)
        self.y = -self.height
        Animation(y=0, d=0.18, t="out_quad").start(self)
        return result
