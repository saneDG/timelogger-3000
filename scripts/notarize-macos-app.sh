#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 dist/TimeLogger-3000-VERSION-ARCH.dmg" >&2
  exit 2
fi
if [[ -z "${APPLE_NOTARY_PROFILE:-}" ]]; then
  echo "APPLE_NOTARY_PROFILE must name credentials stored with: xcrun notarytool store-credentials" >&2
  exit 2
fi

DMG="$1"
xcrun notarytool submit "$DMG" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait
xcrun stapler staple "$DMG"
xcrun stapler validate "$DMG"
spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG"
echo "Notarized and stapled $DMG"
