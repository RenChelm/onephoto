"""Reusable dark-theme widgets.

Icons are drawn with canvas primitives instead of a glyph font so they look
identical on every Android device regardless of which fonts are installed.
"""

import math

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (Color, Ellipse, Line, Rectangle, RoundedRectangle,
                           Triangle)
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.properties import (BooleanProperty, ColorProperty, NumericProperty,
                             ObjectProperty, StringProperty)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from .. import theme as T


# ---------------------------------------------------------------- icons ---
class Icon(Widget):
    """A vector icon drawn straight onto the widget canvas."""

    icon = StringProperty("folder")
    color = ColorProperty(T.TEXT)
    icon_scale = NumericProperty(0.52)
    line_width = NumericProperty(dp(1.7))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._trigger = Clock.create_trigger(self._draw, -1)
        self.bind(pos=self._trigger, size=self._trigger, icon=self._trigger,
                  color=self._trigger, icon_scale=self._trigger)
        self._trigger()

    def draw_background(self):
        """Hook for subclasses that need something behind the glyph."""

    def _draw(self, *_args):
        self.canvas.clear()
        with self.canvas:
            self.draw_background()
            cx, cy = self.center
            r = min(self.width, self.height) * self.icon_scale / 2.0
            if r <= 0:
                return
            Color(*self.color)
            painter = _PAINTERS.get(self.icon, _paint_folder)
            painter(cx, cy, r, self.line_width)


def _stroke(points, width, close=False):
    Line(points=points, width=width, cap="round", joint="round", close=close)


def _paint_back(cx, cy, r, w):
    _stroke([cx + r * 0.45, cy + r * 0.85, cx - r * 0.4, cy,
             cx + r * 0.45, cy - r * 0.85], w)


def _paint_chevron(cx, cy, r, w):
    _stroke([cx - r * 0.35, cy + r * 0.8, cx + r * 0.35, cy,
             cx - r * 0.35, cy - r * 0.8], w)


def _paint_close(cx, cy, r, w):
    _stroke([cx - r * 0.75, cy - r * 0.75, cx + r * 0.75, cy + r * 0.75], w)
    _stroke([cx - r * 0.75, cy + r * 0.75, cx + r * 0.75, cy - r * 0.75], w)


def _paint_check(cx, cy, r, w):
    _stroke([cx - r * 0.8, cy + r * 0.05, cx - r * 0.2, cy - r * 0.6,
             cx + r * 0.85, cy + r * 0.65], w)


def _paint_list(cx, cy, r, w):
    for dy in (r * 0.72, 0.0, -r * 0.72):
        _stroke([cx - r * 0.95, cy + dy, cx - r * 0.65, cy + dy], w)
        _stroke([cx - r * 0.35, cy + dy, cx + r * 0.95, cy + dy], w)


def _paint_grid(cx, cy, r, _w):
    cell = r * 0.78
    gap = r * 0.2
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = cx + (gap / 2 if sx > 0 else -gap / 2 - cell)
            y = cy + (gap / 2 if sy > 0 else -gap / 2 - cell)
            RoundedRectangle(pos=(x, y), size=(cell, cell),
                             radius=[cell * 0.25])


def _paint_settings(cx, cy, r, w):
    # Sliders: each track is broken where its knob sits.
    knobs = (r * 0.42, -r * 0.38, r * 0.12)
    for index, dy in enumerate((r * 0.72, 0.0, -r * 0.72)):
        knob_x = cx + knobs[index]
        gap = r * 0.32
        _stroke([cx - r, cy + dy, knob_x - gap, cy + dy], w)
        _stroke([knob_x + gap, cy + dy, cx + r, cy + dy], w)
        Line(circle=(knob_x, cy + dy, r * 0.21), width=w)


def _paint_folder(cx, cy, r, _w):
    RoundedRectangle(pos=(cx - r, cy + r * 0.28), size=(r * 0.95, r * 0.55),
                     radius=[r * 0.16])
    RoundedRectangle(pos=(cx - r, cy - r * 0.85), size=(r * 2, r * 1.55),
                     radius=[r * 0.2])


def _paint_image(cx, cy, r, w):
    Line(rounded_rectangle=(cx - r, cy - r * 0.82, r * 2, r * 1.64, r * 0.22),
         width=w)
    knob = r * 0.16
    Ellipse(pos=(cx - r * 0.55 - knob, cy + r * 0.28 - knob),
            size=(knob * 2, knob * 2))
    _stroke([cx - r * 0.85, cy - r * 0.55, cx - r * 0.1, cy + r * 0.2,
             cx + r * 0.35, cy - r * 0.2, cx + r * 0.85, cy - r * 0.55], w)


def _paint_photos(cx, cy, r, w):
    # Two offset frames read as a stack of pictures.
    Line(rounded_rectangle=(cx - r, cy - r * 0.45, r * 1.6, r * 1.3,
                            r * 0.2), width=w)
    Line(rounded_rectangle=(cx - r * 0.6, cy - r, r * 1.6, r * 1.3,
                            r * 0.2), width=w)


def _paint_home(cx, cy, r, w):
    _stroke([cx - r, cy + r * 0.05, cx, cy + r * 0.9, cx + r, cy + r * 0.05], w)
    _stroke([cx - r * 0.72, cy - r * 0.1, cx - r * 0.72, cy - r * 0.85,
             cx + r * 0.72, cy - r * 0.85, cx + r * 0.72, cy - r * 0.1], w)


def _paint_pin(cx, cy, r, w):
    Line(circle=(cx, cy + r * 0.25, r * 0.62), width=w)
    knob = r * 0.2
    Ellipse(pos=(cx - knob, cy + r * 0.25 - knob), size=(knob * 2, knob * 2))
    _stroke([cx, cy - r * 0.37, cx, cy - r], w)


def _paint_refresh(cx, cy, r, w):
    radius = r * 0.78
    Line(circle=(cx, cy, radius, 30, 330), width=w)
    # Arrowhead sitting on the arc, pointing the way it turns.
    angle = math.radians(330)
    px = cx + radius * math.sin(angle)
    py = cy + radius * math.cos(angle)
    tx, ty = math.cos(angle), -math.sin(angle)      # clockwise tangent
    nx, ny = -ty, tx
    Triangle(points=[px + tx * r * 0.36, py + ty * r * 0.36,
                     px + nx * r * 0.22, py + ny * r * 0.22,
                     px - nx * r * 0.22, py - ny * r * 0.22])


def _paint_trash(cx, cy, r, w):
    _stroke([cx - r * 0.85, cy + r * 0.55, cx + r * 0.85, cy + r * 0.55], w)
    _stroke([cx - r * 0.3, cy + r * 0.55, cx - r * 0.3, cy + r * 0.85,
             cx + r * 0.3, cy + r * 0.85, cx + r * 0.3, cy + r * 0.55], w)
    _stroke([cx - r * 0.62, cy + r * 0.55, cx - r * 0.5, cy - r * 0.85,
             cx + r * 0.5, cy - r * 0.85, cx + r * 0.62, cy + r * 0.55], w)


def _paint_signout(cx, cy, r, w):
    _stroke([cx + r * 0.1, cy + r * 0.9, cx - r * 0.85, cy + r * 0.9,
             cx - r * 0.85, cy - r * 0.9, cx + r * 0.1, cy - r * 0.9], w)
    _stroke([cx + r * 0.15, cy, cx + r * 0.9, cy], w)
    _stroke([cx + r * 0.55, cy + r * 0.38, cx + r * 0.92, cy,
             cx + r * 0.55, cy - r * 0.38], w)


def _paint_cloud(cx, cy, r, _w):
    # Overlapping filled shapes union into one cloud silhouette.
    for offset_x, offset_y, size in ((-0.45, -0.02, 0.42), (0.05, 0.22, 0.55),
                                     (0.58, -0.05, 0.4)):
        radius = r * size
        Ellipse(pos=(cx + r * offset_x - radius, cy + r * offset_y - radius),
                size=(radius * 2, radius * 2))
    RoundedRectangle(pos=(cx - r * 0.88, cy - r * 0.46),
                     size=(r * 1.86, r * 0.55), radius=[r * 0.16])


def _paint_dots(cx, cy, r, _w):
    knob = r * 0.17
    for dy in (r * 0.6, 0.0, -r * 0.6):
        Ellipse(pos=(cx - knob, cy + dy - knob), size=(knob * 2, knob * 2))


def _paint_plus(cx, cy, r, w):
    _stroke([cx - r * 0.8, cy, cx + r * 0.8, cy], w)
    _stroke([cx, cy - r * 0.8, cx, cy + r * 0.8], w)


_PAINTERS = {
    "back": _paint_back, "chevron": _paint_chevron, "close": _paint_close,
    "check": _paint_check, "list": _paint_list, "grid": _paint_grid,
    "settings": _paint_settings, "folder": _paint_folder,
    "image": _paint_image, "photos": _paint_photos, "home": _paint_home,
    "pin": _paint_pin, "refresh": _paint_refresh, "trash": _paint_trash,
    "signout": _paint_signout, "cloud": _paint_cloud, "dots": _paint_dots,
    "plus": _paint_plus,
}


class IconButton(ButtonBehavior, Icon):
    """Tappable icon with a circular press highlight."""

    hit_color = ColorProperty(T.SURFACE_PRESS)

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", (dp(44), dp(44)))
        super().__init__(**kwargs)
        self.bind(state=self._trigger)

    def draw_background(self):
        if self.state == "down":
            Color(*self.hit_color)
            radius = min(self.width, self.height) / 2.0
            Ellipse(pos=(self.center_x - radius, self.center_y - radius),
                    size=(radius * 2, radius * 2))


# --------------------------------------------------------------- images ---
def cover_region(texture, width, height):
    """Crop ``texture`` to the aspect of a box so it fills without stretching."""
    tw, th = texture.size
    if not tw or not th or width <= 0 or height <= 0:
        return texture
    scale = max(width / float(tw), height / float(th))
    cw = max(1, min(tw, int(round(width / scale))))
    ch = max(1, min(th, int(round(height / scale))))
    if cw == tw and ch == th:
        return texture
    return texture.get_region((tw - cw) // 2, (th - ch) // 2, cw, ch)


class RoundedImage(Widget):
    """Texture painted into a rounded rectangle, cropped to fill."""

    texture = ObjectProperty(None, allownone=True)
    radius = NumericProperty(T.PHOTO_RADIUS)
    background = ColorProperty(T.SURFACE_HI)
    overlay = NumericProperty(0.0)      # darkening applied while pressed

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._trigger = Clock.create_trigger(self._redraw, -1)
        self.bind(pos=self._trigger, size=self._trigger, texture=self._trigger,
                  radius=self._trigger, background=self._trigger,
                  overlay=self._trigger)
        self._trigger()

    def _redraw(self, *_args):
        self.canvas.clear()
        radii = [self.radius] * 4
        with self.canvas:
            Color(*self.background)
            RoundedRectangle(pos=self.pos, size=self.size, radius=radii)
            if self.texture is not None:
                Color(1, 1, 1, 1)
                RoundedRectangle(
                    pos=self.pos, size=self.size, radius=radii,
                    texture=cover_region(self.texture, self.width, self.height))
            if self.overlay > 0:
                Color(0, 0, 0, self.overlay)
                RoundedRectangle(pos=self.pos, size=self.size, radius=radii)


def _scrim_texture():
    """A one-pixel-wide vertical black gradient, opaque at the bottom."""
    texture = Texture.create(size=(1, 64), colorfmt="rgba")
    buf = bytearray()
    for row in range(64):
        alpha = int(215 * ((63 - row) / 63.0) ** 1.6)
        buf += bytes((0, 0, 0, alpha))
    texture.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    texture.wrap = "clamp_to_edge"
    return texture


SCRIM_TEXTURE = None


def scrim_texture():
    global SCRIM_TEXTURE
    if SCRIM_TEXTURE is None:
        SCRIM_TEXTURE = _scrim_texture()
    return SCRIM_TEXTURE


# ---------------------------------------------------------------- chrome ---
class Surface(Widget):
    """Plain rounded panel used as a background for rows, bars and sheets."""

    bg = ColorProperty(T.SURFACE)
    radius = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._trigger = Clock.create_trigger(self._redraw, -1)
        self.bind(pos=self._trigger, size=self._trigger, bg=self._trigger,
                  radius=self._trigger)
        self._trigger()

    def _redraw(self, *_args):
        self.canvas.clear()
        with self.canvas:
            Color(*self.bg)
            if self.radius:
                RoundedRectangle(pos=self.pos, size=self.size,
                                 radius=[self.radius] * 4)
            else:
                Rectangle(pos=self.pos, size=self.size)


class Body(Label):
    """Label with sane defaults for this theme."""

    def __init__(self, **kwargs):
        kwargs.setdefault("color", T.TEXT)
        kwargs.setdefault("font_size", T.FONT_MD)
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("valign", "middle")
        kwargs.setdefault("markup", False)
        super().__init__(**kwargs)
        self.bind(size=self._sync_text_size)
        self._sync_text_size()

    def _sync_text_size(self, *_args):
        self.text_size = self.size


class RoundedButton(ButtonBehavior, BoxLayout):
    """Filled pill button."""

    text = StringProperty("")
    bg = ColorProperty(T.ACCENT)
    fg = ColorProperty((1, 1, 1, 1))
    radius = NumericProperty(dp(12))
    outline = BooleanProperty(False)
    icon = StringProperty("")

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(48))
        kwargs.setdefault("padding", (dp(16), 0))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)
        self._icon = Icon(size_hint=(None, 1), width=dp(20), icon_scale=0.9)
        self._label = Body(halign="center", font_size=T.FONT_MD, bold=True)
        self.add_widget(self._label)
        self.bind(pos=self._redraw, size=self._redraw, bg=self._redraw,
                  state=self._redraw, radius=self._redraw,
                  outline=self._redraw, text=self._sync, fg=self._sync,
                  icon=self._sync)
        self._sync()
        self._redraw()

    def _sync(self, *_args):
        self._label.text = self.text
        self._label.color = self.fg
        self._icon.color = self.fg
        self._icon.icon = self.icon or "check"
        has_icon = bool(self.icon)
        if has_icon and self._icon.parent is None:
            self.add_widget(self._icon, index=len(self.children))
        elif not has_icon and self._icon.parent is not None:
            self.remove_widget(self._icon)

    def _redraw(self, *_args):
        self.canvas.before.clear()
        pressed = self.state == "down"
        with self.canvas.before:
            if self.outline:
                Color(*(T.SURFACE_PRESS if pressed else T.SURFACE_HI))
                RoundedRectangle(pos=self.pos, size=self.size,
                                 radius=[self.radius] * 4)
                Color(*T.OUTLINE)
                Line(rounded_rectangle=(self.x, self.y, self.width,
                                        self.height, self.radius),
                     width=dp(1))
            else:
                red, green, blue, alpha = self.bg
                shade = 0.82 if pressed else 1.0
                Color(red * shade, green * shade, blue * shade, alpha)
                RoundedRectangle(pos=self.pos, size=self.size,
                                 radius=[self.radius] * 4)


class TopBar(BoxLayout):
    """Back button, title block and trailing actions."""

    title = StringProperty("")
    subtitle = StringProperty("")

    def __init__(self, on_back=None, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", T.BAR_HEIGHT)
        kwargs.setdefault("padding", (dp(4), 0, dp(6), 0))
        kwargs.setdefault("spacing", dp(2))
        super().__init__(**kwargs)
        self.back_button = IconButton(icon="back", color=T.TEXT)
        self.back_button.bind(on_release=lambda *_a: on_back and on_back())
        self.add_widget(self.back_button)

        titles = BoxLayout(orientation="vertical", padding=(dp(6), dp(8)))
        self._title = Body(font_size=T.FONT_LG, bold=True, shorten=True,
                           shorten_from="right", max_lines=1)
        self._subtitle = Body(font_size=T.FONT_SM, color=T.TEXT_DIM,
                              shorten=True, shorten_from="left", max_lines=1)
        titles.add_widget(self._title)
        titles.add_widget(self._subtitle)
        self.add_widget(titles)
        self._titles = titles

        self.actions = BoxLayout(size_hint_x=None, width=0, spacing=dp(2))
        self.add_widget(self.actions)

        self.bind(title=self._sync, subtitle=self._sync)
        self._sync()
        self._redraw()
        self.bind(pos=self._redraw, size=self._redraw)

    def _sync(self, *_args):
        self._title.text = self.title
        self._subtitle.text = self.subtitle
        self._subtitle.size_hint_y = 1 if self.subtitle else 0.001
        self._subtitle.opacity = 1 if self.subtitle else 0

    def _redraw(self, *_args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*T.SURFACE)
            Rectangle(pos=self.pos, size=self.size)
            Color(*T.OUTLINE)
            Rectangle(pos=(self.x, self.y), size=(self.width, dp(1)))

    def add_action(self, icon, callback, color=None):
        button = IconButton(icon=icon, color=color or T.TEXT)
        button.bind(on_release=lambda *_a: callback())
        self.actions.add_widget(button)
        self.actions.width = len(self.actions.children) * dp(44)
        return button

    def clear_actions(self):
        self.actions.clear_widgets()
        self.actions.width = 0

    def show_back(self, visible):
        self.back_button.opacity = 1 if visible else 0
        self.back_button.disabled = not visible
        self.back_button.width = dp(44) if visible else dp(8)


class SegmentedControl(BoxLayout):
    """Two-way switch used for the view-mode toggle."""

    value = StringProperty("")

    def __init__(self, options, on_change=None, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(40))
        kwargs.setdefault("spacing", dp(4))
        kwargs.setdefault("padding", dp(4))
        super().__init__(**kwargs)
        self._on_change = on_change
        self._buttons = {}
        for key, label, icon in options:
            button = _Segment(text=label, icon=icon)
            button.bind(on_release=lambda _b, k=key: self.select(k))
            self._buttons[key] = button
            self.add_widget(button)
        self.bind(value=self._sync, pos=self._redraw, size=self._redraw)
        self._redraw()

    def select(self, key):
        if self.value != key:
            self.value = key
            if self._on_change:
                self._on_change(key)
        else:
            self._sync()

    def _sync(self, *_args):
        for key, button in self._buttons.items():
            button.active = key == self.value

    def _redraw(self, *_args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*T.SURFACE_HI)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)] * 4)


class _Segment(ButtonBehavior, BoxLayout):
    text = StringProperty("")
    icon = StringProperty("")
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        kwargs.setdefault("spacing", dp(6))
        kwargs.setdefault("padding", (dp(10), 0))
        super().__init__(**kwargs)
        self._icon = Icon(size_hint=(None, 1), width=dp(18), icon_scale=0.9)
        self._label = Body(halign="center", font_size=T.FONT_SM, bold=True)
        self.add_widget(self._icon)
        self.add_widget(self._label)
        self.bind(text=self._sync, icon=self._sync, active=self._sync,
                  pos=self._redraw, size=self._redraw)
        self.bind(active=self._redraw)
        self._sync()
        self._redraw()

    def _sync(self, *_args):
        self._label.text = self.text
        self._icon.icon = self.icon or "grid"
        tint = T.TEXT if self.active else T.TEXT_DIM
        self._label.color = tint
        self._icon.color = tint

    def _redraw(self, *_args):
        self.canvas.before.clear()
        with self.canvas.before:
            if self.active:
                Color(*T.SURFACE_PRESS)
                RoundedRectangle(pos=self.pos, size=self.size,
                                 radius=[dp(9)] * 4)


class Field(TextInput):
    """Single-line dark text input."""

    def __init__(self, **kwargs):
        kwargs.setdefault("multiline", False)
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(46))
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("foreground_color", T.TEXT)
        kwargs.setdefault("cursor_color", T.ACCENT)
        kwargs.setdefault("hint_text_color", T.TEXT_FAINT)
        kwargs.setdefault("selection_color", T.ACCENT_DIM)
        kwargs.setdefault("font_size", T.FONT_MD)
        kwargs.setdefault("padding", (dp(12), dp(12)))
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, focus=self._redraw)
        self._redraw()

    def _redraw(self, *_args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*T.SURFACE_HI)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)] * 4)
            Color(*(T.ACCENT if self.focus else T.OUTLINE))
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height,
                                    dp(10)), width=dp(1))


class EmptyState(BoxLayout):
    """Centred icon + message shown when a listing has nothing in it."""

    def __init__(self, icon="image", title="Nothing here", detail="", **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("spacing", dp(10))
        kwargs.setdefault("padding", dp(32))
        super().__init__(**kwargs)
        self.add_widget(Widget())
        glyph = Icon(icon=icon, color=T.TEXT_FAINT, size_hint=(1, None),
                     height=dp(56), icon_scale=0.8)
        self.add_widget(glyph)
        self._title = Body(text=title, halign="center", font_size=T.FONT_LG,
                           color=T.TEXT_DIM, size_hint_y=None, height=dp(26))
        self._detail = Body(text=detail, halign="center", font_size=T.FONT_SM,
                            color=T.TEXT_FAINT, size_hint_y=None, height=dp(40))
        self.add_widget(self._title)
        self.add_widget(self._detail)
        self.add_widget(Widget())

    def update(self, title=None, detail=None):
        if title is not None:
            self._title.text = title
        if detail is not None:
            self._detail.text = detail


class ProgressStrip(Widget):
    """Thin indeterminate bar shown while a folder is loading."""

    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(2))
        super().__init__(**kwargs)
        self._offset = 0.0
        self._event = None
        self.bind(pos=self._redraw, size=self._redraw, active=self._toggle)
        self._redraw()

    def _toggle(self, *_args):
        if self.active and self._event is None:
            self._event = Clock.schedule_interval(self._tick, 1 / 30.0)
        elif not self.active and self._event is not None:
            self._event.cancel()
            self._event = None
        self._redraw()

    def _tick(self, dt):
        self._offset = (self._offset + dt * 0.9) % 1.4
        self._redraw()

    def _redraw(self, *_args):
        self.canvas.clear()
        if not self.active:
            return
        with self.canvas:
            Color(*T.ACCENT_DIM)
            Rectangle(pos=self.pos, size=self.size)
            Color(*T.ACCENT)
            span = self.width * 0.35
            x = self.x - span + self._offset * (self.width + span) / 1.4
            start = max(self.x, x)
            end = min(self.right, x + span)
            if end > start:
                Rectangle(pos=(start, self.y), size=(end - start, self.height))


class Toast(Body):
    """Short-lived message pinned near the bottom of the window."""

    _current = None

    def __init__(self, text, **kwargs):
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("font_size", T.FONT_SM)
        kwargs.setdefault("size_hint", (None, None))
        super().__init__(text=text, **kwargs)
        self.texture_update()
        self.size = (min(Window.width - dp(48), self.texture_size[0] + dp(32)),
                     self.texture_size[1] + dp(22))
        self.text_size = (self.width - dp(24), None)
        self.texture_update()
        self.center_x = Window.width / 2.0
        self.y = dp(72)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.16, 0.16, 0.2, 0.96)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)] * 4)

    @classmethod
    def show(cls, text, duration=2.4):
        if cls._current is not None and cls._current.parent:
            cls._current.parent.remove_widget(cls._current)
        toast = cls(text)
        cls._current = toast
        Window.add_widget(toast)
        Animation.cancel_all(toast)
        toast.opacity = 0
        Animation(opacity=1, d=0.15).start(toast)
        Clock.schedule_once(lambda _dt: cls._dismiss(toast), duration)
        return toast

    @classmethod
    def _dismiss(cls, toast):
        anim = Animation(opacity=0, d=0.25)
        anim.bind(on_complete=lambda *_a: toast.parent
                  and toast.parent.remove_widget(toast))
        anim.start(toast)


__all__ = ["Icon", "IconButton", "RoundedImage", "Surface", "Body",
           "RoundedButton", "TopBar", "SegmentedControl", "Field",
           "EmptyState", "ProgressStrip", "Toast", "cover_region",
           "scrim_texture"]
