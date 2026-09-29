# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


def collect_data_tree(source, target_prefix):
    root = Path(source)
    if not root.exists():
        return []
    datas = []
    target_root = Path(target_prefix)
    for path in root.rglob("*"):
        if path.is_file():
            datas.append((str(path), str(target_root / path.relative_to(root).parent)))
    return datas


brand_datas = collect_data_tree("assets/brand", "assets/brand")
font_datas = collect_data_tree("assets/fonts", "assets/fonts")


a = Analysis(
    ['printer_settings_launcher.py'],
    pathex=[],
    binaries=[],
    datas=brand_datas + font_datas,
    hiddenimports=['win32print'],
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
    name='프린터설정',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=r'C:\Users\Public\ChaeumLABRuntime',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/brand/chaeumlab_app_icon.ico',
)
