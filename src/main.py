#!/usr/bin/env python
from pathlib import Path
import sys
import os
import platform
import subprocess


def get_base_path() -> str:
    """
    Nuitka --onefile extracts to a temp dir accessible via sys._MEIPASS
    (Nuitka sets this for compatibility). The data files land there directly
    — no need to copy them, just return the path.
    PyInstaller fallback kept for safety.
    """
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore
    # Running from source
    return str(Path(__file__).parent.resolve())


def is_hardware_64bit() -> bool:
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "(Get-CimInstance Win32_Processor).AddressWidth",
        ]
        output = subprocess.check_output(
            cmd, text=True, creationflags=subprocess.CREATE_NO_WINDOW
        ).strip()
        return output == "64"
    except Exception:
        return "64" in platform.machine()


if not is_hardware_64bit():
    print("Wubi requires a 64-bit hardware architecture.")
    sys.exit(1)


root_dir = get_base_path()

# Only needed when running from source — Nuitka bakes the packages in
src_dir = str(Path(root_dir) / "src")
if Path(src_dir).is_dir():
    sys.path.insert(0, src_dir)


try:
    from version import application_name, version, revision
except ImportError:
    application_name = "project_lubie"
    version = "0.0"
    revision = "0"


from wubi.application import Wubi

application = Wubi(application_name, version, revision, root_dir)
application.run()