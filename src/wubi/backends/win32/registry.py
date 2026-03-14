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

import winreg
import logging
log = logging.getLogger("registry")

KEY_WOW64_64KEY = 0x0100

def get_value(key, subkey, attr):
    hkey = getattr(winreg, key)
    for flags in [KEY_WOW64_64KEY, 0]: # try 64-bit view first, then 32-bit view
        try:
            handle = winreg.OpenKey(hkey, subkey,
                                    access=winreg.KEY_READ | flags)
            value, _ = winreg.QueryValueEx(handle, attr)
            winreg.CloseKey(handle)
            return value
        except OSError:
            continue
    return None

def set_value(key, subkey, attr, value):
    hkey = getattr(winreg, key)
    try:
        handle = winreg.OpenKey(hkey, subkey,
                                access=winreg.KEY_SET_VALUE | KEY_WOW64_64KEY)
    except OSError:
        handle = winreg.CreateKeyEx(hkey, subkey,
                                    access=winreg.KEY_SET_VALUE | KEY_WOW64_64KEY)
    try:
        winreg.SetValueEx(handle, attr, 0, winreg.REG_SZ, str(value))
    except Exception as err:
        log.exception("Cannot set registry key %s\\%s = %s\n%s" % (subkey, attr, value, err))
    finally:
        winreg.CloseKey(handle)

def delete_key(key, subkey):
    key = getattr(winreg, key)
    try:
        winreg.DeleteKey(key, subkey)
    except Exception as err:
        log.exception("Cannot delete registry key %s\n%s" % (subkey, err))
