#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
PYINSTALLER="${PYINSTALLER:-$ROOT/.venv/bin/pyinstaller}"
DMGBUILD="${DMGBUILD:-$ROOT/.venv/bin/dmgbuild}"
VERSION="0.1.0"
APP="$ROOT/dist/TimeLogger 3000.app"
DMG="$ROOT/dist/TimeLogger-3000-$VERSION-$(uname -m).dmg"

"$PYTHON" packaging/macos/create_icon.py
"$ROOT/scripts/build-activitywatch-runtime-macos.sh"
"$PYINSTALLER" --clean --noconfirm packaging/macos/TimeLogger3000.spec

if [[ -n "${APPLE_SIGNING_IDENTITY:-}" ]]; then
  codesign --force --deep --options runtime --timestamp \
    --entitlements packaging/macos/entitlements.plist \
    --sign "$APPLE_SIGNING_IDENTITY" "$APP"
  codesign --verify --deep --strict --verbose=2 "$APP"
else
  echo "WARNING: APPLE_SIGNING_IDENTITY is unset; creating an unsigned development build." >&2
fi

rm -f "$DMG"
"$DMGBUILD" -s packaging/macos/dmg_settings.py \
  -D "app=$APP" "TimeLogger 3000" "$DMG"

if [[ -n "${APPLE_SIGNING_IDENTITY:-}" ]]; then
  codesign --force --timestamp --sign "$APPLE_SIGNING_IDENTITY" "$DMG"
fi

echo "Created $APP"
echo "Created $DMG"
