# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
import sys, os

tk_datas = collect_data_files('tkinter')
tcl_path = os.path.join(sys.prefix, 'tcl')
tk_path  = os.path.join(sys.prefix, 'Lib', 'tkinter')

hiddenimports = (
    collect_submodules('wubi')
    + collect_submodules('aiotorrent')
    + collect_submodules('bitstring')
    + collect_submodules('bitarray')
    + collect_submodules('pywin32')
    + [
        'bitstring.bitstore_bitarray',
        'bitstring.bitstore',
        'bitarray',
        'bitarray._bitarray',
        'fastbencode',
    ]
)

datas=[
    ('data', 'data'),
    ('build/bin', 'bin'),
    ('build/version.py', '.'),
    ('build/winboot', 'winboot'),
    ('build/translations', 'translations'),
    ('src/wubi', 'wubi'),
] + tk_datas

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='wubi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    uac_admin=True,
    uac_uiaccess=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['data/images/Wubi.ico'],
)