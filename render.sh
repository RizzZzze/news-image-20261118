#!/bin/sh
# Render entry.png from render.html with headless Chromium and system fonts.
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
CHROME="$HOME/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome"
"$CHROME" --headless --no-sandbox --disable-gpu --hide-scrollbars \
  --window-size=1024,1024 \
  --screenshot="$DIR/entry.png" \
  "file://$DIR/render.html"
