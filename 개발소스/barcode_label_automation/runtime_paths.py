from __future__ import annotations

import os
import shutil
import sys
import uuid
from pathlib import Path


APP_DATA_VENDOR_DIR_NAME = "ChaeumLAB"
APP_DATA_PRODUCT_DIR_NAME = "LabelPrint"
LEGACY_APP_DATA_DIR_NAME = "GeobogiLabel"
SEED_FILES = (
    "config.ini",
    "config.example.ini",
    "barcode_db.xlsx",
    "print_queue.xlsx",
    "labels.xlsm",
    "sample_direct_open.gblabel",
)
SEED_DIRS = ("templates", "db", "assets", "tools")


def executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def runtime_base_dir(install_dir: Path | None = None) -> Path:
    source_dir = (install_dir or executable_dir()).resolve()
    if _requires_user_data_dir(source_dir):
        return ensure_user_data_dir(source_dir)
    return source_dir


def ensure_user_data_dir(install_dir: Path) -> Path:
    target = _local_app_data_dir()
    _migrate_legacy_user_data(target)
    target.mkdir(parents=True, exist_ok=True)
    _copy_seed_files(install_dir, target)
    return target


def _local_app_data_dir() -> Path:
    return _base_local_app_data_dir() / APP_DATA_VENDOR_DIR_NAME / APP_DATA_PRODUCT_DIR_NAME


def _legacy_local_app_data_dir() -> Path:
    return _base_local_app_data_dir() / LEGACY_APP_DATA_DIR_NAME


def _base_local_app_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data)
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return Path(user_profile) / "AppData" / "Local"
    public_profile = os.environ.get("PUBLIC")
    if public_profile:
        return Path(public_profile) / "Documents"
    system_drive = os.environ.get("SystemDrive")
    if system_drive:
        return Path(system_drive) / "Users" / "Public" / "Documents"
    try:
        return Path.home() / "AppData" / "Local"
    except RuntimeError:
        return Path("C:/Users/Public/Documents")


def _migrate_legacy_user_data(target_dir: Path) -> None:
    legacy_dir = _legacy_local_app_data_dir()
    if target_dir.exists() or not legacy_dir.exists() or not legacy_dir.is_dir():
        return
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(legacy_dir, target_dir)


def _requires_user_data_dir(path: Path) -> bool:
    return _is_restricted_install_dir(path) or not _can_write_to_dir(path)


def _is_restricted_install_dir(path: Path) -> bool:
    value = str(path.resolve()).casefold()
    candidates = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramW6432"),
    ]
    for candidate in candidates:
        if candidate and value.startswith(str(Path(candidate).resolve()).casefold()):
            return True
    return value.startswith("c:\\program files")


def _can_write_to_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write_probe_{uuid.uuid4().hex}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _copy_seed_files(source_dir: Path, target_dir: Path) -> None:
    for file_name in SEED_FILES:
        source = source_dir / file_name
        target = target_dir / file_name
        if not source.exists():
            continue
        if file_name == "config.ini":
            _copy_config_if_missing(source, target)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for dir_name in SEED_DIRS:
        source = source_dir / dir_name
        target = target_dir / dir_name
        if source.exists() and not target.exists():
            shutil.copytree(source, target)


def _copy_config_if_missing(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(source, target)
