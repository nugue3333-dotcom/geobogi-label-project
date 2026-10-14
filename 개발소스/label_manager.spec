from pathlib import Path
# -*- mode: python ; coding: utf-8 -*-



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



barcode_runtime_datas = [
    (str(path), str(path.parent))
    for directory in (Path("barcode_label_automation/resources"), Path("barcode_label_automation/vendor/zint"))
    for path in directory.rglob("*") if path.is_file()
]

a = Analysis(
    ['label_manager_launcher.py'],
    pathex=[],
    binaries=[],
    datas=brand_datas + font_datas + barcode_runtime_datas,
    hiddenimports=['openpyxl'],
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
    name='라벨출력관리',
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
    icon='assets/brand/chaeumlab_manager_icon.ico',
)
