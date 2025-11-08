#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a local Gaia DR3 variable-star catalog from VizieR (I/358, Part 4: Variability).

Downloads:
  - ReadMe (table layout for CDS parser)
  - vclassre.dat.gz (variability classifier results; includes source_id, RAdeg, DEdeg, best class)

Outputs (downloaded into gui/mpc_variables/):
  - gui/mpc_variables/ReadMe
  - gui/mpc_variables/vclassre.dat.gz

The application code has been updated to:
  - detect and read CDS ASCII (with ReadMe) directly
  - accept RAdeg/DEdeg column names
  - treat magnitude as optional when absent

Usage (Windows):
  C:\Python\Python310\python.exe tools\\build_gaia_variables.py
"""
import os
import sys
import urllib.request
from pathlib import Path

VIZ_ROOT = "https://cdsarc.cds.unistra.fr/ftp/cats/I/358/"
FILES = {
    "ReadMe": VIZ_ROOT + "ReadMe",
    "vclassre.dat.gz": VIZ_ROOT + "vclassre.dat.gz",
}

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "gui" / "mpc_variables"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading: {url}\n -> {dest}")
    urllib.request.urlretrieve(url, dest)


def ensure_files():
    for name, url in FILES.items():
        dest = OUT_DIR / name
        if not dest.exists():
            download(url, dest)
        else:
            print(f"Already exists: {dest}")


def validate_read():
    readme = OUT_DIR / "ReadMe"
    dat_gz = OUT_DIR / "vclassre.dat.gz"
    ok = True
    if not readme.exists():
        print("Missing ReadMe")
        ok = False
    if not dat_gz.exists():
        print("Missing vclassre.dat.gz")
        ok = False
    if not ok:
        return 1

    # Lightweight validation: check that ReadMe declares table 'vclassre.dat'
    try:
        txt = readme.read_text(encoding="utf-8", errors="ignore")
        declared = "vclassre.dat" in txt
        print("ReadMe declares vclassre.dat:", declared)
        return 0 if declared else 2
    except Exception as e:
        print("ERROR: failed to read ReadMe:", e)
        return 2


def main():
    print("Output directory:", OUT_DIR)
    ensure_files()
    rc = validate_read()
    if rc != 0:
        print("Validation failed. You can still use the downloaded files with the app if astropy is available.")
    else:
        print("Validation OK. You can now set local VSX path to vclassre.dat.gz (or leave default).")


if __name__ == "__main__":
    sys.exit(main())

