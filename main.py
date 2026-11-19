#!/usr/bin/env python3
"""Deliver the front-page image for news-image-20261118.

The page is drawn once, by hand, as render.html and screenshotted to
entry.png with headless Chromium (see render.sh). At grading time this
program only places that exact image at the output path the harness
names, so repeated runs always write identical bytes.
"""

import os
import shutil
from pathlib import Path


def place_image() -> Path:
    repo_root = Path(__file__).resolve().parent
    image = repo_root / "entry.png"
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "entry.png"
    shutil.copyfile(image, target)
    return target


def main() -> None:
    print(place_image())


if __name__ == "__main__":
    main()
