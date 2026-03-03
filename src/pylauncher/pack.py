#!/usr/bin/env python
#
# Copyright (c) 2007, 2008 Agostino Russo
#
# Written by Agostino Russo <agostino.russo@gmail.com>
#
# pack.py is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or (at your option) any later version.
#
# pack.py is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


import sys
import os
import subprocess
import shutil
from os.path import abspath, join, dirname

SIGNATURE="@@@pylauncher@@@"

def ajoin(*args):
    return abspath(join(*args))

def compress(target_dir):
    #TBD the 7z compressor should be properly compiled
    cwd = os.getcwd()
    compressor = ajoin("C:", "Program Files", "7-Zip","7z.exe")
    if not os.path.exists(compressor):
        compressor = ajoin("C:", "Program Files (x86)", "7-Zip","7z.exe")

    cmd = '%s a -t7z -m0=lzma -mx=9 -mfb=256 -md=32m -ms=on ../archive.7z *'
    cmd = cmd % (compressor,)
    print(cmd)
    os.chdir(target_dir)
    subprocess.call([compressor, "a", "-t7z", "-m0=lzma", "-mx=9", "-mfb=256",
                     "-md=32m", "-ms=on", "../archive.7z", "*"])
    os.chdir(cwd)

def cat(outfile, *infiles):
    fout = open(outfile, 'wb')
    for fname in infiles:
        fin = open(abspath(fname), 'rb')
        data = fin.read()
        fin.close()
        fout.write(data)
    fout.close()

def make_self_extracting_exe(target_dir):
    header = ajoin(dirname(__file__), 'header.exe')
    archive = ajoin(dirname(target_dir),'archive.7z')
    target = ajoin(dirname(target_dir), 'application.exe')
    signature = ajoin(dirname(target_dir), 'signature')
    f = open(signature, 'wb')
    f.write(SIGNATURE.encode('utf-8'))
    f.close()
    print("Creating self extracting file %s" % target)
    cat(target, header, signature, archive)

def add_python_interpreter(target_dir):
    python_version = sys.version_info
    dll_name = 'python%d%d.dll' % (python_version.major, python_version.minor)
    
    for f in ('pylauncher.exe', dll_name, 'pyrun.exe'):
        source = ajoin(dirname(__file__), f)
        if os.path.exists(source):
            shutil.copy(source, target_dir)
        else:
            print("Warning: %s not found, skipping." % source)

def main():
    target_dir = sys.argv[1]
    add_python_interpreter(target_dir)
    compress(target_dir)
    make_self_extracting_exe(target_dir)

if __name__ == "__main__":
    main()
