#
# Copyright (c) 2007, 2008 Agostino Russo
# Python port of wubi/disckimage/main.c by Hampus Wessman
#
# Written by Agostino Russo <agostino.russo@gmail.com>
#
# win32.ui is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or (at your option) any later version.
#
# win32.ui is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

'''
Allocates disk space for the virtual disk
'''

import ctypes
from ctypes import byref, wintypes
import win32file
import win32security
import sys
import logging
from winui import defs
log = logging.getLogger('Virtualdisk')

def create_virtual_disk(path, size_mb):
    '''
    Fast allocation of disk space
    This is done by using the windows API
    The initial and final block are zeroed
    '''
    log.debug(" Creating virtual disk %s of %sMB" % (path, size_mb))
    clear_bytes = 1000000
    if not size_mb or size_mb < 1:
        return

    # Get Permission
    grant_privileges()

    # Create file
    file_handle = win32file.CreateFileW(
        str(path),
        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
        0,
        win32security.SECURITY_ATTRIBUTES(),
        win32file.CREATE_ALWAYS,
        win32file.FILE_ATTRIBUTE_NORMAL,
        None)
    if file_handle == win32file.INVALID_HANDLE_VALUE:
        log.exception("Failed to create file %s" % path)
        return
    handle = wintypes.HANDLE(int(file_handle))

    # Set pointer to end of file
    file_pos = defs.LARGE_INTEGER()
    file_pos.QuadPart = size_mb * 1024 * 1024
    result = defs.SetFilePointerEx(
                   handle,
                   ctypes.c_longlong(file_pos.QuadPart),
                   defs.NULL,
                   defs.FILE_BEGIN)
    if not result:
        log.exception("Failed to set file pointer to end of file")

    # Set end of file
    if not win32file.SetEndOfFile(file_handle):
        log.exception("Failed to extend file. Not enough free space?")

    # Set valid data (if possible), ignore errors
    call_SetFileValidData(handle, file_pos)

    # Set pointer to beginning of file
    file_pos.QuadPart = 0
    result = defs.SetFilePointerEx(
                   handle,
                   ctypes.c_longlong(file_pos.QuadPart),
                   defs.NULL,
                   defs.FILE_BEGIN)
    if not result:
        log.exception("Failed to set file pointer to beginning of file")

    # Zero chunk of file
    zero_file(handle, clear_bytes)

    # Set pointer to end - clear_bytes of file
    file_pos.QuadPart = size_mb*1024*1024 - clear_bytes
    result = defs.SetFilePointerEx(
                   handle,
                   ctypes.c_longlong(file_pos.QuadPart),
                   defs.NULL,
                   defs.FILE_BEGIN)
    if not result:
        log.exception("Failed to set file pointer to end - clear_bytes of file")

    # Zero file
    zero_file(handle, clear_bytes)


    defs.CloseHandle(handle)

def grant_privileges():
    # platform < 2 = Win9x/ME, platform 2 = WinNT/2000/XP/Vista/7/8/10
    ver = sys.getwindowsversion()
    if ver.platform < 2:
        return
    handle = ctypes.c_long(0)
    if defs.OpenProcessToken(defs.GetCurrentProcess(),
                             defs.TOKEN_ADJUST_PRIVILEGES | defs.TOKEN_QUERY,
                             byref(handle)):
        luid = defs.LUID()
        if defs.LookupPrivilegeValue(defs.NULL, defs.SE_MANAGE_VOLUME_NAME, byref(luid)):
            tp = defs.TOKEN_PRIVILEGES()
            tp.PrivilegeCount = 1
            tp.Privileges[0].Luid = luid
            tp.Privileges[0].Attributes = defs.SE_PRIVILEGE_ENABLED
            defs.AdjustTokenPrivileges(handle, defs.FALSE, byref(tp), 0,
                                       defs.NULL, defs.NULL)
        defs.CloseHandle(handle)

def call_SetFileValidData(file_handle, size_bytes):
    ver = sys.getwindowsversion()
    if ver.platform < 2:
        return
    try:
        SetFileValidData = ctypes.windll.kernel32.SetFileValidData
        if hasattr(size_bytes, 'QuadPart'):
            size_bytes = size_bytes.QuadPart
        SetFileValidData(file_handle, ctypes.c_longlong(size_bytes))
    except Exception as e:
        log.debug("SetFileValidData failed (non-fatal): %s" % e)

def zero_file(file_handle, clear_bytes):
   bytes_cleared = 0
   buf_size = 1000
   n_bytes_written = ctypes.c_ulong(0)
   write_buf = b"\x00" * buf_size

   while bytes_cleared < clear_bytes:
       bytes_to_write = buf_size
       if (bytes_to_write > clear_bytes - bytes_cleared):
           bytes_to_write = clear_bytes - bytes_cleared
       result = defs.WriteFile(
                   file_handle,
                   write_buf,
                   bytes_to_write,
                   byref(n_bytes_written),
                   defs.NULL)
       if not result or not n_bytes_written.value:
           log.exception("WriteFile() failed!")
       bytes_cleared += n_bytes_written.value
