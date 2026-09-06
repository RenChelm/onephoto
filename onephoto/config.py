# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""Small JSON-backed settings store.

Everything the user can change from the Settings screen lives here: which
folder the app opens on, which of the two view modes is active and the
Azure application (client) id used for sign-in.
"""

import json
import os
import threading

from . import app_id

DEFAULTS = {
    # Azure "Application (client) ID" of a public client app.  Normally this
    # comes from app_id.DEFAULT_CLIENT_ID, which is baked in at build time;
    # the stored value is only used when the app ships without one and the
    # user types it on the sign-in screen.
    "client_id": "",
    # Which sign-in authority to use.  "consumers" is the default because
    # personal Microsoft accounts are what this app is for, and "common"
    # routes them to the Entra device page, where their sign-in dead-ends on
    # "You have reached the wrong page".  The sign-in screen can switch this
    # to "organizations" for work and school accounts.
    "tenant": "consumers",
    # "folders" -> classic browser, "photos" -> flattened folder tiles
    "view_mode": "folders",
    # Folder opened on startup.  "root" is the top of the drive.
    "start_folder_id": "root",
    "start_folder_name": "OneDrive",
    "start_folder_path": "/",
    "thumb_cache_mb": 300,
}

VIEW_FOLDERS = "folders"
VIEW_PHOTOS = "photos"


class Config:
    """Dict-like settings object that writes through to disk."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._data = dict(DEFAULTS)
        self.load()

    # -- persistence ------------------------------------------------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                self._data.update({k: v for k, v in stored.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
        # Resolution order: environment override, then the id built into
        # this package, then whatever the user typed on the sign-in screen.
        # The built-in id wins over the stored one so that rebuilding with a
        # different registration is not shadowed by an old settings file.
        env_id = (os.environ.get("ONEPHOTO_CLIENT_ID") or "").strip()
        baked_id = (app_id.DEFAULT_CLIENT_ID or "").strip()
        if env_id:
            self._data["client_id"] = env_id
        elif baked_id:
            self._data["client_id"] = baked_id
        # "common" serves every account type but routes personal accounts to
        # the Entra device page; "consumers" uses the page personal accounts
        # actually complete on.
        env_tenant = (os.environ.get("ONEPHOTO_TENANT") or "").strip()
        if env_tenant:
            self._data["tenant"] = env_tenant
        return self._data

    @property
    def client_id_is_builtin(self):
        """True when this build carries its own id, so no prompt is needed."""
        return bool((os.environ.get("ONEPHOTO_CLIENT_ID") or "").strip()
                    or (app_id.DEFAULT_CLIENT_ID or "").strip())

    def save(self):
        with self._lock:
            tmp = self.path + ".tmp"
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
            os.replace(tmp, self.path)

    # -- access -----------------------------------------------------------
    def get(self, key, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def __getitem__(self, key):
        return self.get(key)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def update(self, **kwargs):
        self._data.update(kwargs)
        self.save()

    def set_start_folder(self, item_id, name, path="/"):
        self.update(start_folder_id=item_id, start_folder_name=name,
                    start_folder_path=path)

    @property
    def start_folder(self):
        return {
            "id": self.get("start_folder_id"),
            "name": self.get("start_folder_name"),
            "path": self.get("start_folder_path"),
        }
