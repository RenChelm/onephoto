# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""Microsoft identity sign-in using the OAuth 2.0 device authorisation flow.

The device flow is used because it needs no redirect URI, no embedded web
view and no custom URL scheme registration -- the phone shows a short code,
the user types it at https://microsoft.com/devicelogin and the app polls for
the resulting tokens.  Refresh tokens are cached so sign-in survives
restarts.
"""

import json
import os
import stat
import threading
import time

import requests

AUTH_HOST = "https://login.microsoftonline.com"
SCOPES = ["offline_access", "Files.Read.All", "User.Read"]
# Refresh a little early so a long request never dies on a stale token.
EXPIRY_SKEW = 120


class AuthError(Exception):
    """Sign-in failed in a way the user has to act on."""


class AuthPending(Exception):
    """The user has not finished entering the code yet."""


class Authenticator:
    def __init__(self, client_id, tenant="common", token_path="token.json"):
        self.client_id = (client_id or "").strip()
        self.tenant = tenant or "common"
        self.token_path = token_path
        self._lock = threading.Lock()
        self._access_token = None
        self._expires_at = 0.0
        self._refresh_token = None
        self.account = {}
        self._load()

    # -- endpoints --------------------------------------------------------
    @property
    def _device_url(self):
        return "%s/%s/oauth2/v2.0/devicecode" % (AUTH_HOST, self.tenant)

    @property
    def _token_url(self):
        return "%s/%s/oauth2/v2.0/token" % (AUTH_HOST, self.tenant)

    # -- token cache ------------------------------------------------------
    def _load(self):
        try:
            with open(self.token_path, "r", encoding="utf-8") as fh:
                blob = json.load(fh)
        except (OSError, ValueError):
            return
        self._refresh_token = blob.get("refresh_token")
        self._access_token = blob.get("access_token")
        self._expires_at = blob.get("expires_at", 0)
        self.account = blob.get("account", {}) or {}
        # A token cached for a different app registration is useless.
        if blob.get("client_id") and blob["client_id"] != self.client_id:
            self._refresh_token = self._access_token = None
            self.account = {}

    def _store(self):
        blob = {
            "client_id": self.client_id,
            "refresh_token": self._refresh_token,
            "access_token": self._access_token,
            "expires_at": self._expires_at,
            "account": self.account,
        }
        tmp = self.token_path + ".tmp"
        os.makedirs(os.path.dirname(self.token_path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(blob, fh)
        try:
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        os.replace(tmp, self.token_path)

    def _absorb(self, payload):
        self._access_token = payload["access_token"]
        self._expires_at = time.time() + float(payload.get("expires_in", 3600))
        if payload.get("refresh_token"):
            self._refresh_token = payload["refresh_token"]
        self._store()

    # -- state ------------------------------------------------------------
    @property
    def signed_in(self):
        return bool(self._refresh_token or self._access_token)

    def sign_out(self):
        with self._lock:
            self._access_token = None
            self._refresh_token = None
            self._expires_at = 0
            self.account = {}
        try:
            os.remove(self.token_path)
        except OSError:
            pass

    # -- device flow ------------------------------------------------------
    def begin_device_flow(self):
        """Ask Microsoft for a user code.  Returns the flow dict to poll."""
        if not self.client_id:
            raise AuthError("No application (client) ID configured.")
        resp = requests.post(
            self._device_url,
            data={"client_id": self.client_id, "scope": " ".join(SCOPES)},
            timeout=30,
        )
        payload = _json(resp)
        if resp.status_code >= 400:
            raise AuthError(_describe(payload, "Could not start sign-in."))
        payload.setdefault("interval", 5)
        payload["deadline"] = time.time() + float(payload.get("expires_in", 900))
        return payload

    def poll_device_flow(self, flow):
        """Poll once.  Returns True when signed in, raises AuthPending if not."""
        if time.time() > flow.get("deadline", 0):
            raise AuthError("The code expired. Please start again.")
        resp = requests.post(
            self._token_url,
            data={
                "client_id": self.client_id,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": flow["device_code"],
            },
            timeout=30,
        )
        payload = _json(resp)
        if resp.status_code < 400:
            with self._lock:
                self._absorb(payload)
            return True
        error = payload.get("error", "")
        if error == "authorization_pending":
            raise AuthPending()
        if error == "slow_down":
            flow["interval"] = flow.get("interval", 5) + 5
            raise AuthPending()
        if error == "authorization_declined":
            raise AuthError("Sign-in was declined.")
        if error == "expired_token":
            raise AuthError("The code expired. Please start again.")
        raise AuthError(_describe(payload, "Sign-in failed."))

    # -- tokens -----------------------------------------------------------
    def access_token(self, force_refresh=False):
        """Return a usable bearer token, refreshing it when needed."""
        with self._lock:
            fresh = self._access_token and time.time() < self._expires_at - EXPIRY_SKEW
            if fresh and not force_refresh:
                return self._access_token
            if not self._refresh_token:
                raise AuthError("Signed out. Please sign in again.")
            resp = requests.post(
                self._token_url,
                data={
                    "client_id": self.client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "scope": " ".join(SCOPES),
                },
                timeout=30,
            )
            payload = _json(resp)
            if resp.status_code >= 400:
                # A rejected refresh token is dead -- force a new sign-in.
                if payload.get("error") in ("invalid_grant", "invalid_client"):
                    self._refresh_token = None
                    self._access_token = None
                    self._store()
                raise AuthError(_describe(payload, "Session expired."))
            self._absorb(payload)
            return self._access_token


def _json(resp):
    try:
        return resp.json()
    except ValueError:
        return {}


def _describe(payload, fallback):
    text = payload.get("error_description") or payload.get("error") or fallback
    # Microsoft error descriptions carry a trace block; keep the first line.
    return str(text).split("\r\n")[0].split("\n")[0].strip() or fallback
