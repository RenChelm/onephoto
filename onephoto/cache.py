# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""Disk-backed thumbnail cache with a small pool of download threads.

Pictures are streamed from OneDrive on demand: a tile asks for a key, the
cache either hands back a file that is already on disk or queues a download
and calls back on the Kivy thread once the bytes have landed.  Requests are
served most-recent-first so whatever the user just scrolled to wins, and a
generation counter lets a screen abandon everything it asked for when the
user navigates away.
"""

import hashlib
import os
import shutil
import threading
import queue

import requests
from kivy.clock import Clock
from kivy.loader import Loader

CHUNK = 64 * 1024


class ImageCache:
    def __init__(self, root, headers_provider, max_bytes=300 * 1024 * 1024,
                 workers=4):
        self.root = root
        self.headers_provider = headers_provider
        self.max_bytes = max_bytes
        os.makedirs(self.root, exist_ok=True)
        self._queue = queue.LifoQueue()
        self._inflight = {}          # key -> callbacks waiting on it
        self._failed = set()
        self._lock = threading.Lock()
        self._generation = 0
        self._threads = []
        for i in range(workers):
            thread = threading.Thread(target=self._worker, daemon=True,
                                      name="thumb-%d" % i)
            thread.start()
            self._threads.append(thread)
        threading.Thread(target=self.prune, daemon=True).start()

    # -- paths ------------------------------------------------------------
    def path_for(self, key):
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return os.path.join(self.root, digest[:2], digest + ".img")

    def peek(self, key):
        """Local path if the image is already cached, else None."""
        path = self.path_for(key)
        if os.path.exists(path):
            try:                       # keep it fresh for LRU pruning
                os.utime(path, None)
            except OSError:
                pass
            return path
        return None

    # -- requests ---------------------------------------------------------
    def invalidate_pending(self):
        """Drop every queued download (called when the user navigates)."""
        with self._lock:
            self._generation += 1

    def request(self, key, url, callback):
        """Fetch ``url`` into the cache and call ``callback(key, path)``.

        The callback always runs on the Kivy main thread; ``path`` is None
        when the image could not be fetched.
        """
        path = self.peek(key)
        if path:
            _on_main(callback, key, path)
            return path
        with self._lock:
            if key in self._failed:
                _on_main(callback, key, None)
                return None
            generation = self._generation
            waiting = self._inflight.get(key)
            if waiting is not None:
                waiting.append(callback)     # ride along with the in-flight one
                return None
            self._inflight[key] = [callback]
        self._queue.put((generation, key, url))
        return None

    # -- workers ----------------------------------------------------------
    def _worker(self):
        while True:
            generation, key, url = self._queue.get()
            path = None
            try:
                with self._lock:
                    stale = generation < self._generation
                # A stale request is one whose screen has gone away; serve it
                # from disk if the bytes happen to be there, but do not spend
                # the network on it.
                path = self.peek(key)
                if path is None and not stale:
                    path = self._download(key, url)
            except Exception:
                path = None
            finally:
                with self._lock:
                    waiting = self._inflight.pop(key, [])
                for callback in waiting:
                    _on_main(callback, key, path)
                self._queue.task_done()

    def _download(self, key, url):
        target = self.path_for(key)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = target + ".part-%d" % threading.get_ident()
        try:
            resp = requests.get(url, headers=self.headers_provider(),
                                stream=True, timeout=60)
            if resp.status_code == 404:
                # OneDrive cannot render a thumbnail for this file.
                with self._lock:
                    self._failed.add(key)
                return None
            if resp.status_code >= 400:
                return None
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(CHUNK):
                    if chunk:
                        fh.write(chunk)
            if os.path.getsize(tmp) == 0:
                raise IOError("empty response")
            os.replace(tmp, target)
            return target
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return None

    # -- housekeeping -----------------------------------------------------
    def usage(self):
        total = 0
        for dirpath, _dirs, files in os.walk(self.root):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, name))
                except OSError:
                    pass
        return total

    def prune(self):
        """Drop least-recently-used files until back under the size cap."""
        entries = []
        total = 0
        for dirpath, _dirs, files in os.walk(self.root):
            for name in files:
                full = os.path.join(dirpath, name)
                try:
                    stat = os.stat(full)
                except OSError:
                    continue
                entries.append((stat.st_mtime, stat.st_size, full))
                total += stat.st_size
        if total <= self.max_bytes:
            return total
        entries.sort()
        for _mtime, size, full in entries:
            if total <= self.max_bytes * 0.8:
                break
            try:
                os.remove(full)
                total -= size
            except OSError:
                pass
        return total

    def clear(self):
        with self._lock:
            self._failed.clear()
            self._generation += 1
        shutil.rmtree(self.root, ignore_errors=True)
        os.makedirs(self.root, exist_ok=True)


def _on_main(callback, key, path):
    Clock.schedule_once(lambda _dt: callback(key, path), 0)


def load_texture(path, callback):
    """Decode an image off the main thread and hand back its texture.

    Kivy's Loader keeps its own small texture cache, so a tile that scrolls
    back into view is usually served without touching the disk again.
    """
    proxy = Loader.image(path)
    if proxy.loaded and proxy.texture is not None:
        callback(proxy.texture)
        return proxy

    def _done(image_proxy, *_args):
        callback(getattr(image_proxy, "texture", None))

    proxy.bind(on_load=_done)
    return proxy
