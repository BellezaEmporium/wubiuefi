# Copyright (c) 2008 Agostino Russo
#
# Written by Agostino Russo <agostino.russo@gmail.com>
#
# This file is part of Wubi the Win32 Ubuntu Installer.
#
# Wubi is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2.1 of
# the License, or (at your option) any later version.
#
# Wubi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
import os
import hashlib
import subprocess
import shutil
import ctypes
import logging

log = logging.getLogger("CommonBackendUtils")

def join_path(*args):
    if args and args[0] and args[0][-1] == ":":
        args = list(args)
        args[0] = args[0] + os.path.sep
    return os.path.abspath(os.path.join(*args))

def spawn_command(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE, show_window=False):
    STARTF_USESHOWWINDOW = 1
    SW_HIDE = 0
    if show_window:
        startupinfo = None
    else:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = SW_HIDE
    # stdin, stdout, and stderr must not be None:
    # http://www.py2exe.org/index.cgi/Py2ExeSubprocessInteractions
    return subprocess.Popen(command, stderr=stderr, stdin=stdin,
                               stdout=stdout, startupinfo=startupinfo,
                               shell=False)

def md5_password(password):
    """Produces an MD5 hash of the given password."""
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def run_command(command, show_window=False):
    '''
    return stdout on success or raise error
    '''
    process = spawn_command(command, show_window=show_window)
    output = b""
    errormsg = b""
    if process.stdin:
        process.stdin.close()
    if process.stdout:
        output = process.stdout.read()
    if process.stderr:
        errormsg = process.stderr.read()
    retval = process.wait()
    if retval == 0:
        return output
    else:
        raise Exception(
            "Error executing command\n>>command=%s\n>>retval=%s\n>>stderr=%s\n>>stdout=%s"
            % (" ".join(str(c) for c in command), retval, errormsg, output)
        )

def run_nonblocking_command(command, show_window=False):
    '''
    run command and return immediately
    '''
    process = spawn_command(command, show_window)
    return process.pid

def hash_password(password: str) -> str:
    """
    Produces a hashed password using SHA-512-crypt. 
    It tries to use passlib or crypt if available, and falls back to a pure Python implementation if necessary.
    """
    try:
        from passlib.hash import sha512_crypt
        return sha512_crypt.hash(password)
    except ImportError:
        pass
    try:
        import crypt # type: ignore
        return crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    except (ImportError, AttributeError):
        pass
    # Python < 3.13 fallback implementation
    return _sha512_crypt_pure(password)  # type: ignore

def get_file_hash(file_path, hash_name='md5', associated_task=None):
    if not file_path or not os.path.isfile(file_path):
        return
    file_size_mb = os.path.getsize(file_path) / (1024 ** 2)
    if associated_task:
        associated_task.unit = "MB"
        associated_task.size = file_size_mb
    h = hashlib.new(hash_name)
    bytes_read = 0
    with open(file_path, "rb") as f:
        while True:
            data = f.read(1024 ** 2)
            if not data:
                break
            h.update(data)
            bytes_read += len(data)
            if associated_task:
                if associated_task.set_progress(bytes_read / (1024 ** 2)):
                    return None
    if associated_task:
        associated_task.finish()
    return h.hexdigest()

def get_drive_space(drive_path):
    #Windows only
    freeuser = ctypes.c_int64()
    total = ctypes.c_int64()
    free = ctypes.c_int64()
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            str(drive_path),
            ctypes.byref(freeuser),
            ctypes.byref(total),
            ctypes.byref(free))
    return total.value

def copy_file(source, target, associated_task=None):
    '''
    Copy file with progress report
    '''
    file_size = None
    if os.path.isfile(source):
        file_size = os.path.getsize(source)
    elif os.path.ismount(source):
        if sys.platform.startswith("win"):
            file_size = get_drive_space(source)
            source = "\\\\.\\%s" % source[:2]

    if associated_task:
        associated_task.size = (file_size / 1024 ** 2) if file_size else 1
        associated_task.unit = "MB"

    data_read = 0
    with open(source, "rb") as source_file, open(target, "wb") as target_file:
        while True:
            data = source_file.read(1024 ** 2)
            if not data:
                break
            data_read += len(data)
            target_file.write(data)
            if associated_task:
                if associated_task.set_progress(data_read / (1024 ** 2)):
                    return

    if associated_task:
        associated_task.finish()

def reverse_list(lst):
    lst.reverse()
    return lst

def read_file(file_path, binary=False):
    if not file_path or not os.path.isfile(file_path):
        return
    f = None
    if binary:
        f = open(file_path, 'rb')
    else:
        f = open(file_path, 'r')
    content = f.read()
    f.close()
    return content

def write_file(file_path, str):
    if not file_path:
        return
    f = None
    f = open(file_path, 'w')
    f.write(str)
    f.close()

def replace_line_in_file(file_path, old_line, new_line):
    if new_line[-1] != "\n":
        new_line += "\n"
    f = open(file_path, 'r')
    lines = f.readlines()
    f.close()
    f = open(file_path, 'w')
    for i,line in enumerate(lines):
        if line.startswith(old_line):
            lines[i] = new_line
    try:
        f.writelines(lines)
    except Exception as err:
        log.exception(err)
    f.close()

def remove_line_in_file(file_path, rm_line, ignore_case=False):
    f = open(file_path, 'r')
    lines = f.readlines()
    f.close()
    f = open(file_path, 'w')
    if ignore_case:
        rm_line = rm_line.lower()
    for i,line in enumerate(lines):
        if ignore_case:
            line = line.lower()
        if line.startswith(rm_line):
            lines[i] = ""
    f.writelines(lines)
    f.close()

def find_line_in_file(file_path, text, endswith=False):
    if not file_path or not os.path.isfile(file_path):
        return
    if endswith and text[-1] != "\n":
        text += "\n"
    f = open(file_path, 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
        if (endswith and line.endswith(text)) \
        or (not endswith and line.startswith(text)):
            return line[:-1]

def unix_path(path):
    """Convert Windows path to Unix-style path"""
    path = path.replace('\\', '/')
    if len(path) > 1 and path[1] == ':':
        path = path[2:]
    if len(path) > 1 and path[-1] == '/':
        path = path[:-1]
    return path

def rm_tree(target):
    if not os.path.exists(target):
        return
    if os.path.isfile(target):
            os.unlink(target)
    elif not os.path.isdir(target):
        return
    if sys.platform.startswith("win"):
        for dir, subdirs, files in os.walk(target):
            if not files:
                continue
            for file in files:
                file = join_path(dir, file)
                run_command(['attrib', '-R', '-S', '-H', file])
    shutil.rmtree(target)