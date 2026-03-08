# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(SPEC))

block_cipher = None

# Collect data files for minecraft_launcher_lib
minecraft_data = collect_data_files('minecraft_launcher_lib')

# Collect all submodules for minecraft_launcher_lib
minecraft_modules = collect_submodules('minecraft_launcher_lib')

# Main application
a = Analysis(
    ['launcher.py'],
    pathex=[current_dir],
    binaries=[],
    datas=minecraft_data + [('README.md', '.')],  # Include README if it exists
    hiddenimports=[
        'minecraft_launcher_lib',
        'minecraft_launcher_lib.install',
        'minecraft_launcher_lib.command',
        'minecraft_launcher_lib.versions',
        'minecraft_launcher_lib.fabric',
        'minecraft_launcher_lib.quilt',
        'minecraft_launcher_lib.forge',
        'customtkinter',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL._tkinter_finder',
        'PIL._imagingtk',
        'PIL._imaging',
        'requests',
        'json',
        'threading',
        'subprocess',
        'zipfile',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        'tkinter.Menu',
        'io',
        're',
        'shutil',
        'os',
        'sys'
    ] + minecraft_modules,
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
    name='OrbusLauncher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,  # Add Windows icon if available
)
