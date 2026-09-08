# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para la variante interina de la GUI
(gui/app_test_mssql.py): usa SQL Server tanto para el catálogo como para el
data warehouse, mientras el conector Oracle real siga pendiente. Ver
gui/app_test_mssql.py y README ("Pendiente de Fase 2").

Uso (desde la raíz del proyecto, con pyinstaller instalado):
    pyinstaller build/exportador_test_mssql.spec

El resultado queda en dist/ExportadorIndicadores_PRUEBA.exe -nombre
deliberadamente distinto al .exe final (ExportadorIndicadores.exe) para que
no se confundan ni se pisen entre sí. Es transitorio: cuando el conector
Oracle esté implementado, se deja de generar y se usa
build/exportador.spec directamente.
"""

from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(PROJECT_ROOT / "gui" / "app_test_mssql.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
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
    name="ExportadorIndicadores_PRUEBA",
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
    icon=str(PROJECT_ROOT / "build" / "assets" / "smi.ico"),
)
