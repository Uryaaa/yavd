# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

_spec_dir = os.path.abspath(os.path.dirname(sys.argv[0])) if sys.argv else os.getcwd()
if not _spec_dir:
    _spec_dir = os.getcwd()
_icon_path = os.path.join(_spec_dir, "icon.ico")
if not os.path.exists(_icon_path):
    _icon_path = os.path.join(os.getcwd(), "icon.ico")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(_icon_path, ".")] if os.path.exists(_icon_path) else [],
    hiddenimports=[
        'PIL._tkinter_finder',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YAVDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False to hide console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon_path if os.path.exists(_icon_path) else None,  # Application icon
)
