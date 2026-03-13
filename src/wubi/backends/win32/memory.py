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

import ctypes
import ctypes.wintypes
DWORD = ctypes.wintypes.DWORD

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ('dwLength',                ctypes.wintypes.DWORD),
        ('dwMemoryLoad',            ctypes.wintypes.DWORD),
        ('ullTotalPhys',            ctypes.c_uint64),
        ('ullAvailPhys',            ctypes.c_uint64),
        ('ullTotalPageFile',        ctypes.c_uint64),
        ('ullAvailPageFile',        ctypes.c_uint64),
        ('ullTotalVirtual',         ctypes.c_uint64),
        ('ullAvailVirtual',         ctypes.c_uint64),
        ('ullAvailExtendedVirtual', ctypes.c_uint64),
    ]

def get_total_memory_mb():
    mem = MEMORYSTATUSEX()
    mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
    return mem.ullTotalPhys / 1024**2
