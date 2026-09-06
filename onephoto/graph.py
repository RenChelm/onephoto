# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""Microsoft Graph client covering the slice of OneDrive this app needs.

Thumbnails and originals are fetched straight from the Graph *content*
endpoints (``/thumbnails/0/{size}/content``) rather than from the
pre-authenticated URLs returned by ``$expand=thumbnails``.  That keeps
listings small and means a URL never goes stale -- the downloader simply
attaches the current bearer token.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

import requests

from .auth import AuthError

GRAPH = "https://graph.microsoft.com/v1.0"
ROOT_ID = "root"

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif",
    ".tif", ".tiff", ".jfif", ".dng", ".cr2", ".nef", ".arw", ".raf",
}

# Fields needed to render a row or a tile.  Keeping the projection tight
# matters: photo mode walks an entire subtree.
CHILD_SELECT = ("id,name,size,folder,file,image,photo,video,"
                "lastModifiedDateTime,parentReference")

WALK_LIMIT = 1500        # hard cap on folders surfaced in photo mode
WALK_MAX_DEPTH = 12
PAGE_SIZE = 200


class GraphError(Exception):
    pass


class DriveItem:
    """A single OneDrive file or folder."""

    __slots__ = ("id", "name", "size", "is_folder", "child_count", "mime",
                 "modified", "parent_path", "drive_id", "_is_image",
                 "cover_id", "photo_count", "rel_path", "scanned")

    def __init__(self, raw):
        self.id = raw.get("id", "")
        self.name = raw.get("name", "")
        self.size = raw.get("size", 0) or 0
        folder = raw.get("folder")
        self.is_folder = folder is not None
        self.child_count = (folder or {}).get("childCount", 0)
        self.mime = ((raw.get("file") or {}).get("mimeType") or "").lower()
        self.modified = raw.get("lastModifiedDateTime", "")
        parent = raw.get("parentReference") or {}
        self.parent_path = _readable_path(parent.get("path", ""))
        self.drive_id = parent.get("driveId", "")
        self._is_image = bool(raw.get("image") or raw.get("photo"))
        # Filled in by the photo-mode walker.
        self.cover_id = None
        self.photo_count = 0
        self.rel_path = ""
        self.scanned = False

    @property
    def is_image(self):
        if self._is_image:
            return True
        if self.is_folder:
            return False
        if self.mime.startswith("image/"):
            return True
        dot = self.name.rfind(".")
        return dot != -1 and self.name[dot:].lower() in IMAGE_EXTENSIONS

    @property
    def is_video(self):
        return self.mime.startswith("video/")

    @property
    def path(self):
        base = self.parent_path or "/"
        return (base.rstrip("/") + "/" + self.name) or "/"

    def __repr__(self):
        return "<DriveItem %s %r>" % ("dir" if self.is_folder else "file",
                                      self.name)


class FolderScan:
    """Result of listing one folder once."""

    __slots__ = ("subfolders", "cover_id", "photo_count")

    def __init__(self, subfolders, cover_id, photo_count):
        self.subfolders = subfolders
        self.cover_id = cover_id
        self.photo_count = photo_count


class GraphClient:
    def __init__(self, auth, workers=6):
        self.auth = auth
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"
        self.pool = ThreadPoolExecutor(max_workers=workers,
                                       thread_name_prefix="graph")

    # -- plumbing ---------------------------------------------------------
    def headers(self):
        return {"Authorization": "Bearer " + self.auth.access_token()}

    def _request(self, method, url, **kwargs):
        """One Graph call, with token refresh, throttling and retries."""
        kwargs.setdefault("timeout", 45)
        extra = dict(kwargs.pop("headers", None) or {})
        last_error = None
        for attempt in range(4):
            try:
                headers = dict(extra)
                headers.update(self.headers())
                resp = self.session.request(method, url, headers=headers,
                                            **kwargs)
            except AuthError:
                raise
            except requests.RequestException as exc:
                last_error = GraphError("Network error: %s" % exc)
                time.sleep(0.6 * (attempt + 1))
                continue
            if resp.status_code == 401 and attempt == 0:
                self.auth.access_token(force_refresh=True)
                continue
            if resp.status_code in (429, 503, 504):
                delay = _retry_after(resp, 2 * (attempt + 1))
                time.sleep(min(delay, 20))
                last_error = GraphError("OneDrive is throttling requests.")
                continue
            if resp.status_code >= 400:
                raise GraphError(_error_message(resp))
            return resp
        raise last_error or GraphError("Request failed.")

    def _get_json(self, url, params=None):
        return self._request("GET", url, params=params).json()

    # -- account ----------------------------------------------------------
    def me(self):
        data = self._get_json(GRAPH + "/me")
        return {
            "name": data.get("displayName") or "OneDrive user",
            "email": data.get("userPrincipalName") or data.get("mail") or "",
        }

    def drive_usage(self):
        quota = self._get_json(GRAPH + "/me/drive").get("quota") or {}
        return {"used": quota.get("used", 0), "total": quota.get("total", 0)}

    # -- items ------------------------------------------------------------
    @staticmethod
    def item_url(item_id):
        if not item_id or item_id == ROOT_ID:
            return GRAPH + "/me/drive/root"
        return GRAPH + "/me/drive/items/" + item_id

    def get_item(self, item_id):
        return DriveItem(self._get_json(self.item_url(item_id)))

    def list_children(self, item_id, select=CHILD_SELECT, cancel=None):
        """Every child of a folder, following @odata.nextLink."""
        url = self.item_url(item_id) + "/children"
        params = {"$top": PAGE_SIZE, "$select": select}
        items = []
        while url:
            if cancel is not None and cancel.is_set():
                return items
            payload = self._get_json(url, params=params)
            params = None                     # nextLink already carries them
            items.extend(DriveItem(raw) for raw in payload.get("value", []))
            url = payload.get("@odata.nextLink")
        return items

    def list_folder(self, item_id, cancel=None):
        """Children split into (folders, files), each naturally sorted."""
        children = self.list_children(item_id, cancel=cancel)
        folders = sorted((c for c in children if c.is_folder), key=_sort_key)
        files = sorted((c for c in children if not c.is_folder), key=_sort_key)
        return folders, files

    def list_images(self, item_id, cancel=None):
        """Only the pictures sitting directly inside this folder."""
        children = self.list_children(item_id, cancel=cancel)
        return sorted((c for c in children if c.is_image), key=_sort_key)

    def scan_folder(self, item_id, cancel=None):
        """List a folder once, returning its subfolders, cover and photo count."""
        children = self.list_children(item_id, cancel=cancel)
        subfolders = sorted((c for c in children if c.is_folder), key=_sort_key)
        photos = sorted((c for c in children if c.is_image), key=_sort_key)
        return FolderScan(subfolders, photos[0].id if photos else None,
                          len(photos))

    # -- photo mode -------------------------------------------------------
    def walk_folders(self, root_id, on_progress=None, cancel=None,
                     max_depth=WALK_MAX_DEPTH, limit=WALK_LIMIT):
        """Collect every descendant folder of ``root_id``, flattened.

        Photo mode shows folders and subfolders side by side at one level,
        so the tree is walked breadth-first and the result is a flat list.
        Every folder is listed exactly once: that single listing yields its
        subfolders, its direct photo count and the photo used as its tile
        cover.  A folder therefore appears as a tile as soon as its *parent*
        is scanned and gains its cover once it is scanned itself.

        ``on_progress(new_items, updated_items, done, root_scan)`` runs on
        the worker thread after each depth level so the grid can fill in
        gradually.  ``root_scan`` describes the folder the walk started
        from, whose own pictures have no tile of their own.
        """
        root_scan = {"cover_id": None, "photo_count": 0}
        found = []
        pending = [(root_id, "", 0, None)]     # id, relative path, depth, item

        while pending and len(found) < limit:
            if cancel is not None and cancel.is_set():
                break
            jobs = [(rel, depth, item,
                     self.pool.submit(self.scan_folder, fid, cancel))
                    for fid, rel, depth, item in pending]
            new_items, updated, nxt = [], [], []

            for rel, depth, item, future in jobs:
                if cancel is not None and cancel.is_set():
                    break
                try:
                    scan = future.result()
                except (GraphError, AuthError):
                    continue                   # skip folders we cannot read
                if item is None:               # the folder we started from
                    root_scan["cover_id"] = scan.cover_id
                    root_scan["photo_count"] = scan.photo_count
                else:
                    item.cover_id = scan.cover_id
                    item.photo_count = scan.photo_count
                    item.scanned = True
                    updated.append(item)
                for sub in scan.subfolders:
                    if len(found) + len(new_items) >= limit:
                        break
                    sub.rel_path = (rel + "/" + sub.name) if rel else sub.name
                    new_items.append(sub)
                    if depth + 1 < max_depth and sub.child_count:
                        nxt.append((sub.id, sub.rel_path, depth + 1, sub))

            found.extend(new_items)
            if on_progress and (new_items or updated):
                on_progress(new_items, updated, False, root_scan)
            pending = nxt

        if on_progress:
            on_progress([], [], True, root_scan)
        return found, root_scan

    # -- binaries ---------------------------------------------------------
    @staticmethod
    def thumb_url(item_id, size="c400x400_Crop"):
        """Graph renders (and caches) thumbnails server side at any size."""
        return "%s/me/drive/items/%s/thumbnails/0/%s/content" % (
            GRAPH, item_id, size)

    @staticmethod
    def content_url(item_id):
        return "%s/me/drive/items/%s/content" % (GRAPH, item_id)

    def shutdown(self):
        self.pool.shutdown(wait=False)


def _sort_key(item):
    return item.name.lower()


def _retry_after(resp, fallback):
    try:
        return float(resp.headers.get("Retry-After", fallback))
    except (TypeError, ValueError):
        return fallback


def _readable_path(raw_path):
    """'/drive/root:/Pictures/2024' -> '/Pictures/2024'."""
    if not raw_path:
        return "/"
    idx = raw_path.find("root:")
    if idx == -1:
        return "/"
    return unquote(raw_path[idx + len("root:"):]) or "/"


def _error_message(resp):
    try:
        payload = resp.json().get("error", {})
        message = payload.get("message") or payload.get("code")
    except ValueError:
        message = None
    if resp.status_code == 404:
        return "That item no longer exists in OneDrive."
    if resp.status_code == 403:
        return "Access denied for this item."
    return str(message or "OneDrive returned HTTP %s" % resp.status_code)
