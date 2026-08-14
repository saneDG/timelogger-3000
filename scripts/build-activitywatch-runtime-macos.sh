#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="v0.13.2"
SOURCE_COMMIT="839d99ffabe8a0281d332a2fddfb78514266698b"
SERVER_COMMIT="b4ad07509067defec9a2a958ea9d58f3ed220c88"
WINDOW_COMMIT="7a89db41f36abe44a157e5a1fdeb572a60a4e2f9"
AFK_COMMIT="d30bb84d6cb7d36e038ded753cdafecca9a31576"
CACHE="${TIMELOGGER_BUILD_CACHE:-$HOME/Library/Caches/TimeLogger 3000/build}"
SOURCE="$CACHE/activitywatch-$VERSION"
OUTPUT="$ROOT/build/activitywatch-runtime"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
mkdir -p "$CACHE" "$ROOT/build"
if [[ ! -d "$SOURCE/.git" ]]; then
  git clone --quiet https://github.com/ActivityWatch/activitywatch.git "$SOURCE"
fi
git -C "$SOURCE" fetch --quiet origin tag "$VERSION"
git -C "$SOURCE" checkout --quiet --detach "$SOURCE_COMMIT"
git -C "$SOURCE" submodule update --init \
  aw-server aw-watcher-window aw-watcher-afk

[[ "$(git -C "$SOURCE/aw-server" rev-parse HEAD)" == "$SERVER_COMMIT" ]]
[[ "$(git -C "$SOURCE/aw-watcher-window" rev-parse HEAD)" == "$WINDOW_COMMIT" ]]
[[ "$(git -C "$SOURCE/aw-watcher-afk" rev-parse HEAD)" == "$AFK_COMMIT" ]]

rm -rf "$OUTPUT"
mkdir -p "$OUTPUT"

"$PYTHON" -m pip install --quiet "$SOURCE/aw-server" "$SOURCE/aw-watcher-window" "$SOURCE/aw-watcher-afk"
PLACEHOLDER="$CACHE/server-static"
mkdir -p "$PLACEHOLDER"
printf '<!doctype html><title>ActivityWatch API</title>' > "$PLACEHOLDER/index.html"
SERVER_SPEC="$CACHE/activitywatch-server.spec"
sed -e "s|__SOURCE__|$SOURCE/aw-server|g" -e "s|__PLACEHOLDER__|$PLACEHOLDER|g" \
  "$ROOT/packaging/macos/activitywatch-server.spec.template" > "$SERVER_SPEC"
"$PYTHON" -m PyInstaller "$SERVER_SPEC" --clean --noconfirm --distpath "$OUTPUT" --workpath "$CACHE/server-work"
WINDOW_SPEC="$CACHE/activitywatch-window.spec"
sed -e "s|__SOURCE__|$SOURCE/aw-watcher-window|g" \
  -e "s|__RUNTIME_HOOK__|$ROOT/packaging/macos/activitywatch_freeze_support.py|g" \
  "$ROOT/packaging/macos/activitywatch-window.spec.template" > "$WINDOW_SPEC"
"$PYTHON" -m PyInstaller "$WINDOW_SPEC" --clean --noconfirm --distpath "$OUTPUT" --workpath "$CACHE/window-work"
(
  cd "$SOURCE/aw-watcher-afk"
  "$PYTHON" -m PyInstaller aw-watcher-afk.spec --clean --noconfirm --distpath "$OUTPUT" --workpath "$CACHE/afk-work"
)

chmod +x "$OUTPUT/aw-server/aw-server" \
  "$OUTPUT/aw-watcher-window/aw-watcher-window" \
  "$OUTPUT/aw-watcher-afk/aw-watcher-afk"

cat > "$OUTPUT/VERSIONS.json" <<EOF
{"activitywatch":"$VERSION","activitywatch_commit":"$SOURCE_COMMIT","aw-server":"$SERVER_COMMIT","aw-watcher-window":"$WINDOW_COMMIT","aw-watcher-afk":"$AFK_COMMIT","architecture":"$(uname -m)"}
EOF

echo "Built native ActivityWatch runtime at $OUTPUT"
