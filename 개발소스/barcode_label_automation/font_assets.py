from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path


APP_FONT_FAMILY = "머니그라피TTF Rounded"
APP_FONT_PIL_FAMILY = "MoneygraphyTTF Rounded"
APP_FONT_FILE_NAME = "MONEYGRAPHY-ROUNDED.TTF"
APP_FONT_RELATIVE_PATH = Path("assets") / "fonts" / APP_FONT_FILE_NAME
APP_FONT_SHA256 = "24e07ffaabe939ac0e6d6da90207077a47de6ebeb1df2b8dfdb8deb8e6d1a93e"
FR_PRIVATE = 0x10

_REGISTERED_FONT_PATHS: set[Path] = set()


def bundled_font_path(
    *,
    base_dir: str | Path | None = None,
    install_dir: str | Path | None = None,
) -> Path | None:
    for candidate in font_asset_candidates(base_dir=base_dir, install_dir=install_dir):
        if candidate.is_file():
            return candidate
    return None


def register_bundled_font(
    *,
    base_dir: str | Path | None = None,
    install_dir: str | Path | None = None,
) -> bool:
    path = bundled_font_path(base_dir=base_dir, install_dir=install_dir)
    if path is None:
        return False
    resolved = path.resolve()
    if resolved in _REGISTERED_FONT_PATHS:
        return True
    if os.name != "nt":
        return False
    try:
        added = ctypes.windll.gdi32.AddFontResourceExW(str(resolved), FR_PRIVATE, 0)
    except (AttributeError, OSError):
        return False
    if added <= 0:
        return False
    _REGISTERED_FONT_PATHS.add(resolved)
    return True


def font_asset_candidates(
    *,
    base_dir: str | Path | None = None,
    install_dir: str | Path | None = None,
) -> list[Path]:
    roots: list[Path] = []
    if base_dir:
        roots.append(Path(base_dir))
    if install_dir:
        roots.append(Path(install_dir))
    if getattr(sys, "frozen", False):
        mei_root = str(getattr(sys, "_MEIPASS", ""))
        if mei_root:
            roots.append(Path(mei_root))
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path(__file__).resolve().parents[1])

    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        candidate = (root / APP_FONT_RELATIVE_PATH).resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates
