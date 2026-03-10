# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules


a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('data', 'data'),
        ('build/bin', 'bin'),
        ('build/version.py', '.'),
        ('build/winboot', 'winboot'),
        ('build/translations', 'translations'),
        ('src/wubi', 'wubi'),
    ],
    hiddenimports=[
        'wubi',
        'wubi.application',
        'wubi.backends',
        'wubi.frontends',
    ],
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
    upx=True,
    upx_exclude=[],
    uac_admin=True,
    uac_uiaccess=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['data/images/Wubi.ico'],
)
