#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${1:-$ROOT/dist/compliance}"
WORK="$(mktemp -d)"
BUNDLE="$WORK/timelogger-3000-0.1.0-activitywatch-source"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$BUNDLE/source" "$BUNDLE/licenses" "$OUT_DIR"
cp "$ROOT/licenses/activitywatch/MPL-2.0.txt" "$BUNDLE/licenses/MPL-2.0.txt"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$BUNDLE/THIRD_PARTY_NOTICES.md"
cp "$ROOT/compliance/activitywatch-components.json" "$BUNDLE/activitywatch-components.json"

archive_component() {
  local name="$1" repository="$2" ref="$3"
  local checkout="$WORK/$name"
  git init --quiet "$checkout"
  git -C "$checkout" remote add origin "$repository"
  git -C "$checkout" fetch --quiet --depth 1 origin "$ref"
  git -C "$checkout" checkout --quiet --detach FETCH_HEAD
  git -C "$checkout" archive --format=tar.gz --prefix="$name-$ref/" -o "$BUNDLE/source/$name-$ref.tar.gz" HEAD
}

archive_component "aw-client" "https://github.com/ActivityWatch/aw-client.git" "v0.5.15"
archive_component "aw-core" "https://github.com/ActivityWatch/aw-core.git" "v0.5.17"
archive_component "aw-server" "https://github.com/ActivityWatch/aw-server.git" "b4ad07509067defec9a2a958ea9d58f3ed220c88"
archive_component "aw-watcher-window" "https://github.com/ActivityWatch/aw-watcher-window.git" "7a89db41f36abe44a157e5a1fdeb572a60a4e2f9"
archive_component "aw-watcher-afk" "https://github.com/ActivityWatch/aw-watcher-afk.git" "d30bb84d6cb7d36e038ded753cdafecca9a31576"

cat > "$BUNDLE/BUILDING.md" <<'EOF'
# Corresponding source

These are unmodified upstream source archives for the exact ActivityWatch components distributed with TimeLogger 3000 0.1.0.

TimeLogger 3000 does not currently modify these MPL-covered components. Their upstream build instructions are included inside each source archive. The macOS runtime build procedure is also available in `scripts/build-activitywatch-runtime-macos.sh` in the TimeLogger 3000 source distribution.
EOF

(
  cd "$WORK"
  tar -czf "$OUT_DIR/timelogger-3000-0.1.0-activitywatch-source.tar.gz" "$(basename "$BUNDLE")"
)
shasum -a 256 "$OUT_DIR/timelogger-3000-0.1.0-activitywatch-source.tar.gz" > "$OUT_DIR/timelogger-3000-0.1.0-activitywatch-source.tar.gz.sha256"
echo "Created $OUT_DIR/timelogger-3000-0.1.0-activitywatch-source.tar.gz"
