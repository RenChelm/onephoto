# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""Thin wrappers over the few Android-specific things the app needs."""

from kivy.utils import platform

IS_ANDROID = platform == "android"


def open_url(url):
    """Open a link in the system browser (Android intent, else webbrowser)."""
    if IS_ANDROID:
        try:
            from jnius import autoclass, cast
            activity_cls = autoclass("org.kivy.android.PythonActivity")
            intent_cls = autoclass("android.content.Intent")
            uri_cls = autoclass("android.net.Uri")
            intent = intent_cls(intent_cls.ACTION_VIEW, uri_cls.parse(url))
            intent.setFlags(intent_cls.FLAG_ACTIVITY_NEW_TASK)
            activity = cast("android.app.Activity", activity_cls.mActivity)
            activity.startActivity(intent)
            return True
        except Exception:
            return False
    try:
        import webbrowser
        return webbrowser.open(url)
    except Exception:
        return False


def copy_text(text):
    try:
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(text)
        return True
    except Exception:
        return False


def human_size(num_bytes):
    size = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return "%d B" % size
            return "%.1f %s" % (size, unit)
        size /= 1024.0
    return "%d B" % size


def plural(count, singular, suffix="s"):
    return "%d %s%s" % (count, singular, "" if count == 1 else suffix)
