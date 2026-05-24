# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path.cwd()
SOUNDS = ROOT / "src" / "sounds_library"
ASSETS = ROOT / "assets"

datas = []

if SOUNDS.exists():
    datas.append((str(SOUNDS), "src/sounds_library"))

if ASSETS.exists():
    datas.append((str(ASSETS), "assets"))

a = Analysis(
    [str(ROOT / "src" / "cypher" / "gui.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "cypher.main",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "soundfile",
        "numpy",
        "cryptography",
        "LocalAuthentication",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "mypy",
        "ruff",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Cypher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Cypher",
)

app = BUNDLE(
    coll,
    name="Cypher.app",
    icon=None,
    bundle_identifier="com.victorbergeroux.cypher",
    info_plist={
        "CFBundleName": "Cypher",
        "CFBundleDisplayName": "Cypher",
        "CFBundleShortVersionString": "0.6.0",
        "CFBundleVersion": "0.6.0",
        "NSHighResolutionCapable": "True",
        "NSRequiresAquaSystemAppearance": "False",
    },
)
