# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""The main screen: the folder browser and the photo-first grid.

Two view modes share one screen because they share one navigation stack:

* **Folders** -- the classic layout.  Subfolders and files of the current
  folder as a list; tapping a folder opens it.
* **Photos** -- every folder *and subfolder* below the current one is
  flattened onto a single three-per-row grid of rounded square tiles.  The
  tiles show folders only, never their contents.  Tapping one opens just
  that folder's own pictures -- its subfolders are not shown again, they
  already have tiles of their own.
"""

import threading

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout

from .. import theme as T
from ..config import VIEW_FOLDERS, VIEW_PHOTOS
from ..device import human_size, plural
from ..auth import AuthError
from ..graph import GraphError, ROOT_ID
from .base import BottomSheet, Page
from .tiles import (FOLDER_CAPTION_HEIGHT, EntryList, FolderTile, PhotoTile,
                    TileGrid)
from .widgets import (Body, EmptyState, ProgressStrip, SegmentedControl,
                      Toast, TopBar)

GRID_THUMB = "c400x400_Crop"
ROW_THUMB = "c128x128_Crop"


class BrowserScreen(Page):
    def __init__(self, app, **kwargs):
        super().__init__(name="browser", **kwargs)
        self.app = app
        self.stack = []              # folder-mode breadcrumb of dicts
        self.photo_folder = None     # folder opened from the photo grid
        self.mode = app.prefs.get("view_mode", VIEW_FOLDERS)
        self.needs_refresh = True
        self._token = 0
        self._cancel = threading.Event()
        self._images = []            # DriveItems backing the photo grid
        self._folders = []           # DriveItems backing the folder grid
        self._rows = []              # row dicts backing the folder-mode list
        self._folder_rows = []
        self._file_rows = []

        root = BoxLayout(orientation="vertical")
        self.bar = TopBar(on_back=self.go_back)
        self.bar.add_action("pin", self.pin_current)
        self.bar.add_action("dots", self.open_menu)
        root.add_widget(self.bar)

        tools = BoxLayout(size_hint_y=None, height=dp(48),
                          padding=(T.PAGE_PAD, dp(5)), spacing=dp(10))
        self.segment = SegmentedControl(
            [(VIEW_FOLDERS, "Folders", "list"), (VIEW_PHOTOS, "Photos", "grid")],
            on_change=self.set_mode, size_hint_x=None, width=dp(184),
            height=dp(38))
        tools.add_widget(self.segment)
        self.count_label = Body(text="", halign="right", color=T.TEXT_DIM,
                                font_size=T.FONT_SM)
        tools.add_widget(self.count_label)
        root.add_widget(tools)

        self.progress = ProgressStrip()
        root.add_widget(self.progress)

        self.content = FloatLayout()
        root.add_widget(self.content)
        self.add_widget(root)

        self.entry_list = EntryList()
        self.entry_list.select_callback = self.on_entry
        self.folder_grid = TileGrid(FolderTile,
                                    extra_height=FOLDER_CAPTION_HEIGHT + dp(6))
        self.folder_grid.select_callback = self.on_folder_tile
        self.photo_grid = TileGrid(PhotoTile)
        self.photo_grid.select_callback = self.on_photo
        self.empty = EmptyState()
        self._current_view = None

        self.segment.value = self.mode

    # -- navigation state --------------------------------------------------
    @property
    def current(self):
        return self.stack[-1] if self.stack else {"id": ROOT_ID,
                                                  "name": "OneDrive",
                                                  "path": "/"}

    def reset_to_start(self):
        start = self.app.prefs.start_folder
        self.stack = [{"id": start["id"], "name": start["name"],
                       "path": start["path"]}]
        self.photo_folder = None
        self.needs_refresh = True

    def on_pre_enter(self, *_args):
        if not self.stack:
            self.reset_to_start()
        if self.mode != self.app.prefs.get("view_mode"):
            self.mode = self.app.prefs.get("view_mode")
            self.segment.value = self.mode
        if self.needs_refresh:
            self.refresh()

    def handle_back(self):
        return self.go_back()

    def go_back(self):
        if self.photo_folder is not None:
            self.photo_folder = None
            self.refresh()
            return True
        if len(self.stack) > 1:
            self.stack.pop()
            self.refresh()
            return True
        return False

    def set_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        self.photo_folder = None
        self.app.prefs.set("view_mode", mode)
        self.refresh()

    # -- loading -----------------------------------------------------------
    def refresh(self, *_args):
        self.needs_refresh = False
        self._token += 1
        token = self._token
        self._cancel.set()
        self._cancel = threading.Event()
        self.app.images.invalidate_pending()
        self._images = []
        self._folders = []
        self.progress.active = True
        self._sync_bar()
        threading.Thread(target=self._load, args=(token, self._cancel),
                         daemon=True).start()

    def _load(self, token, cancel):
        graph = self.app.graph
        try:
            if self.mode == VIEW_PHOTOS and self.photo_folder is None:
                graph.walk_folders(
                    self.current["id"], cancel=cancel,
                    on_progress=lambda new, upd, done, root: self._post(
                        token, self._walk_progress, new, upd, done, root))
                return
            if self.mode == VIEW_PHOTOS:
                images = graph.list_images(self.photo_folder["id"],
                                           cancel=cancel)
                self._post(token, self._show_photos, images)
                return
            folders, files = graph.list_folder(self.current["id"],
                                               cancel=cancel)
            self._post(token, self._show_entries, folders, files)
        except AuthError as exc:
            self._post(token, self.app.require_sign_in, str(exc))
        except GraphError as exc:
            self._post(token, self._show_error, str(exc))
        except Exception as exc:                        # noqa: BLE001
            self._post(token, self._show_error, str(exc))

    def _post(self, token, func, *args):
        """Hop back to the Kivy thread, dropping results from stale loads."""
        def run(_dt):
            if token == self._token:
                func(*args)
        Clock.schedule_once(run, 0)

    # -- photo mode: flattened folder grid ---------------------------------
    def _walk_progress(self, new_items, updated, done, root_scan):
        if new_items:
            self._folders.extend(new_items)
        if new_items or updated or done:
            self._render_folder_grid(root_scan)
        if done:
            self.progress.active = False
            if not self._folders and not root_scan.get("photo_count"):
                self._show_empty(
                    "folder", "No folders in here",
                    "Photos view lists the folders below \"%s\". Switch to "
                    "Folders to browse this one directly."
                    % self.current["name"])

    def _render_folder_grid(self, root_scan):
        data = []
        if root_scan.get("photo_count"):
            # Pictures sitting loose in the browsed folder have no tile of
            # their own, so give them one and mark it as the current folder.
            cover = root_scan.get("cover_id")
            data.append({
                "item_id": self.current["id"],
                "title": "This folder",
                "subtitle": plural(root_scan["photo_count"], "photo"),
                "thumb_key": _thumb_key(cover, GRID_THUMB),
                "thumb_url": _thumb_url(self.app, cover, GRID_THUMB),
                "is_current": True,
                "index": 0,
            })
        for folder in self._folders:
            data.append({
                "item_id": folder.id,
                "title": folder.name,
                "subtitle": _folder_subtitle(folder),
                "thumb_key": _thumb_key(folder.cover_id, GRID_THUMB),
                "thumb_url": _thumb_url(self.app, folder.cover_id, GRID_THUMB),
                "is_current": False,
                "index": len(data),
            })
        for index, entry in enumerate(data):
            entry["index"] = index
        self.folder_grid.data = data
        self._set_view(self.folder_grid)
        self.count_label.text = plural(len(self._folders), "folder")
        self._sync_bar()

    def on_folder_tile(self, index):
        data = self.folder_grid.data
        if index >= len(data):
            return
        entry = data[index]
        if entry.get("is_current"):
            self.photo_folder = {"id": self.current["id"],
                                 "name": self.current["name"],
                                 "path": self.current["path"]}
        else:
            offset = index - (1 if data and data[0].get("is_current") else 0)
            if offset < 0 or offset >= len(self._folders):
                return
            folder = self._folders[offset]
            self.photo_folder = {"id": folder.id, "name": folder.name,
                                 "path": folder.rel_path or folder.name}
        self.refresh()

    # -- photo mode: one folder's pictures ---------------------------------
    def _show_photos(self, images):
        self.progress.active = False
        self._images = images
        self.photo_grid.data = [{
            "item_id": item.id,
            "title": item.name,
            "thumb_key": _thumb_key(item.id, GRID_THUMB),
            "thumb_url": _thumb_url(self.app, item.id, GRID_THUMB),
            "index": index,
        } for index, item in enumerate(images)]
        self.count_label.text = plural(len(images), "photo")
        self._sync_bar()
        if not images:
            self._show_empty("image", "No pictures here",
                             "This folder has no photos of its own.")
        else:
            self._set_view(self.photo_grid)

    def on_photo(self, index):
        if 0 <= index < len(self._images):
            self.app.open_viewer(self._images, index)

    # -- folder mode -------------------------------------------------------
    def _show_entries(self, folders, files):
        self.progress.active = False
        self._images = [f for f in files if f.is_image]
        rows = []
        for folder in folders:
            rows.append({
                "item_id": folder.id,
                "title": folder.name,
                "subtitle": plural(folder.child_count, "item"),
                "kind": "folder",
                "thumb_key": "",
                "thumb_url": "",
                "index": len(rows),
            })
        for item in files:
            is_image = item.is_image
            rows.append({
                "item_id": item.id,
                "title": item.name,
                "subtitle": human_size(item.size),
                "kind": "image" if is_image else "file",
                "thumb_key": _thumb_key(item.id, ROW_THUMB) if is_image else "",
                "thumb_url": (_thumb_url(self.app, item.id, ROW_THUMB)
                              if is_image else ""),
                "index": len(rows),
            })
        self.entry_list.data = rows
        self._rows = rows
        self._folder_rows = folders
        self._file_rows = files
        parts = []
        if folders:
            parts.append(plural(len(folders), "folder"))
        if files:
            parts.append(plural(len(files), "file"))
        self.count_label.text = "  ".join(parts)
        self._sync_bar()
        if not rows:
            self._show_empty("folder", "This folder is empty", "")
        else:
            self._set_view(self.entry_list)

    def on_entry(self, index):
        rows = getattr(self, "_rows", [])
        if index >= len(rows):
            return
        row = rows[index]
        if row["kind"] == "folder":
            folder = self._folder_rows[index]
            self.stack.append({"id": folder.id, "name": folder.name,
                               "path": folder.path})
            self.refresh()
        elif row["kind"] == "image":
            item_id = row["item_id"]
            for position, item in enumerate(self._images):
                if item.id == item_id:
                    self.app.open_viewer(self._images, position)
                    break
        else:
            Toast.show("%s is not a picture" % row["title"])

    # -- chrome ------------------------------------------------------------
    def _set_view(self, widget):
        if self._current_view is widget:
            return
        self.content.clear_widgets()
        self.content.add_widget(widget)
        self._current_view = widget

    def _show_empty(self, icon, title, detail):
        self.empty = EmptyState(icon=icon, title=title, detail=detail)
        self.content.clear_widgets()
        self.content.add_widget(self.empty)
        self._current_view = self.empty

    def _show_error(self, message):
        self.progress.active = False
        self._show_empty("cloud", "Could not load this folder", message)
        self.count_label.text = ""

    def _sync_bar(self):
        if self.mode == VIEW_PHOTOS and self.photo_folder is not None:
            self.bar.title = self.photo_folder["name"]
            self.bar.subtitle = self.photo_folder["path"]
        elif self.mode == VIEW_PHOTOS:
            self.bar.title = self.current["name"]
            self.bar.subtitle = "All folders below %s" % self.current["path"]
        else:
            self.bar.title = self.current["name"]
            self.bar.subtitle = self.current["path"]
        self.bar.show_back(self.photo_folder is not None or len(self.stack) > 1)

    # -- actions -----------------------------------------------------------
    def _pin_target(self):
        if self.mode == VIEW_PHOTOS and self.photo_folder is not None:
            return self.photo_folder
        return self.current

    def pin_current(self):
        target = self._pin_target()
        self.app.prefs.set_start_folder(target["id"], target["name"],
                                         target.get("path", "/"))
        Toast.show("\"%s\" opens on startup" % target["name"])

    def go_home(self):
        self.reset_to_start()
        self.refresh()

    def open_menu(self):
        target = self._pin_target()
        BottomSheet(target.get("path", "/"), [
            ("pin", "Set \"%s\" as startup folder" % target["name"],
             self.pin_current),
            ("home", "Go to startup folder", self.go_home),
            ("refresh", "Reload", self.refresh),
            ("settings", "Settings", self.app.open_settings),
        ]).open()


def _folder_subtitle(folder):
    if not folder.scanned:
        return "..."
    bits = []
    if folder.photo_count:
        bits.append(plural(folder.photo_count, "photo"))
    if not bits:
        bits.append("no photos")
    return "  ".join(bits)


def _thumb_key(item_id, size):
    return "%s:%s" % (item_id, size) if item_id else ""


def _thumb_url(app, item_id, size):
    return app.graph.thumb_url(item_id, size) if item_id else ""


__all__ = ["BrowserScreen"]
