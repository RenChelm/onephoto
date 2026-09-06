# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 renchelm
"""Headless functional test over the fake OneDrive.

Checks the behaviour the screenshots cannot show: that photo mode really
flattens the whole subtree, that every folder is listed exactly once, that
opening a tile shows only that folder's own pictures, and that navigation
and the startup-folder setting behave.

    python tools/selftest.py
"""

import os
import sys
import time

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kivy.config import Config                                    # noqa: E402
Config.set("graphics", "width", "412")
Config.set("graphics", "height", "880")
Config.set("kivy", "exit_on_escape", "0")

from kivy.base import EventLoop                                   # noqa: E402
from kivy.clock import Clock                                      # noqa: E402

import main as app_main                                           # noqa: E402
from onephoto import app_id                                       # noqa: E402
from onephoto.config import VIEW_FOLDERS, VIEW_PHOTOS             # noqa: E402
from tools import fakedrive                                       # noqa: E402

# Pretend this build was packaged with its own registration, the way a
# shipped APK is.
BAKED_ID = "00000000-1111-2222-3333-444444444444"
app_id.DEFAULT_CLIENT_ID = BAKED_ID

CHILDREN, SOURCES = fakedrive.build_sample(with_images=False)
CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append((label, bool(condition), detail))
    print("  %s %s%s" % ("PASS" if condition else "FAIL", label,
                         "" if condition else "  <- %s" % detail))


def pump(seconds=0.05):
    deadline = time.time() + seconds
    while time.time() < deadline:
        EventLoop.idle()
        time.sleep(1 / 240.0)


def wait_for(predicate, label, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        EventLoop.idle()
        time.sleep(1 / 240.0)
        if predicate():
            return True
    raise AssertionError("timed out waiting for %s" % label)


class TestApp(app_main.OnePhotoApp):
    @property
    def user_data_dir(self):
        path = os.path.join(fakedrive.WORK, "testdata")
        os.makedirs(path, exist_ok=True)
        return path

    def build(self):
        root = super().build()
        self.auth = fakedrive.FakeAuth()
        self.graph = fakedrive.FakeGraph(CHILDREN, latency=0)
        self.images = fakedrive.FakeCache(
            os.path.join(fakedrive.WORK, "testthumbs"), SOURCES)
        return root


def test_first_run(app):
    print("\nfirst run")
    check("a fresh install opens on the sign-in screen",
          app.manager.current == "login", app.manager.current)
    check("a build with its own client id asks for nothing else",
          not app.login._asking_for_id and app.login.client_box.height == 0)
    check("the only action offered is signing in",
          app.login.primary.text == "Sign in with Microsoft" and
          not app.login.primary.disabled)

    app.on_signed_in()          # what the device-code flow calls on success
    wait_for(lambda: app.manager.current == "browser" and
             app.browser.entry_list.data, "the drive root")
    check("signing in lands on the main screen",
          app.manager.current == "browser")
    check("the main screen shows the OneDrive root",
          app.browser.current["id"] == "root" and
          app.browser.current["name"] == "OneDrive", str(app.browser.current))
    check("the root directory is listed",
          len(app.browser.entry_list.data) == 4,
          "%d rows" % len(app.browser.entry_list.data))
    check("a signed-in account is fetched for Settings",
          app.auth.signed_in)


def test_client_id(app):
    print("\nclient id")
    path = os.path.join(app.user_data_dir, "settings.json")
    stale = app_main.Config(path)
    stale.set("client_id", "an-old-registration")
    reloaded = app_main.Config(path)
    check("the built-in id beats a stale stored one",
          reloaded.get("client_id") == BAKED_ID, reloaded.get("client_id"))
    check("the app reports that it carries its own id",
          reloaded.client_id_is_builtin)

    app_id.DEFAULT_CLIENT_ID = ""
    try:
        without = app_main.Config(path)
        check("without a built-in id the stored one is used",
              without.get("client_id") == "an-old-registration",
              without.get("client_id"))
        check("and the app knows it must ask",
              not without.client_id_is_builtin)
    finally:
        app_id.DEFAULT_CLIENT_ID = BAKED_ID


def test_sign_in_authority(app):
    print("\nsign-in authority")
    check("personal accounts are the default authority",
          app.prefs.get("tenant") == "consumers", app.prefs.get("tenant"))
    check("the sign-in screen offers the work-account alternative",
          "work or school" in app.login.kind_button.text,
          app.login.kind_button.text)

    app.login.toggle_account_kind()
    check("switching moves to the work/school authority",
          app.prefs.get("tenant") == "organizations" and
          app.auth.tenant == "organizations", app.prefs.get("tenant"))
    check("and the button offers the way back",
          "personal" in app.login.kind_button.text, app.login.kind_button.text)

    app.login.toggle_account_kind()
    check("switching back restores personal accounts",
          app.prefs.get("tenant") == "consumers", app.prefs.get("tenant"))


def test_walker(app):
    print("\nwalk_folders")
    app.graph.calls = []
    folders, root_scan = app.graph.walk_folders("Pictures")
    names = sorted(f.name for f in folders)
    expected = sorted(["2024", "2023", "Screenshots", "Wallpapers", "Iceland",
                       "Tokyo", "Studio", "Wedding", "Garden", "Reykjavik",
                       "Vestrahorn"])
    check("every folder and subfolder is flattened", names == expected,
          "got %s" % names)
    check("each folder is listed exactly once",
          len(app.graph.calls) == len(set(app.graph.calls)) == 12,
          "calls=%d unique=%d" % (len(app.graph.calls),
                                  len(set(app.graph.calls))))
    by_name = {f.name: f for f in folders}
    check("nested folders keep a relative path",
          by_name["Reykjavik"].rel_path == "2024/Iceland/Reykjavik",
          by_name["Reykjavik"].rel_path)
    check("direct photo counts are annotated",
          by_name["Tokyo"].photo_count == 21 and
          by_name["Iceland"].photo_count == 6,
          "tokyo=%d iceland=%d" % (by_name["Tokyo"].photo_count,
                                   by_name["Iceland"].photo_count))
    check("a folder with pictures gets a cover",
          by_name["Wedding"].cover_id is not None)
    check("a folder without pictures gets no cover",
          by_name["2024"].cover_id is None and by_name["2024"].photo_count == 0)
    check("the browsed folder reports its own loose photos",
          root_scan["photo_count"] == 3, str(root_scan))


def test_photo_mode(app):
    print("\nphoto mode")
    app.prefs.set_start_folder("Pictures", "Pictures", "/Pictures")
    app.prefs.set("view_mode", VIEW_PHOTOS)
    browser = app.browser
    browser.mode = VIEW_PHOTOS
    browser.segment.value = VIEW_PHOTOS
    browser.reset_to_start()
    browser.refresh()
    wait_for(lambda: not browser.progress.active and
             len(browser.folder_grid.data) >= 12, "the folder grid")

    data = browser.folder_grid.data
    check("grid holds a tile per folder plus the current folder",
          len(data) == 12, "len=%d" % len(data))
    check("the current folder's loose photos are reachable",
          data[0]["is_current"] and data[0]["subtitle"] == "3 photos",
          str(data[0]))
    check("tiles carry a cover thumbnail url",
          all(d["thumb_url"] or d["subtitle"] == "no photos" for d in data))
    check("grid is three columns",
          browser.folder_grid.layout.cols == 3)

    tile = next(i for i, d in enumerate(data) if d["title"] == "Iceland")
    browser.on_folder_tile(tile)
    wait_for(lambda: browser.photo_folder is not None and
             not browser.progress.active and browser.photo_grid.data,
             "Iceland's photos")
    check("tapping a folder opens that folder",
          browser.photo_folder["name"] == "Iceland",
          str(browser.photo_folder))
    check("only the folder's own pictures are shown, not its subfolders'",
          len(browser.photo_grid.data) == 6,
          "%d photos" % len(browser.photo_grid.data))
    check("no subfolder tiles appear inside an opened folder",
          all("kind" not in d for d in browser.photo_grid.data))

    check("back returns to the flattened grid", browser.go_back())
    wait_for(lambda: browser.photo_folder is None and
             len(browser.folder_grid.data) >= 12, "the grid again")
    check("back at the top of the stack lets the app close",
          browser.go_back() is False)


def test_folder_mode(app):
    print("\nfolder mode")
    browser = app.browser
    browser.set_mode(VIEW_FOLDERS)
    wait_for(lambda: not browser.progress.active and browser.entry_list.data,
             "the folder listing")
    rows = browser.entry_list.data
    check("folders are listed before files",
          [r["kind"] for r in rows] == ["folder"] * 4 + ["image"] * 3,
          str([r["kind"] for r in rows]))
    check("view mode is remembered",
          app.prefs.get("view_mode") == VIEW_FOLDERS)

    browser.on_entry(0)
    wait_for(lambda: len(browser.stack) == 2 and browser.entry_list.data,
             "the nested folder")
    check("tapping a folder opens it", browser.current["name"] == "2023",
          str(browser.current))
    check("nested listing shows that folder's children",
          len(browser.entry_list.data) == 4,
          "%d rows" % len(browser.entry_list.data))
    check("back pops the stack", browser.go_back() and len(browser.stack) == 1)


def test_startup_folder(app):
    print("\nstartup folder")
    browser = app.browser
    wait_for(lambda: not browser.progress.active, "idle")
    browser.stack.append({"id": "Screenshots", "name": "Screenshots",
                          "path": "/Pictures/Screenshots"})
    browser.pin_current()
    check("pinning stores the folder",
          app.prefs.get("start_folder_id") == "Screenshots" and
          app.prefs.get("start_folder_path") == "/Pictures/Screenshots",
          str(app.prefs.start_folder))

    reloaded = app_main.Config(os.path.join(app.user_data_dir,
                                            "settings.json"))
    check("the choice survives a restart",
          reloaded.get("start_folder_id") == "Screenshots" and
          reloaded.get("view_mode") == VIEW_FOLDERS,
          str(reloaded.start_folder))

    browser.reset_to_start()
    check("the app opens on the pinned folder",
          browser.current["id"] == "Screenshots", str(browser.current))


def test_cache(app):
    print("\nthumbnail cache")
    from PIL import Image
    sample = os.path.join(fakedrive.WORK, "cache-source.jpg")
    Image.new("RGB", (64, 64), (80, 120, 200)).save(sample)
    app.images.sources["img001"] = sample

    got = []
    key = "img001:c400x400_Crop"
    app.images.request(key, "http://example.invalid/x", lambda k, p: got.append(p))
    wait_for(lambda: got, "the cached file")
    check("a requested thumbnail lands on disk",
          got[0] and os.path.exists(got[0]), str(got))
    check("a second request is served from disk",
          got[0] is not None and app.images.peek(key) == got[0])
    missing = []
    app.images.request("nope:c400x400_Crop", "http://example.invalid/y",
                       lambda k, p: missing.append(p))
    wait_for(lambda: missing, "the missing-thumbnail callback")
    check("a thumbnail that cannot be fetched reports None",
          missing[0] is None, str(missing))


def main():
    app = TestApp()

    def script(_dt):
        try:
            test_first_run(app)
            test_sign_in_authority(app)
            test_client_id(app)
            test_walker(app)
            test_photo_mode(app)
            test_folder_mode(app)
            test_startup_folder(app)
            test_cache(app)
        except Exception as exc:                       # noqa: BLE001
            import traceback
            traceback.print_exc()
            check("test run completed", False, str(exc))
        failed = [c for c in CHECKS if not c[1]]
        print("\n%d checks, %d failed" % (len(CHECKS), len(failed)))
        app.stop()
        sys.exit(1 if failed else 0)

    Clock.schedule_once(script, 0.6)
    app.run()


if __name__ == "__main__":
    main()
