#!/usr/bin/env python
import sys
import os
import platform
import shutil, tempfile
import atexit
import subprocess

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        tmp = tempfile.mkdtemp(prefix="wubi_")
        for folder in ('winboot', 'data', 'translations', 'bin'):
            src = os.path.join(sys._MEIPASS, folder) # type: ignore | typical for PyInstaller
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(tmp, folder))
        atexit.register(shutil.rmtree, tmp, True)
        return tmp
    return os.path.abspath(os.path.dirname(__file__))


root_dir = get_base_path()
lib_dir = os.path.join(root_dir, 'lib')
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
