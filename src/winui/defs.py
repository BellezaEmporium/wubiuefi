#
# Copyright (c) 2007, 2008 Agostino Russo
#
# Written by Agostino Russo <agostino.russo@gmail.com>
#
# winui is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or (at your option) any later version.
#
# winui is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

'''
win32 constants, structures and functions
'''

import ctypes
import ctypes.wintypes as wintypes
import win32con
from ctypes.wintypes import (
    HWND, HMENU, HINSTANCE, HICON,
    UINT, WPARAM, LPARAM, ATOM
)

# Common control constants can be missing from some win32con builds/stubs.
TCIF_TEXT = getattr(win32con, 'TCIF_TEXT', 0x0001)
TCIF_PARAM = getattr(win32con, 'TCIF_PARAM', 0x0008)
TCM_FIRST = getattr(win32con, 'TCM_FIRST', 0x1300)
TCM_INSERTITEM = getattr(win32con, 'TCM_INSERTITEM', TCM_FIRST + 62)
PBM_FIRST = getattr(win32con, 'PBM_FIRST', 0x0400)
PBM_SETPOS = getattr(win32con, 'PBM_SETPOS', PBM_FIRST + 2)
PBM_GETPOS = getattr(win32con, 'PBM_GETPOS', PBM_FIRST + 8)
PBM_SETBARCOLOR = getattr(win32con, 'PBM_SETBARCOLOR', PBM_FIRST + 9)
PBM_SETBKCOLOR = getattr(win32con, 'PBM_SETBKCOLOR', PBM_FIRST + 1)
TTS_ALWAYSTIP = getattr(win32con, 'TTS_ALWAYSTIP', 0x0001)

LF_FACESIZE = 32
HCURSOR   = ctypes.c_void_p
LRESULT   = ctypes.c_long
ATOM      = ctypes.c_ushort
WNDPROC   = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", wintypes.HDC),
                ("fErase", wintypes.BOOL),
                ("rcPaint", wintypes.RECT),
                ("fRestore", wintypes.BOOL),
                ("fIncUpdate", wintypes.BOOL),
                ("rgbReserved", wintypes.LPCSTR * 32)]

class TCITEM(ctypes.Structure):
    _fields_ = [("mask", wintypes.UINT),
                ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD),
                ("pszText", wintypes.LPWSTR),
                ("cchTextMax", wintypes.INT),
                ("iImage", wintypes.INT),
                ("lParam", wintypes.LPARAM)]

class WNDCLASSEX(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT),
                ('style', wintypes.UINT),
                ('lpfnWndProc', WNDPROC), 
                ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int),
                ('hInstance', wintypes.HINSTANCE),
                ('hIcon', wintypes.HICON),
                ('hCursor', HCURSOR),
                ('hbrBackground', wintypes.HBRUSH),
                ('lpszMenuName', ctypes.c_wchar_p),
                ('lpszClassName', ctypes.c_wchar_p),
                ("hIconSm", wintypes.HICON)]

    def __init__(self,
                 wndProc,
                 className,
                 style=None,
                 clsExtra=0,
                 wndExtra=0,
                 menuName=None,
                 instance=None,
                 icon=None,
                 iconsm=None,
                 cursor=None,
                 background=None,
                 ):

        if style is None:
            style = win32con.CS_HREDRAW | win32con.CS_VREDRAW
        if not instance:
            instance = ctypes.windll.kernel32.GetModuleHandleW(None)
        if not icon:
            icon = ctypes.windll.user32.LoadIconW(None, ctypes.c_wchar_p(win32con.IDI_APPLICATION))
        if not iconsm:
            iconsm = icon
        if not cursor:
            cursor = ctypes.windll.user32.LoadCursorW(None, ctypes.c_wchar_p(win32con.IDC_ARROW))
        if not background:
            background = win32con.COLOR_WINDOW + 1

        self.cbSize = ctypes.sizeof(self)
        self.lpfnWndProc = WNDPROC(wndProc)
        self.style = style
        self.cbClsExtra = clsExtra
        self.cbWndExtra = wndExtra
        self.hInstance = instance
        self.hIcon = icon
        self.hIconSm = iconsm
        self.hCursor = cursor
        self.hbrBackground = background
        self.lpszMenuName = None if menuName is None else str(menuName)
        self.lpszClassName = str(className)

def ErrorIfZero(handle):
    if handle == 0:
        raise ctypes.WinError()
    else:
        return handle

CreateWindowEx = ctypes.windll.user32.CreateWindowExW
CreateWindowEx.restype = ErrorIfZero
CreateWindowEx.argtypes = [
    wintypes.DWORD,      # dwExStyle
    ctypes.c_wchar_p,    # lpClassName
    ctypes.c_wchar_p,    # lpWindowName
    wintypes.DWORD,      # dwStyle
    ctypes.c_int,        # X
    ctypes.c_int,        # Y
    ctypes.c_int,        # nWidth
    ctypes.c_int,        # nHeight
    HWND,                # hWndParent
    HMENU,               # hMenu
    HINSTANCE,           # hInstance
    ctypes.c_void_p,     # lpParam
]

RegisterClassExW = ctypes.windll.user32.RegisterClassExW
RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEX)]
RegisterClassExW.restype = ATOM

DefWindowProcW = ctypes.windll.user32.DefWindowProcW
DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
DefWindowProcW.restype = LRESULT

GetModuleHandleW = ctypes.windll.kernel32.GetModuleHandleW
GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
GetModuleHandleW.restype = HINSTANCE

LoadIconW = ctypes.windll.user32.LoadIconW
LoadIconW.argtypes = [HINSTANCE, ctypes.c_wchar_p]
LoadIconW.restype = HICON

LoadCursorW = ctypes.windll.user32.LoadCursorW
LoadCursorW.argtypes = [HINSTANCE, ctypes.c_wchar_p]
LoadCursorW.restype = HCURSOR

SELF_HWND = object() #on instanciation the value has to be replaced with self._hwnd
PARENT_HWND = object() #on instanciation the value has to be replaced with self.parent._hwnd
APPLICATION_HINSTANCE = object() #on instanciation the value has to be replaced with self.application._hinstance


def RGB(r,g,b):
    return r | (g<<8) | (b<<16)

class LOGFONT(ctypes.Structure):
    _fields_ = [("lfHeight", wintypes.LONG),
                ("lfWidth", wintypes.LONG),
                ("lfEscapement", wintypes.LONG),
                ("lfOrientation", wintypes.LONG),
                ("lfWeight", wintypes.LONG),
                ("lfItalic", wintypes.BYTE),
                ("lfUnderline", wintypes.BYTE),
                ("lfStrikeOut", wintypes.BYTE),
                ("lfCharSet", wintypes.BYTE),
                ("lfOutPrecision", wintypes.BYTE),
                ("lfClipPrecision", wintypes.BYTE),
                ("lfQuality", wintypes.BYTE),
                ("lfPitchAndFamily", wintypes.BYTE),
                ("lfFaceName", ctypes.c_wchar_p * LF_FACESIZE)]

class LUID(ctypes.Structure):
    _fields_ = [
        # C:/PROGRA~1/gccxml/bin/Vc6/Include/winnt.h 394
        ('LowPart', wintypes.DWORD),
        ('HighPart', wintypes.LONG),
        ]

class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        # C:/PROGRA~1/gccxml/bin/Vc6/Include/winnt.h 3241
        ('Luid', LUID),
        ('Attributes', wintypes.DWORD),
        ]

class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        # C:/PROGRA~1/gccxml/bin/Vc6/Include/winnt.h 4188
        ('PrivilegeCount', wintypes.DWORD),
        ('Privileges', LUID_AND_ATTRIBUTES * 1),
        ]

class LARGE_INTEGER(ctypes.Structure):
    _fields_ = [
        ('QuadPart', ctypes.c_longlong),
        ]

# Constants and API bindings used by win32 backend helpers.
NULL = 0
FALSE = 0
FILE_BEGIN = 0
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002

CloseHandle = ctypes.windll.kernel32.CloseHandle
SetFilePointerEx = ctypes.windll.kernel32.SetFilePointerEx
SetEndOfFile = ctypes.windll.kernel32.SetEndOfFile
WriteFile = ctypes.windll.kernel32.WriteFile
OpenProcessToken = ctypes.windll.advapi32.OpenProcessToken
GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
LookupPrivilegeValue = ctypes.windll.advapi32.LookupPrivilegeValueW
AdjustTokenPrivileges = ctypes.windll.advapi32.AdjustTokenPrivileges

SE_MANAGE_VOLUME_NAME = "SeManageVolumePrivilege"
