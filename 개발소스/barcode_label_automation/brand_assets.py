from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk


HEADER_LOGO_FILE = Path("assets") / "brand" / "chaeumlab_logo_header.png"
APP_ICON_FILE = Path("assets") / "brand" / "chaeumlab_app_icon.ico"


def load_header_logo(
    master: tk.Misc,
    *,
    base_dir: str | Path | None = None,
    install_dir: str | Path | None = None,
    max_width: int | None = None,
    max_height: int | None = None,
) -> tk.PhotoImage | None:
    for path in _asset_candidates(HEADER_LOGO_FILE, base_dir=base_dir, install_dir=install_dir):
        if not path.is_file():
            continue
        try:
            with Image.open(path) as source:
                image = source.convert("RGBA")
                image = _resize_to_fit(image, max_width=max_width, max_height=max_height)
                return ImageTk.PhotoImage(image, master=master)
        except (OSError, tk.TclError):
            continue
    return None


def _resize_to_fit(image: Image.Image, *, max_width: int | None, max_height: int | None) -> Image.Image:
    if not max_width and not max_height:
        return image
    width = max(1, image.width)
    height = max(1, image.height)
    scale = 1.0
    if max_width:
        scale = min(scale, max_width / width)
    if max_height:
        scale = min(scale, max_height / height)
    if scale >= 1:
        return image
    target = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(target, Image.Resampling.LANCZOS)


def apply_window_icon(
    window: tk.Tk | tk.Toplevel,
    *,
    base_dir: str | Path | None = None,
    install_dir: str | Path | None = None,
) -> bool:
    for path in _asset_candidates(APP_ICON_FILE, base_dir=base_dir, install_dir=install_dir):
        if not path.is_file():
            continue
        try:
            window.iconbitmap(default=str(path))
            return True
        except tk.TclError:
            continue
    return False


def _asset_candidates(
    asset_path: Path,
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
        roots.append(Path(getattr(sys, "_MEIPASS", "")))
    roots.append(Path(__file__).resolve().parents[1])

    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not str(root):
            continue
        candidate = (root / asset_path).resolve()
        if candidate in seen:
            continue
        candidates.append(candidate)
        seen.add(candidate)
    return candidates
