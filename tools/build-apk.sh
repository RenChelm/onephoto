#!/usr/bin/env sh
# Build the Android package.
#
# Three things this handles that a bare `buildozer android debug` does not.
#
# 1. python-for-android runs `python -m venv venv` over its build venv at the
#    start of every run.  On the second and later runs that re-seeds
#    ensurepip's pip on top of whatever the previous run left, and the two
#    releases are shaped differently: pip 25.3 ships `build_env.py` as a
#    module, pip 26.x ships `build_env/` as a package.  The leftover package
#    directory shadows the module, so pip imports half of one release and
#    half of the other and dies with
#        ImportError: cannot import name 'BuildDependencyInstallError'
#    Deleting the venv makes every build behave like a first build.
#
# 2. Belt and braces for the same problem: pinning pip to the version
#    ensurepip bundles turns p4a's `pip install -U pip` into a no-op, so the
#    two releases can never be mixed in the first place.  The pin only names
#    pip, so it leaves the project's own requirements alone.
#
# 3. buildozer looks for `cython` on PATH, and ours lives in kivyenv/bin.
#
# Usage:  tools/build-apk.sh                       -> debug APK into bin/
#         tools/build-apk.sh release               -> release build
#         tools/build-apk.sh debug deploy run logcat
set -e

cd "$(dirname "$0")/.."

if [ $# -eq 0 ]; then
    set -- debug
fi

echo "==> clearing python-for-android's build venv"
rm -rf .buildozer/android/platform/build-*/build/venv

HOSTPYTHON=$(ls .buildozer/android/platform/build-*/build/other_builds/hostpython3/desktop/hostpython3/native-build/root/usr/local/bin/python 2>/dev/null | head -1)
if [ -n "$HOSTPYTHON" ]; then
    SEEDED_PIP=$("$HOSTPYTHON" -c 'import ensurepip; print(ensurepip.version())' 2>/dev/null || true)
    if [ -n "$SEEDED_PIP" ]; then
        mkdir -p .buildozer
        echo "pip==$SEEDED_PIP" > .buildozer/pip-constraint.txt
        PIP_CONSTRAINT="$(pwd)/.buildozer/pip-constraint.txt"
        export PIP_CONSTRAINT
        echo "==> pinning the build venv to pip $SEEDED_PIP"
    fi
fi

PATH="$(pwd)/kivyenv/bin:$PATH"
export PATH

echo "==> buildozer android $*"
exec buildozer android "$@"
