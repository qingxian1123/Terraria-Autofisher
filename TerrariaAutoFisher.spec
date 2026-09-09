# -*- mode: python ; coding: utf-8 -*-
"""Single-file Windows build; paths are relative to this spec, not the shell."""

from pathlib import Path
import runpy

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
version = runpy.run_path(str(root / "autofisher" / "__init__.py"))["__version__"]
runtime = root / "injector" / "runtime-v2"
if not (runtime / "TerrariaAutoFisher.Injector.exe").is_file():
    raise SystemExit("Build injector first, or run: python tools/build.py")

datas, binaries, hiddenimports = collect_all("vgamepad")
datas.append((str(root / "assets"), "assets"))
datas.extend(
    (str(path), "injector/runtime-v2")
    for path in sorted(runtime.iterdir())
    if path.suffix.lower() in {".exe", ".dll", ".config"}
)

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=binaries,
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
    name=f"TerrariaAutoFisher-v{version}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
)
