from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import shutil
import winreg
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .label_file_types import LABEL_FILE_EXTENSION, LEGACY_LABEL_FILE_EXTENSION, PROJECT_FILE_EXTENSIONS


LABEL_EXTENSION = LABEL_FILE_EXTENSION
LABEL_PROG_ID = "ChaeumLAB.LabelDocument.1"
LEGACY_LABEL_PROG_ID = "ChaeumLAB.LabelFile"
PROJECT_PROG_ID = "ChaeumLAB.LabelProject.1"
LEGACY_PROG_IDS = ("GeobogiDream.LabelFile",)
LABEL_ICON_RELATIVE_PATH = Path("assets") / "brand" / "chaeumlab_label_file_icon_white.ico"
PROJECT_ICON_RELATIVE_PATH = Path("assets") / "brand" / "chaeumlab_project_file_icon_white.ico"
STABLE_ICON_DIRECTORY = Path("ChaeumLAB") / "icons"
LEGACY_STABLE_ICON_RELATIVE_PATH = STABLE_ICON_DIRECTORY / "chaeumlab_label_file.ico"
_CLASSES_ROOT = r"Software\Classes"
_ROLLBACK_FORMAT = "chaeumlab-file-association-rollback"
_OWNED_ROOTS = tuple(
    fr"{_CLASSES_ROOT}\{name}"
    for name in (LABEL_EXTENSION, LEGACY_LABEL_FILE_EXTENSION, *PROJECT_FILE_EXTENSIONS,
                 LABEL_PROG_ID, LEGACY_LABEL_PROG_ID, PROJECT_PROG_ID, *LEGACY_PROG_IDS)
)


@dataclass(frozen=True)
class FileAssociationResult:
    registered: bool
    icon_path: Path | None = None
    error: str = ""
    project_icon_path: Path | None = None
    rollback_path: Path | None = None


@dataclass(frozen=True)
class _RegistryWrite:
    key: str
    name: str
    value: str | bytes
    value_type: int


def ensure_label_file_association(
    designer_exe: str | Path,
    *,
    icon_source: str | Path | None = None,
    project_icon_source: str | Path | None = None,
    local_app_data: str | Path | None = None,
) -> FileAssociationResult:
    """Register candidates without changing another application or UserChoice."""
    if os.name != "nt":
        return FileAssociationResult(False, error="Windows에서만 파일 연결을 등록할 수 있습니다.")
    exe_path = Path(designer_exe).resolve()
    if not exe_path.is_file():
        return FileAssociationResult(False, error=f"라벨 디자이너를 찾을 수 없습니다: {exe_path}")
    local_root = local_app_data_dir(local_app_data)
    source = Path(icon_source).resolve() if icon_source else exe_path.parent / LABEL_ICON_RELATIVE_PATH
    project_source = Path(project_icon_source).resolve() if project_icon_source else exe_path.parent / PROJECT_ICON_RELATIVE_PATH
    rollback_path: Path | None = None
    snapshot: dict[str, object] | None = None
    try:
        icon_path = _cached_icon(source, local_root, "label", exe_path)
        project_icon_path = _cached_icon(project_source, local_root, "project", exe_path)
        writes = _association_writes(exe_path, icon_path, project_icon_path)
        snapshot = _snapshot_changes(writes)
        if snapshot["changes"]:
            rollback_path = _save_snapshot(local_root, snapshot)
            for change in snapshot["changes"]:
                _write_change(change)
            _notify_shell_association_changed()
    except (OSError, ValueError) as exc:
        error = str(exc)
        if snapshot and snapshot.get("changes"):
            try:
                _restore_snapshot(snapshot)
            except OSError as restore_error:
                error += f"\n자동 파일 연결 복원 실패: {restore_error}"
        return FileAssociationResult(False, error=error, rollback_path=rollback_path)
    return FileAssociationResult(True, icon_path=icon_path, project_icon_path=project_icon_path, rollback_path=rollback_path)


def restore_file_association(snapshot_path: str | Path) -> FileAssociationResult:
    """Restore only values still equal to this registration's writes."""
    path = Path(snapshot_path).resolve()
    try:
        if path.stat().st_size > 1024 * 1024:
            raise ValueError("파일 연결 복원 기록이 허용 크기를 넘습니다.")
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        _validate_snapshot(snapshot)
        _restore_snapshot(snapshot)
        _notify_shell_association_changed()
    except (OSError, ValueError, TypeError) as exc:
        return FileAssociationResult(False, error=f"파일 연결을 복원하지 못했습니다: {exc}", rollback_path=path)
    return FileAssociationResult(True, rollback_path=path)


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


def _cached_icon(source: Path, local_root: Path, role: str, fallback: Path) -> Path:
    if not source.is_file():
        return fallback
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    destination = local_root / STABLE_ICON_DIRECTORY / f"chaeumlab_{role}_file_{digest}.ico"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file() or source.read_bytes() != destination.read_bytes():
        shutil.copy2(source, destination)
    return destination


def _read_value(root: int, subkey: str, name: str = "") -> tuple[object, int] | None:
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as key:
            return winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None


def _key_exists(subkey: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ):
            return True
    except FileNotFoundError:
        return False


def _association_writes(exe_path: Path, icon_path: Path, project_icon_path: Path) -> list[_RegistryWrite]:
    writes: list[_RegistryWrite] = []
    associations = ((LABEL_EXTENSION, LABEL_PROG_ID), (LEGACY_LABEL_FILE_EXTENSION, LEGACY_LABEL_PROG_ID),
                    *((extension, PROJECT_PROG_ID) for extension in PROJECT_FILE_EXTENSIONS))
    legacy_ids: set[str] = set()
    for extension, prog_id in associations:
        key = fr"{_CLASSES_ROOT}\{extension}"
        default = _read_value(winreg.HKEY_CURRENT_USER, key) or _read_value(winreg.HKEY_LOCAL_MACHINE, key)
        if default is None or not default[0]:
            writes.append(_RegistryWrite(key, "", prog_id, winreg.REG_SZ))
        elif extension == LEGACY_LABEL_FILE_EXTENSION and default[0] in LEGACY_PROG_IDS:
            legacy_ids.add(str(default[0]))
        writes.append(_RegistryWrite(fr"{key}\OpenWithProgids", prog_id, b"", winreg.REG_NONE))
    for prog_id in (LABEL_PROG_ID, LEGACY_LABEL_PROG_ID, PROJECT_PROG_ID, *sorted(legacy_ids)):
        is_project = prog_id == PROJECT_PROG_ID
        key = fr"{_CLASSES_ROOT}\{prog_id}"
        icon = project_icon_path if is_project else icon_path
        command = f'"{exe_path}" --import-project "%1"' if is_project else f'"{exe_path}" "%1"'
        writes.extend((
            _RegistryWrite(key, "", "채움랩 이동 프로젝트" if is_project else "채움랩 라벨 도안", winreg.REG_SZ),
            _RegistryWrite(fr"{key}\DefaultIcon", "", f'"{icon}",0', winreg.REG_SZ),
            _RegistryWrite(fr"{key}\shell\open\command", "", command, winreg.REG_SZ),
        ))
        if not is_project:
            writes.append(_RegistryWrite(fr"{key}\shell\print\command", "", f'"{exe_path}" --print "%1"', winreg.REG_SZ))
    return writes


def _encoded_value(value: object) -> object:
    if isinstance(value, bytes):
        return {"bytes": base64.b64encode(value).decode("ascii")}
    return value


def _decoded_value(value: object) -> object:
    if isinstance(value, dict) and set(value) == {"bytes"}:
        return base64.b64decode(value["bytes"], validate=True)
    return value


def _snapshot_changes(writes: list[_RegistryWrite]) -> dict[str, object]:
    changes: list[dict[str, object]] = []
    created_keys: set[str] = set()
    for write in writes:
        previous = _read_value(winreg.HKEY_CURRENT_USER, write.key, write.name)
        if previous == (write.value, write.value_type):
            continue
        changes.append({"key": write.key, "name": write.name,
                        "previous": None if previous is None else [_encoded_value(previous[0]), previous[1]],
                        "written": [_encoded_value(write.value), write.value_type]})
        key = write.key
        while _owned_key(key):
            if not _key_exists(key):
                created_keys.add(key)
            key = key.rsplit("\\", 1)[0]
    return {"format": _ROLLBACK_FORMAT, "version": 1,
            "created_at": datetime.now().astimezone().isoformat(), "changes": changes,
            "created_keys": sorted(created_keys, key=lambda value: (-value.count("\\"), value))}


def _save_snapshot(local_root: Path, snapshot: dict[str, object]) -> Path:
    directory = local_root / "ChaeumLAB" / "file-association"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"rollback_{datetime.now().astimezone():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}.json"
    temporary = path.with_suffix(".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(snapshot, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _write_change(change: dict[str, object]) -> None:
    value, value_type = change["written"]
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, change["key"], 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, change["name"], 0, value_type, _decoded_value(value))


def _owned_key(key: str) -> bool:
    return any(key == root or key.startswith(root + "\\") for root in _OWNED_ROOTS)


def _validate_snapshot(snapshot: object) -> None:
    if not isinstance(snapshot, dict) or snapshot.get("format") != _ROLLBACK_FORMAT or snapshot.get("version") != 1:
        raise ValueError("지원하지 않는 파일 연결 복원 기록입니다.")
    changes = snapshot.get("changes")
    keys = snapshot.get("created_keys")
    if not isinstance(changes, list) or len(changes) > 128 or not isinstance(keys, list) or len(keys) > 128:
        raise ValueError("파일 연결 복원 목록이 올바르지 않습니다.")
    if any(not isinstance(key, str) or not _owned_key(key) for key in keys):
        raise ValueError("복원할 레지스트리 경로가 채움랩 파일 연결 범위를 벗어납니다.")
    for change in changes:
        if not isinstance(change, dict) or not isinstance(change.get("key"), str) or not _owned_key(change["key"]) or not isinstance(change.get("name"), str):
            raise ValueError("복원할 레지스트리 값이 올바르지 않습니다.")
        for field in ("previous", "written"):
            value = change.get(field)
            if field == "previous" and value is None:
                continue
            if not isinstance(value, list) or len(value) != 2 or not isinstance(value[1], int):
                raise ValueError("복원할 레지스트리 값 형식이 올바르지 않습니다.")
            decoded = _decoded_value(value[0])
            if not isinstance(decoded, (str, bytes, int, list)):
                raise ValueError("복원할 레지스트리 데이터가 올바르지 않습니다.")


def _restore_snapshot(snapshot: dict[str, object]) -> None:
    _validate_snapshot(snapshot)
    for change in reversed(snapshot["changes"]):
        current = _read_value(winreg.HKEY_CURRENT_USER, change["key"], change["name"])
        written = change["written"]
        if current != (_decoded_value(written[0]), written[1]):
            continue  # Preserve a user's later choice instead of taking ownership back.
        previous = change["previous"]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, change["key"], 0, winreg.KEY_SET_VALUE) as key:
            if previous is None:
                winreg.DeleteValue(key, change["name"])
            else:
                winreg.SetValueEx(key, change["name"], 0, previous[1], _decoded_value(previous[0]))
    for subkey in snapshot["created_keys"]:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_READ) as key:
                children, values, _ = winreg.QueryInfoKey(key)
            if not children and not values:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, subkey)
        except FileNotFoundError:
            continue


def _notify_shell_association_changed() -> None:
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
