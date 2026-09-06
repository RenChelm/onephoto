# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""An offline stand-in for OneDrive, shared by the preview and self-test.

It subclasses the real GraphClient and ImageCache and replaces only the two
network seams -- listing children and fetching bytes -- so folder walking,
caching, layout and rendering all run the real code paths.
"""

import os
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from onephoto.cache import ImageCache
from onephoto.graph import DriveItem, GraphClient

WORK = tempfile.mkdtemp(prefix="onephoto-fake-")

PALETTES = [
    ((32, 58, 96), (120, 180, 220)), ((92, 42, 60), (232, 168, 130)),
    ((28, 84, 68), (168, 224, 150)), ((70, 52, 110), (206, 160, 240)),
    ((104, 74, 26), (240, 210, 130)), ((26, 62, 82), (150, 214, 232)),
]

# folder -> subfolders
TREE = {
    "Pictures": ["2024", "2023", "Screenshots", "Wallpapers"],
    "2024": ["Iceland", "Tokyo", "Studio"],
    "2023": ["Wedding", "Garden"],
    "Iceland": ["Reykjavik", "Vestrahorn"],
    "Tokyo": [], "Studio": [], "Wedding": [], "Garden": [],
    "Screenshots": [], "Wallpapers": [], "Reykjavik": [], "Vestrahorn": [],
}
# folder -> number of pictures sitting directly inside it
PHOTO_COUNTS = {"Pictures": 3, "2024": 0, "2023": 2, "Iceland": 6, "Tokyo": 21,
                "Studio": 9, "Wedding": 14, "Garden": 5, "Screenshots": 11,
                "Wallpapers": 7, "Reykjavik": 12, "Vestrahorn": 8}


def build_sample(with_images=True):
    """Return (children by folder id, item id -> local JPEG path)."""
    children = {}
    sources = {}
    counter = [0]

    def make_image(item_id, seed):
        if not with_images:
            return
        from PIL import Image, ImageDraw
        top, bottom = PALETTES[seed % len(PALETTES)]
        width, height = (900, 640) if seed % 3 else (640, 900)
        image = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(image)
        for y in range(height):
            ratio = y / float(height - 1)
            draw.line([(0, y), (width, y)],
                      fill=tuple(int(top[i] + (bottom[i] - top[i]) * ratio)
                                 for i in range(3)))
        for ring in range(4):
            inset = 60 + ring * 55 + (seed % 5) * 12
            draw.ellipse([inset, inset, width - inset, height - inset],
                         outline=(255, 255, 255), width=6)
        path = os.path.join(WORK, "%s.jpg" % item_id)
        image.save(path, "JPEG", quality=88)
        sources[item_id] = path

    def add_folder(name, parent_path):
        raw = {"id": name, "name": name,
               "folder": {"childCount": len(TREE.get(name, [])) +
                          PHOTO_COUNTS.get(name, 0)},
               "parentReference": {"path": "/drive/root:%s" % parent_path}}
        kids = []
        here = "%s/%s" % (parent_path.rstrip("/"), name)
        for sub in TREE.get(name, []):
            kids.append(add_folder(sub, here))
        for index in range(PHOTO_COUNTS.get(name, 0)):
            counter[0] += 1
            photo_id = "img%03d" % counter[0]
            make_image(photo_id, counter[0])
            kids.append({
                "id": photo_id,
                "name": "%s-%04d.jpg" % (name.lower(), index + 1),
                "size": 2_400_000 + index * 91_000,
                "file": {"mimeType": "image/jpeg"}, "image": {"width": 900},
                "lastModifiedDateTime": "2024-06-0%dT10:00:00Z"
                                        % (index % 9 + 1),
                "parentReference": {"path": "/drive/root:%s" % here}})
        children[name] = kids
        return raw

    root_kids = [add_folder("Pictures", "/")]
    root_kids.append({"id": "Documents", "name": "Documents",
                      "folder": {"childCount": 1},
                      "parentReference": {"path": "/drive/root:"}})
    children["Documents"] = [
        {"id": "doc1", "name": "Notes.txt", "size": 8100,
         "file": {"mimeType": "text/plain"},
         "parentReference": {"path": "/drive/root:/Documents"}}]
    for index in range(2):
        counter[0] += 1
        photo_id = "img%03d" % counter[0]
        make_image(photo_id, counter[0])
        root_kids.append({
            "id": photo_id, "name": "onedrive-%d.jpg" % (index + 1),
            "size": 1_800_000, "file": {"mimeType": "image/jpeg"},
            "image": {"width": 900},
            "parentReference": {"path": "/drive/root:"}})
    children["root"] = root_kids
    return children, sources


class FakeGraph(GraphClient):
    """The real client with its HTTP listing swapped for the sample tree."""

    def __init__(self, children, latency=0.02):
        self.auth = None
        self.session = None
        self.latency = latency
        self.children = children
        self.calls = []
        self.pool = ThreadPoolExecutor(max_workers=4)

    def headers(self):
        return {}

    def list_children(self, item_id, select=None, cancel=None):
        self.calls.append(item_id)
        if self.latency:
            time.sleep(self.latency)
        return [DriveItem(raw) for raw in self.children.get(item_id, [])]

    def get_item(self, item_id):
        return DriveItem({"id": item_id, "name": item_id,
                          "folder": {"childCount": 0},
                          "parentReference": {"path": "/drive/root:"}})

    def me(self):
        return {"name": "Sample Account", "email": "sample@example.com"}

    def drive_usage(self):
        return {"used": 84_300_000_000, "total": 1_099_511_627_776}


class FakeCache(ImageCache):
    """Serves thumbnails from generated JPEGs instead of Graph."""

    def __init__(self, root, sources, **kwargs):
        self.sources = sources
        super().__init__(root, headers_provider=lambda: {}, **kwargs)

    def _download(self, key, url):
        source = self.sources.get(key.split(":")[0])
        if not source:
            return None
        target = self.path_for(key)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(source, target)
        return target


class FakeAuth:
    client_id = "preview"
    signed_in = True
    account = {}

    def access_token(self, force_refresh=False):
        return "preview-token"

    def sign_out(self):
        self.signed_in = False
