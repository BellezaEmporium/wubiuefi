# Copyright (c) 2008 Agostino Russo
#
# Written by Agostino Russo <agostino.russo@gmail.com>
#
# This file is part of Wubi the Win32 Ubuntu Installer.
#
# Wubi is free software; you can redistribute it and/or modify
# it under 5the terms of the GNU Lesser General Public License as
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

import ctypes
from winui.defs import FILE_SHARE_READ, FILE_SHARE_WRITE, GENERIC_READ, OPEN_EXISTING
IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808

def eject_cd(cd_path):
    if not cd_path:
        return
    create_file = ctypes.windll.kernel32.CreateFileW  # W, pas A
    create_file.restype = ctypes.c_void_p
    cd_handle = create_file(
        "\\\\.\\%s" % cd_path[:2],
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None)
    if cd_handle and cd_handle != ctypes.c_void_p(-1).value:
        x = ctypes.c_int()
        ctypes.windll.kernel32.DeviceIoControl(
            cd_handle, IOCTL_STORAGE_EJECT_MEDIA,
            None, 0, None, 0, ctypes.byref(x), None)
        ctypes.windll.kernel32.CloseHandle(cd_handle)
