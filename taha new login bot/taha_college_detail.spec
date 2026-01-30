# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

BASE_DIR = Path(sys.argv[0]).resolve().parent

datas = [
    (str(BASE_DIR / "web"), "web"),
    (str(BASE_DIR / "templates"), "templates"),
    (str(BASE_DIR / "drivers"), "drivers"),
    (str(BASE_DIR / "data"), "data"),
]

a = Analysis(
    ['taha_college_detail.py'],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=['seleniumwire'],
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
    name='taha_college_detail',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
