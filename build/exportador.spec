# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para empaquetar la GUI (Fase 6) como un único .exe.

Uso (desde la raíz del proyecto, con pyinstaller instalado):
    pyinstaller build/exportador.spec

El resultado queda en dist/ExportadorIndicadores.exe. No incluye config/,
templates/ ni image/ dentro del .exe a propósito: son específicas de cada
institución/servidor y se esperan al lado del .exe (ver README, sección
"Empaquetado y distribución"), no embebidas en el binario -salvo el ícono
del propio ejecutable (build/assets/smi.ico), que PyInstaller sí incrusta.
"""

import sys
from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(PROJECT_ROOT / "gui" / "app.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    # pyodbc y dotenv a veces no se detectan solos con --onefile.
    hiddenimports=["pyodbc", "dotenv", "yaml"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ExportadorIndicadores",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # --windowed: sin consola detrás de la ventana
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "build" / "assets" / "smi.ico"),
)
