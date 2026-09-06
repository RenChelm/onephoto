"""Full-screen picture viewer.

Photo libraries can hold thousands of items, so instead of a Carousel with
one slide per picture this pages through three reusable panes.  Each pane
shows the cached grid thumbnail immediately and swaps in a larger render as
soon as it arrives, which is what makes flicking through a folder feel like
streaming rather than downloading.
"""

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.graphics.transformation import Matrix
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.scatter import Scatter

from .. import theme as T
from ..cache import load_texture
from .base import Page
from .widgets import Body, Icon, IconButton

FULL_THUMB = "c1600x1600"
GRID_THUMB = "c400x400_Crop"
PAGE_GAP = dp(18)
SWIPE_FRACTION = 0.22
ZOOM_LEVEL = 2.6


class PhotoPane(FloatLayout):
    """One picture, with double-tap zoom."""

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.item = None
        self._key = None
        self.zoomed = False
        self.scatter = Scatter(do_rotation=False, do_translation=False,
                               do_scale=False, scale_min=1.0, scale_max=6.0,
                               auto_bring_to_front=False,
                               size_hint=(None, None))
        self.image = Image(fit_mode="contain", size_hint=(1, 1))
        self.scatter.add_widget(self.image)
        self.add_widget(self.scatter)
        self.spinner = Icon(icon="image", color=T.TEXT_FAINT,
                            size_hint=(None, None), size=(dp(40), dp(40)),
                            pos_hint={"center_x": 0.5, "center_y": 0.5},
                            icon_scale=1.0)
        self.add_widget(self.spinner)
        self.bind(size=self._fit, pos=self._fit)

    def _fit(self, *_args):
        self.scatter.size = self.size
        self.scatter.pos = self.pos
        self.image.pos = (0, 0)      # children of a Scatter use local coords
        self.image.size = self.size

    # -- content -----------------------------------------------------------
    def show(self, item):
        self.reset_zoom()
        self.item = item
        if item is None:
            self.image.texture = None
            self.spinner.opacity = 0
            self._key = None
            return
        self._key = item.id
        self.image.texture = None
        self.spinner.opacity = 1
        cache = self.app.images
        preview = cache.peek("%s:%s" % (item.id, GRID_THUMB))
        if preview:
            load_texture(preview,
                         lambda tex: self._apply(item.id, tex, final=False))
        key = "%s:%s" % (item.id, FULL_THUMB)
        cache.request(key, self.app.graph.thumb_url(item.id, FULL_THUMB),
                      self._on_file)

    def _on_file(self, key, path):
        if self.item is None or not key.startswith(self.item.id):
            return
        if not path:
            self.spinner.opacity = 0 if self.image.texture else 1
            return
        item_id = self.item.id
        load_texture(path, lambda tex: self._apply(item_id, tex, final=True))

    def _apply(self, item_id, texture, final):
        if self.item is None or self.item.id != item_id or texture is None:
            return
        if not final and self.image.texture is not None:
            return                       # a sharper render already landed
        self.image.texture = texture
        self.spinner.opacity = 0

    # -- zoom --------------------------------------------------------------
    def reset_zoom(self):
        self.zoomed = False
        self.scatter.do_translation = False
        self.scatter.do_scale = False
        self.scatter.transform = Matrix()
        self._fit()

    def toggle_zoom(self, touch_pos):
        if self.zoomed:
            self.reset_zoom()
            return
        self.zoomed = True
        self.scatter.do_translation = True
        self.scatter.do_scale = True
        self.scatter.apply_transform(
            Matrix().scale(ZOOM_LEVEL, ZOOM_LEVEL, 1),
            anchor=self.scatter.to_local(*touch_pos))

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if touch.is_double_tap:
            self.toggle_zoom(touch.pos)
            return True
        if self.zoomed:
            return super().on_touch_down(touch)
        return False


class Pager(FloatLayout):
    """Three-pane horizontal pager over a list of DriveItems."""

    offset = NumericProperty(0.0)

    def __init__(self, app, on_change=None, on_tap=None, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.items = []
        self.index = 0
        self.on_change = on_change
        self.on_tap = on_tap
        self.panes = [PhotoPane(app) for _ in range(3)]
        for pane in self.panes:
            self.add_widget(pane)
        self._touch_start = None
        self._moved = 0.0
        self._animating = False
        self.bind(offset=self._layout, size=self._layout, pos=self._layout)

    # -- data --------------------------------------------------------------
    def load(self, items, index):
        self.items = items
        self.index = max(0, min(index, len(items) - 1))
        self.offset = 0
        self._bind_panes()

    def _item(self, index):
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def _bind_panes(self):
        for slot, pane in enumerate(self.panes):
            pane.show(self._item(self.index + slot - 1))
        self._layout()
        if self.on_change:
            self.on_change(self.index, len(self.items))

    def _layout(self, *_args):
        step = self.width + PAGE_GAP
        for slot, pane in enumerate(self.panes):
            pane.size = self.size
            pane.y = self.y
            pane.x = self.x + (slot - 1) * step + self.offset

    # -- paging ------------------------------------------------------------
    def go(self, delta):
        target = self.index + delta
        if not 0 <= target < len(self.items) or self._animating:
            self._settle()
            return
        step = self.width + PAGE_GAP
        self._animating = True
        anim = Animation(offset=-delta * step, d=0.18, t="out_quad")
        anim.bind(on_complete=lambda *_a: self._commit(delta))
        anim.start(self)

    def _commit(self, delta):
        self.index += delta
        self.offset = 0
        if delta > 0:
            self.panes = self.panes[1:] + self.panes[:1]
        elif delta < 0:
            self.panes = self.panes[-1:] + self.panes[:-1]
        self._animating = False
        self._bind_panes()

    def _settle(self):
        self._animating = True
        anim = Animation(offset=0, d=0.15, t="out_quad")
        anim.bind(on_complete=lambda *_a: setattr(self, "_animating", False))
        anim.start(self)

    # -- touch -------------------------------------------------------------
    @property
    def _centre(self):
        return self.panes[1]

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if self._centre.dispatch("on_touch_down", touch):
            return True
        if self._animating:
            return True
        self._touch_start = touch.pos
        self._moved = 0.0
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)
        if self._touch_start is None:
            return True
        dx = touch.x - self._touch_start[0]
        self._moved = max(self._moved, abs(dx) + abs(touch.y -
                                                     self._touch_start[1]))
        # Resist dragging past the first and last picture.
        if (dx > 0 and self.index == 0) or \
           (dx < 0 and self.index >= len(self.items) - 1):
            dx *= 0.35
        self.offset = dx
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        touch.ungrab(self)
        if self._touch_start is None:
            return True
        dx = touch.x - self._touch_start[0]
        self._touch_start = None
        if self._moved < dp(10):
            self.offset = 0
            if self.on_tap:
                self.on_tap()
            return True
        threshold = self.width * SWIPE_FRACTION
        if dx <= -threshold:
            self.go(1)
        elif dx >= threshold:
            self.go(-1)
        else:
            self._settle()
        return True


class ViewerScreen(Page):
    def __init__(self, app, **kwargs):
        super().__init__(name="viewer", **kwargs)
        self.app = app
        self._chrome_visible = True
        with self.canvas.before:
            Color(0, 0, 0, 1)
            self._black = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_black, size=self._sync_black)

        self.pager = Pager(app, on_change=self._on_change,
                           on_tap=self.toggle_chrome)
        self.add_widget(self.pager)

        self.chrome = BoxLayout(size_hint=(1, None), height=dp(56),
                                pos_hint={"top": 1}, padding=(dp(4), 0),
                                spacing=dp(4))
        with self.chrome.canvas.before:
            Color(0, 0, 0, 0.55)
            self._chrome_bg = Rectangle(pos=self.chrome.pos,
                                        size=self.chrome.size)
        self.chrome.bind(pos=self._sync_chrome, size=self._sync_chrome)
        close = IconButton(icon="close", color=(1, 1, 1, 1))
        close.bind(on_release=lambda *_a: self.app.close_viewer())
        self.chrome.add_widget(close)
        self.title = Body(text="", color=(1, 1, 1, 1), font_size=T.FONT_MD,
                          shorten=True, shorten_from="right", max_lines=1)
        self.chrome.add_widget(self.title)
        self.counter = Body(text="", color=T.TEXT_DIM, font_size=T.FONT_SM,
                            halign="right", size_hint_x=None, width=dp(84))
        self.chrome.add_widget(self.counter)
        self.add_widget(self.chrome)

    def _sync_black(self, *_args):
        self._black.pos = self.pos
        self._black.size = self.size

    def _sync_chrome(self, *_args):
        self._chrome_bg.pos = self.chrome.pos
        self._chrome_bg.size = self.chrome.size

    def load(self, items, index):
        self._chrome_visible = True
        self.chrome.opacity = 1
        self.chrome.disabled = False
        Clock.schedule_once(lambda _dt: self.pager.load(items, index), 0)

    def _on_change(self, index, total):
        item = self.pager.items[index] if 0 <= index < total else None
        self.title.text = item.name if item else ""
        self.counter.text = "%d / %d" % (index + 1, total) if total else ""

    def toggle_chrome(self):
        self._chrome_visible = not self._chrome_visible
        Animation.cancel_all(self.chrome)
        self.chrome.disabled = not self._chrome_visible
        Animation(opacity=1 if self._chrome_visible else 0, d=0.15).start(
            self.chrome)

    def handle_back(self):
        centre = self.pager.panes[1]
        if centre.zoomed:
            centre.reset_zoom()
            return True
        self.app.close_viewer()
        return True


__all__ = ["ViewerScreen", "Pager", "PhotoPane"]
