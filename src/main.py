#!/usr/bin/env python
from pathlib import Path
import sys
import os
import platform
import shutil, tempfile
import atexit
import subprocess

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        tmp = Path(tempfile.mkdtemp(prefix="wubi_"))
        for folder in ('winboot', 'data', 'translations', 'bin'):
            src = str(Path(sys._MEIPASS) / folder) # type: ignore | typical for PyInstaller
            if Path(src).is_dir():
                shutil.copytree(src, str(tmp / folder))
        atexit.register(shutil.rmtree, tmp, True)
        return str(tmp)
    return str(Path(__file__).parent.resolve())


root_dir = get_base_path()
lib_dir = str(Path(root_dir) / 'lib')
sys.path.insert(0, lib_dir)


def is_hardware_64bit():
    try:
        cmd = ['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_Processor).AddressWidth']
        output = subprocess.check_output(cmd, text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip()
        return output == '64'
    except Exception:
        return '64' in platform.machine()

if not is_hardware_64bit():
    print("We're sorry, but Wubi requires a 64-bit hardware architecture to run.")
    sys.exit(1)

try:
    from version import application_name, version, revision
except ImportError:
    application_name = "wubi"
    version = "0.0"
    revision = "0"


from wubi.application import Wubi

application = Wubi(application_name, version, revision, root_dir)
application.run()
