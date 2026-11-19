#!/bin/sh
# Screenshot the front page (render.html) to entry.png with headless Chromium.
set -eu
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
CHROME="$HOME/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome"
"$CHROME" --headless --no-sandbox --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1 --window-size=1024,1024 \
  --screenshot="$HERE/entry.png" "file://$HERE/render.html"
