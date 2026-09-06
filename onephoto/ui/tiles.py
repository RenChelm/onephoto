"""RecycleView cells: folder tiles, photo tiles and browser rows.

All three pull their picture through the shared ImageCache, so a cell that
scrolls back into view is repainted from disk instead of the network.  Cells
are recycled, so every async callback re-checks that the tile still shows
the item it was fetched for.
"""

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivy.uix.recycleboxlayout import RecycleBoxLayout

from .. import theme as T
from ..cache import load_texture
from .widgets import Body, Icon, RoundedImage

FOLDER_CAPTION_HEIGHT = dp(40)


class _Thumbed:
    """Shared async-thumbnail plumbing for the three cell types."""

    def _init_thumb(self, image, placeholder):
        self._image = image
        self._placeholder = placeholder
        self._loaded_key = None

    def _sync_image(self):
        key = self.thumb_key or ""
        if key == self._loaded_key and self._image.texture is not None:
            return
        self._loaded_key = key
        self._image.texture = None
        self._placeholder.opacity = 1
        if not key:
            return
        app = App.get_running_app()
        if app is None or getattr(app, "images", None) is None:
            return
        app.images.request(key, self.thumb_url, self._on_file)

    def _on_file(self, key, path):
        if key != (self.thumb_key or ""):
            return                      # the cell was recycled meanwhile
        if not path:
            return                      # keep the placeholder
        load_texture(path, lambda texture: self._on_texture(key, texture))

    def _on_texture(self, key, texture):
        if key != (self.thumb_key or "") or texture is None:
            return
        self._image.texture = texture
        self._placeholder.opacity = 0


class FolderTile(RecycleDataViewBehavior, ButtonBehavior, BoxLayout,
                 _Thumbed):
    """Rounded square cover with the folder name underneath.

    This is the cell used by photo mode, where folders and subfolders are
    flattened onto a single 3-per-row grid.
    """

    item_id = StringProperty("")
    title = StringProperty("")
    subtitle = StringProperty("")
    thumb_key = StringProperty("")
    thumb_url = StringProperty("")
    is_current = BooleanProperty(False)
    index = NumericProperty(0)

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("spacing", dp(6))
        super().__init__(**kwargs)
        self.rv = None

        frame = FloatLayout(size_hint_y=None)
        image = RoundedImage(radius=T.TILE_RADIUS, size_hint=(1, 1),
                             pos_hint={"x": 0, "y": 0})
        placeholder = Icon(icon="folder", color=T.TEXT_FAINT,
                           size_hint=(None, None), size=(dp(40), dp(40)),
                           pos_hint={"center_x": 0.5, "center_y": 0.5},
                           icon_scale=1.0)
        frame.add_widget(image)
        frame.add_widget(placeholder)
        self.add_widget(frame)
        self._frame = frame

        caption = BoxLayout(orientation="vertical", size_hint_y=None,
                            height=FOLDER_CAPTION_HEIGHT,
                            padding=(dp(2), 0, dp(2), 0))
        self._name = Body(font_size=T.FONT_SM, shorten=True,
                          shorten_from="right", max_lines=1)
        self._meta = Body(font_size=T.FONT_XS, color=T.TEXT_DIM, shorten=True,
                          shorten_from="right", max_lines=1)
        caption.add_widget(self._name)
        caption.add_widget(self._meta)
        self.add_widget(caption)

        self._init_thumb(image, placeholder)
        self.bind(width=self._square, title=self._sync_text,
                  subtitle=self._sync_text, is_current=self._sync_text,
                  state=self._sync_press)
        self._square()

    def _square(self, *_args):
        self._frame.height = self.width

    def _sync_text(self, *_args):
        self._name.text = self.title
        self._name.color = T.ACCENT if self.is_current else T.TEXT
        self._meta.text = self.subtitle
        self._placeholder.icon = "image" if self.is_current else "folder"

    def _sync_press(self, *_args):
        self._image.overlay = 0.28 if self.state == "down" else 0.0

    def refresh_view_attrs(self, rv, index, data):
        self.rv = rv
        result = super().refresh_view_attrs(rv, index, data)
        self._sync_image()
        return result

    def on_release(self):
        if self.rv is not None and self.rv.select_callback:
            self.rv.select_callback(self.index)


class PhotoTile(RecycleDataViewBehavior, ButtonBehavior, FloatLayout,
                _Thumbed):
    """Rounded square picture used inside a folder."""

    item_id = StringProperty("")
    thumb_key = StringProperty("")
    thumb_url = StringProperty("")
    title = StringProperty("")
    index = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rv = None
        image = RoundedImage(radius=T.PHOTO_RADIUS, size_hint=(1, 1),
                             pos_hint={"x": 0, "y": 0})
        placeholder = Icon(icon="image", color=T.TEXT_FAINT,
                           size_hint=(None, None), size=(dp(30), dp(30)),
                           pos_hint={"center_x": 0.5, "center_y": 0.5},
                           icon_scale=1.0)
        self.add_widget(image)
        self.add_widget(placeholder)
        self._init_thumb(image, placeholder)
        self.bind(state=self._sync_press)

    def _sync_press(self, *_args):
        self._image.overlay = 0.28 if self.state == "down" else 0.0

    def refresh_view_attrs(self, rv, index, data):
        self.rv = rv
        result = super().refresh_view_attrs(rv, index, data)
        self._sync_image()
        return result

    def on_release(self):
        if self.rv is not None and self.rv.select_callback:
            self.rv.select_callback(self.index)


class EntryRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout, _Thumbed):
    """One line of the classic folder browser."""

    item_id = StringProperty("")
    title = StringProperty("")
    subtitle = StringProperty("")
    thumb_key = StringProperty("")
    thumb_url = StringProperty("")
    kind = StringProperty("folder")      # folder | image | file
    index = NumericProperty(0)

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("spacing", dp(12))
        kwargs.setdefault("padding", (T.PAGE_PAD, dp(6), T.PAGE_PAD, dp(6)))
        super().__init__(**kwargs)
        self.rv = None

        frame = FloatLayout(size_hint=(None, 1), width=dp(46))
        image = RoundedImage(radius=dp(8), size_hint=(1, 1),
                             pos_hint={"x": 0, "y": 0})
        placeholder = Icon(icon="folder", color=T.TEXT_DIM,
                           size_hint=(None, None), size=(dp(26), dp(26)),
                           pos_hint={"center_x": 0.5, "center_y": 0.5},
                           icon_scale=1.0)
        frame.add_widget(image)
        frame.add_widget(placeholder)
        self.add_widget(frame)

        text = BoxLayout(orientation="vertical", padding=(0, dp(10)))
        self._name = Body(font_size=T.FONT_MD, shorten=True,
                          shorten_from="right", max_lines=1)
        self._meta = Body(font_size=T.FONT_XS, color=T.TEXT_DIM, shorten=True,
                          shorten_from="right", max_lines=1)
        text.add_widget(self._name)
        text.add_widget(self._meta)
        self.add_widget(text)

        self._chevron = Icon(icon="chevron", color=T.TEXT_FAINT,
                             size_hint=(None, 1), width=dp(20),
                             icon_scale=0.55)
        self.add_widget(self._chevron)

        self._init_thumb(image, placeholder)
        self.bind(title=self._sync_text, subtitle=self._sync_text,
                  kind=self._sync_text, state=self._sync_press)

    def _sync_text(self, *_args):
        self._name.text = self.title
        self._meta.text = self.subtitle
        is_folder = self.kind == "folder"
        self._placeholder.icon = "folder" if is_folder else (
            "image" if self.kind == "image" else "photos")
        self._image.background = T.SURFACE_HI
        self._chevron.opacity = 1 if is_folder else 0

    def _sync_press(self, *_args):
        self.canvas.before.clear()
        if self.state == "down":
            with self.canvas.before:
                Color(*T.SURFACE_HI)
                Rectangle(pos=self.pos, size=self.size)

    def refresh_view_attrs(self, rv, index, data):
        self.rv = rv
        result = super().refresh_view_attrs(rv, index, data)
        self._sync_image()
        return result

    def on_release(self):
        if self.rv is not None and self.rv.select_callback:
            self.rv.select_callback(self.index)


# ----------------------------------------------------------- containers ---
class TileGrid(RecycleView):
    """Vertically scrolling 3-per-row grid of square tiles."""

    extra_height = NumericProperty(0)

    def __init__(self, viewclass, extra_height=0, **kwargs):
        super().__init__(**kwargs)
        self.select_callback = None
        self.extra_height = extra_height
        self.layout = RecycleGridLayout(
            cols=T.GRID_COLUMNS, default_size=(dp(100), dp(100)),
            default_size_hint=(None, None), size_hint=(1, None),
            spacing=T.GUTTER, padding=[T.PAGE_PAD, T.PAGE_PAD])
        self.layout.bind(minimum_height=self.layout.setter("height"))
        self.add_widget(self.layout)
        # viewclass lives on the layout manager, so it can only be set once
        # the manager has been attached.
        self.viewclass = viewclass
        self.bind(width=self._resize, extra_height=self._resize)
        self._resize()

    def _resize(self, *_args):
        cols = T.GRID_COLUMNS
        inner = self.width - 2 * T.PAGE_PAD - T.GUTTER * (cols - 1)
        side = max(dp(48), inner / float(cols))
        self.layout.default_size = (side, side + self.extra_height)


class EntryList(RecycleView):
    """Vertically scrolling list of browser rows."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.select_callback = None
        self.layout = RecycleBoxLayout(
            orientation="vertical", default_size=(None, T.ROW_HEIGHT),
            default_size_hint=(1, None), size_hint=(1, None))
        self.layout.bind(minimum_height=self.layout.setter("height"))
        self.add_widget(self.layout)
        self.viewclass = EntryRow


__all__ = ["FolderTile", "PhotoTile", "EntryRow", "TileGrid", "EntryList",
           "FOLDER_CAPTION_HEIGHT"]
