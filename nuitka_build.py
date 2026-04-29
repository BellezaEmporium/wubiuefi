#!/usr/bin/env python3
"""
Nuitka build script for wubiuefi.
Replaces wubi.spec (PyInstaller).

Usage:
    python tools/build_nuitka.py [--onefile] [--show-progress]
"""
from __future__ import annotations

import subprocess
import sys
import os
from src.version import version, revision, application_name

ROOT            = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC             = os.path.join(ROOT, "wubiuefi", "src")
MAIN            = os.path.join(SRC, "wubi", "application.py")
ICON            = os.path.join(ROOT, "wubiuefi", "data", "images", "Wubi.ico")
DATA            = os.path.join(ROOT, "wubiuefi", "data")
TRANSLATIONS    = os.path.join(ROOT, "wubiuefi", "build", "translations")

cmd = [
    sys.executable, "-m", "nuitka",

    # ── Output ────────────────────────────────────────────────────
    "--onefile",                          # single .exe
    "--output-dir=wubiuefi/dist",
    "--output-filename=wubi.exe",

    # ── Windows ───────────────────────────────────────────────────
    "--windows-console-mode=disable",     # no console window
    f"--windows-icon-from-ico={ICON}",
    "--company-name=BellezaEmporium",
    f"--product-name={application_name}",
    f"--file-version={version}.{revision}",        # e.g. "24.04.4.347"
    f"--product-version={version}.{revision}",     # Nuitka needs both
    f"--file-description=Linux installer for Windows",
    "--windows-uac-admin",              # request admin privileges on launch, for bcdedit checks & changes

    # ── Packages to include ───────────────────────────────────────
    "--include-package=wubi",
    "--include-package=wubi.backends",
    "--include-package=wubi.backends.mixins",
    "--include-package=wubi.backends.utils",
    "--include-package=wubi.backends.data",
    "--include-package=wubi.frontends",

    # ── Data files ────────────────────────────────────────────────
    f"--include-data-dir={DATA}=data",
    f"--include-data-dir={TRANSLATIONS}=translations",
    f"--include-data-files={os.path.join(SRC, 'version.py')}=version.py",

    # ── httpx / certifi (needs explicit inclusion) ─────────────────
    "--include-package=httpx",
    "--include-package=certifi",
    "--include-package=httpcore",

    # ── Other deps ────────────────────────────────────────────────
    "--include-package=py7zr",
    "--include-package=yaml",
    "--enable-plugin=tk-inter",

    # ── Python path so `from wubi import ...` resolves ────────────
    "--include-package-data=wubi",

    # ── Optimisation ─────────────────────────────────────────────
    "--follow-imports",
    "--remove-output",                    # clean build dir after packaging

    # ── Misc ──────────────────────────────────────────────────────
    "--assume-yes-for-downloads",         # auto-download Nuitka deps
    "--show-progress",
    "--show-memory",

    MAIN,
]

os.chdir(ROOT)
sys.path.insert(0, SRC)              # so Nuitka can resolve wubi.

env = os.environ.copy()
env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")

print("Running:", " ".join(cmd))
result = subprocess.run(cmd, env=env)
sys.exit(result.returncode)