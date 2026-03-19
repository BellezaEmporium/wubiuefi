#!/usr/bin/env python
import sys
import os
import platform
import shutil, tempfile
import atexit

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        tmp = tempfile.mkdtemp(prefix="wubi_")
        for folder in ('winboot', 'data', 'translations', 'bin'):
            src = os.path.join(sys._MEIPASS, folder)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(tmp, folder))
        atexit.register(shutil.rmtree, tmp, True)
        return tmp
    return os.path.abspath(os.path.dirname(__file__))


root_dir = get_base_path()
lib_dir = os.path.join(root_dir, 'lib')
sys.path.insert(0, lib_dir)


if platform.architecture()[0] != '64bit':
    print("We're sorry, but Wubi requires a 64-bit version of Windows to run.")
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
