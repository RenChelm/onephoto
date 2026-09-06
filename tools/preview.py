"""Run OnePhoto against a fake OneDrive, offline, and save screenshots.

A development harness -- it never talks to Microsoft.

    python tools/preview.py [outdir]
"""

import os
import sys
import time

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("SDL_VIDEODRIVER", os.environ.get("PREVIEW_SDL",
                                                        "offscreen"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kivy.config import Config                                    # noqa: E402
Config.set("graphics", "width", "412")
Config.set("graphics", "height", "880")
Config.set("graphics", "resizable", "0")
Config.set("kivy", "exit_on_escape", "0")

from kivy.base import EventLoop                                   # noqa: E402
from kivy.clock import Clock                                      # noqa: E402
from kivy.core.window import Window                               # noqa: E402

import main as app_main                                           # noqa: E402
from onephoto import app_id                                       # noqa: E402
from tools import fakedrive                                       # noqa: E402

# Preview the screens as a shipped build shows them: with a client id baked
# in, first run is a single sign-in button.
app_id.DEFAULT_CLIENT_ID = "00000000-1111-2222-3333-444444444444"


OUT = sys.argv[1] if len(sys.argv) > 1 else "preview"
CHILDREN, SOURCES = fakedrive.build_sample()


class PreviewApp(app_main.OnePhotoApp):
    @property
    def user_data_dir(self):
        path = os.path.join(fakedrive.WORK, "data")
        os.makedirs(path, exist_ok=True)
        return path

    def build(self):
        root = super().build()
        self.auth = fakedrive.FakeAuth()
        self.graph = fakedrive.FakeGraph(CHILDREN)
        self.images = fakedrive.FakeCache(
            os.path.join(fakedrive.WORK, "thumbs"), SOURCES)
        self.account = {"name": "Sample Account",
                        "email": "sample@example.com"}
        return root


def pump(seconds=0.6):
    """Run real frames -- tick, dispatch input, draw, flip."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        EventLoop.idle()
        time.sleep(1 / 120.0)


def shot(name):
    pump(0.45)
    path = os.path.join(OUT, "%s.png" % name)
    print("  %-24s -> %s" % (name, Window.screenshot(name=path) or path))


def main():
    os.makedirs(OUT, exist_ok=True)
    app = PreviewApp()

    def script(_dt):
        app.prefs.set("view_mode", "photos")
        app.prefs.set_start_folder("Pictures", "Pictures", "/Pictures")
        print("capturing screens into %s/" % OUT)

        app.manager.current = "login"
        shot("01-login")

        app.manager.current = "browser"
        app.browser.reset_to_start()
        app.browser.mode = "photos"
        app.browser.segment.value = "photos"
        app.browser.refresh()
        pump(3.0)
        shot("02-photos-folder-grid")

        app.browser.on_folder_tile(3)
        pump(2.5)
        shot("03-photos-inside-folder")

        app.browser.set_mode("folders")
        pump(2.0)
        shot("04-folder-list")

        app.browser.on_entry(0)
        pump(2.0)
        shot("05-folder-list-nested")

        if app.browser._images:
            app.open_viewer(app.browser._images, 0)
            pump(2.0)
            shot("06-viewer")
            app.close_viewer()
            pump(0.4)

        app.open_settings()
        pump(1.2)
        shot("07-settings")

        app.open_picker()
        pump(1.5)
        shot("08-picker")

        app.close_picker()
        pump(0.5)
        app.manager.current = "browser"
        app.browser.open_menu()
        pump(0.6)
        shot("09-menu")

        print("done")
        app.stop()

    Clock.schedule_once(script, 1.0)
    app.run()


if __name__ == "__main__":
    main()
