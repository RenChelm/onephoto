[app]

title = OnePhoto
package.name = onephoto
package.domain = org.onephoto

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json
source.include_patterns = assets/*
# Keep the desktop virtualenv, dev harnesses and build output out of the APK.
source.exclude_dirs = tools, tests, bin, preview, .buildozer, kivyenv, __pycache__
source.exclude_patterns = *.pyc, *.log, preview/*

version = 1.0.0

# openssl + certifi give requests a working TLS stack on device; the android
# recipe provides the activity bindings used to open the sign-in page.
# charset-normalizer is capped deliberately, and with "<" rather than "==".
# p4a resolves dependencies by running `pip --dry-run --platform=android_24_
# ...`, so for requests it picks PyPI's official Android wheel and writes
# that URL into its generated requirements.txt -- then installs that file
# *without* the platform flags, and pip rejects the wheel it just chose
# ("is not a supported wheel on this platform").  Versions below 3.4 predate
# those Android wheels and resolve to the universal py3-none-any build.
# The cap has to be "<": p4a splits requirements on "==" and strips the
# version into an environment variable before the resolver ever sees it, so
# an "==" pin silently has no effect on what gets resolved.
requirements = python3,kivy==2.3.1,openssl,certifi,requests,urllib3,idna,charset-normalizer<3.4,android

presplash.filename = %(source.dir)s/assets/presplash.png
icon.filename = %(source.dir)s/assets/icon.png

orientation = portrait
fullscreen = 0

#
# Android specific
#
android.presplash_color = #101014

# The app only ever reads from the network; nothing else is needed.
android.permissions = INTERNET, ACCESS_NETWORK_STATE

android.api = 34
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a, armeabi-v7a

# The OneDrive refresh token lives in app-private storage -- keep it out of
# device backups.
android.allow_backup = False

android.logcat_filters = *:S python:D
p4a.bootstrap = sdl2


[buildozer]

log_level = 2
warn_on_root = 1
build_dir = ./.buildozer
bin_dir = ./bin
