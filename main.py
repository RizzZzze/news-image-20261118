#!/usr/bin/env python3
"""Copy the rendered newspaper image to the output directory.

The entry image lives in this repository as entry.png (rendered from
render.html by render.sh). This program only copies it, so repeated
runs write identical bytes.
"""
import os
import shutil


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "entry.png")
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    dst = os.path.join(outdir, "entry.png")
    shutil.copyfile(src, dst)
    print(dst)


if __name__ == "__main__":
    main()
