from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import winreg
from dataclasses import dataclass
from pathlib import Path


LABEL_EXTENSION = ".gblabel"
LABEL_PROG_ID = "ChaeumLAB.LabelFile"
LEGACY_PROG_IDS = ("GeobogiDream.LabelFile",)
LABEL_ICON_RELATIVE_PATH = Path("assets") / "brand" / "chaeumlab_label_file_icon_white.ico"
STABLE_ICON_DIRECTORY = Path("ChaeumLAB") / "icons"
LEGACY_STABLE_ICON_RELATIVE_PATH = STABLE_ICON_DIRECTORY / "chaeumlab_label_file.ico"


@dataclass(frozen=True)
class FileAssociationResult:
    registered: bool
    icon_path: Path | None = None
    error: str = ""


def ensure_label_file_association(
    designer_exe: str | Path,
    *,
    icon_source: str | Path | None = None,
    local_app_data: str | Path | None = None,
) -> FileAssociationResult:
    """Register the portable designer and keep the document icon at a stable path."""
    if os.name != "nt":
        return FileAssociationResult(False, error="Windows에서만 파일 연결을 등록할 수 있습니다.")

    exe_path = Path(designer_exe).resolve()
    if not exe_path.is_file():
        return FileAssociationResult(False, error=f"라벨 디자이너를 찾을 수 없습니다: {exe_path}")

    source = Path(icon_source).resolve() if icon_source else exe_path.parent / LABEL_ICON_RELATIVE_PATH
    local_root = local_app_data_dir(local_app_data)
    stable_icon = local_root / _versioned_icon_relative_path(source) if source.is_file() else exe_path

    try:
        icon_path = _install_stable_icon(source, stable_icon, fallback=exe_path)
        _write_file_association(exe_path, icon_path)
        _remove_legacy_associations()
        _notify_shell_association_changed()
    except OSError as exc:
        return FileAssociationResult(False, error=str(exc))

    return FileAssociationResult(True, icon_path=icon_path)


def local_app_data_dir(value: str | Path | None = None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    env_value = os.environ.get("LOCALAPPDATA", "").strip()
    if env_value:
        return Path(env_value).resolve()
    if os.name == "nt":
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x001C, None, 0, buffer) == 0 and buffer.value:
            return Path(buffer.value).resolve()
    try:
        return (Path.home() / "AppData" / "Local").resolve()
    except RuntimeError:
        return Path("C:/Users/Public/Documents").resolve()


def _versioned_icon_relative_path(source: Path) -> Path:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    return STABLE_ICON_DIRECTORY / f"chaeumlab_label_file_{digest}.ico"


def _install_stable_icon(source: Path, destination: Path, *, fallback: Path) -> Path:
    if not source.is_file():
        return destination if destination.is_file() else fallback
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file() or source.read_bytes() != destination.read_bytes():
        shutil.copy2(source, destination)
    return destination


def _write_file_association(exe_path: Path, icon_path: Path) -> None:
    classes_root = r"Software\Classes"
    _set_default_value(fr"{classes_root}\{LABEL_EXTENSION}", LABEL_PROG_ID)
    _set_default_value(fr"{classes_root}\{LABEL_PROG_ID}", "채움랩 라벨 파일")
    _set_default_value(fr"{classes_root}\{LABEL_PROG_ID}\DefaultIcon", f'"{icon_path}",0')
    _set_default_value(fr"{classes_root}\{LABEL_PROG_ID}\shell\open\command", f'"{exe_path}" "%1"')
    _set_default_value(
        fr"{classes_root}\{LABEL_PROG_ID}\shell\print\command",
        f'"{exe_path}" --print "%1"',
    )

    open_with_key = fr"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{LABEL_EXTENSION}\OpenWithProgids"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, open_with_key, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, LABEL_PROG_ID, 0, winreg.REG_NONE, b"")


def _set_default_value(subkey: str, value: str) -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, value)


def _remove_legacy_associations() -> None:
    open_with_key = fr"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{LABEL_EXTENSION}\OpenWithProgids"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            open_with_key,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            for prog_id in LEGACY_PROG_IDS:
                try:
                    winreg.DeleteValue(key, prog_id)
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        pass

    for prog_id in LEGACY_PROG_IDS:
        _delete_registry_tree(winreg.HKEY_CURRENT_USER, fr"Software\Classes\{prog_id}")


def _delete_registry_tree(root: int, subkey: str) -> None:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            children: list[str] = []
            index = 0
            while True:
                try:
                    children.append(winreg.EnumKey(key, index))
                    index += 1
                except OSError:
                    break
    except FileNotFoundError:
        return

    for child in children:
        _delete_registry_tree(root, fr"{subkey}\{child}")
    try:
        winreg.DeleteKey(root, subkey)
    except FileNotFoundError:
        pass


def _notify_shell_association_changed() -> None:
    shcne_assocchanged = 0x08000000
    shcnf_idlist = 0x0000
    ctypes.windll.shell32.SHChangeNotify(shcne_assocchanged, shcnf_idlist, None, None)
