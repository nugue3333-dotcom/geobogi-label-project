from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO


BACKUP_FILES = (
    "config.ini",
    "config.example.ini",
    "barcode_db.xlsx",
    "print_queue.xlsx",
    "labels.xlsm",
    "sample_direct_open.gblabel",
)
BACKUP_DIRS = ("templates", "db", "assets/images")
MANIFEST_FILE = "backup_manifest.json"
LEGACY_MANIFEST_FILE = "backup_manifest.txt"
BACKUP_FORMAT = "chaeumlab-customer-backup"
BACKUP_VERSION = 1

MAX_FILE_SIZE = 512 * 1024 * 1024
MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024
MAX_MANIFEST_SIZE = 2 * 1024 * 1024
COPY_CHUNK_SIZE = 1024 * 1024

_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CONIN$",
    "CONOUT$",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
_WINDOWS_INVALID_CHARS = frozenset('<>"|?*')


class CustomerBackupError(RuntimeError):
    """A customer-safe backup or restore failure."""


class RestoreRollbackError(CustomerBackupError):
    def __init__(self, message: str, recovery_path: Path) -> None:
        super().__init__(message)
        self.recovery_path = recovery_path


@dataclass(frozen=True)
class RestoreResult:
    restored_files: int
    pre_restore_backup: Path | None = None


@dataclass(frozen=True)
class _ManifestEntry:
    path: str
    size: int
    sha256: str

    def as_dict(self) -> dict[str, str | int]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}


def create_customer_backup(base_dir: Path) -> Path:
    return _create_customer_backup(Path(base_dir), allow_empty=False)


def restore_customer_backup(base_dir: Path, backup_path: Path) -> RestoreResult:
    base_dir = Path(base_dir).resolve()
    backup_path = Path(backup_path).expanduser().resolve()
    if not backup_path.is_file():
        raise CustomerBackupError(f"복원할 백업 ZIP 파일을 찾을 수 없습니다.\n{backup_path}")

    base_dir.mkdir(parents=True, exist_ok=True)
    output_dir = base_dir / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=".customer_restore_", dir=output_dir))
    payload_dir = staging_root / "payload"
    rollback_dir = staging_root / "rollback"
    preserve_staging = False

    try:
        entries = _validate_backup_archive(backup_path, extract_dir=payload_dir)
        managed_entries = [entry for entry in entries if _is_managed_file(entry.path)]
        if not managed_entries:
            raise CustomerBackupError("복원할 고객 데이터 파일이 없습니다.")

        # A restore never mutates live data unless a durable, verified backup exists.
        pre_restore_backup = _create_customer_backup(base_dir, allow_empty=True)
        try:
            restored_files = _apply_exact_snapshot(base_dir, payload_dir, rollback_dir)
        except RestoreRollbackError:
            preserve_staging = True
            raise
        return RestoreResult(restored_files=restored_files, pre_restore_backup=pre_restore_backup)
    finally:
        if not preserve_staging:
            shutil.rmtree(staging_root, ignore_errors=True)


def _create_customer_backup(base_dir: Path, *, allow_empty: bool) -> Path:
    base_dir = Path(base_dir).resolve()
    if not base_dir.exists():
        raise CustomerBackupError(f"백업할 데이터 폴더가 없습니다.\n{base_dir}")
    if not base_dir.is_dir():
        raise CustomerBackupError(f"백업할 데이터 경로가 폴더가 아닙니다.\n{base_dir}")

    try:
        sources = _collect_backup_sources(base_dir)
    except CustomerBackupError:
        raise
    except OSError as exc:
        raise CustomerBackupError(f"백업 대상을 확인하지 못했습니다: {exc}") from exc
    if not sources and not allow_empty:
        raise CustomerBackupError("백업할 설정, DB, 템플릿 파일을 찾지 못했습니다.")

    output_dir = base_dir / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = output_dir / f"chaeumlab_customer_backup_{timestamp}.zip"
    partial_path = backup_path.with_suffix(backup_path.suffix + ".partial")

    try:
        entries: list[_ManifestEntry] = []
        with zipfile.ZipFile(partial_path, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for source_path, archive_name in sources:
                entries.append(_write_source_to_archive(archive, source_path, archive_name))

            legacy_bytes = _format_legacy_manifest(base_dir, entries).encode("utf-8")
            archive.writestr(LEGACY_MANIFEST_FILE, legacy_bytes)
            entries.append(_entry_for_bytes(LEGACY_MANIFEST_FILE, legacy_bytes))

            manifest = {
                "format": BACKUP_FORMAT,
                "version": BACKUP_VERSION,
                "created_at": datetime.now().astimezone().isoformat(),
                "files": [entry.as_dict() for entry in sorted(entries, key=lambda item: item.path)],
            }
            manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            archive.writestr(MANIFEST_FILE, manifest_bytes)

        _flush_file(partial_path)
        _validate_backup_archive(partial_path)
        os.replace(partial_path, backup_path)
        return backup_path
    except CustomerBackupError:
        partial_path.unlink(missing_ok=True)
        raise
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        partial_path.unlink(missing_ok=True)
        raise CustomerBackupError(f"고객 데이터 백업을 만들지 못했습니다: {exc}") from exc


def _collect_backup_sources(base_dir: Path) -> list[tuple[Path, str]]:
    sources: list[tuple[Path, str]] = []
    for file_name in BACKUP_FILES:
        path = base_dir / file_name
        if path.exists() or _path_is_link_like(path):
            _validate_source_file(base_dir, path, file_name)
            sources.append((path, file_name))

    for dir_name in BACKUP_DIRS:
        root = base_dir / Path(*dir_name.split("/"))
        if not root.exists() and not _path_is_link_like(root):
            continue
        if _path_is_link_like(root) or not root.is_dir():
            raise CustomerBackupError(f"백업 관리 폴더가 안전한 일반 폴더가 아닙니다: {dir_name}")
        try:
            root.resolve().relative_to(base_dir)
        except ValueError as exc:
            raise CustomerBackupError(f"백업 관리 폴더가 데이터 폴더 밖을 가리킵니다: {dir_name}") from exc
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(base_dir).as_posix()
            if _path_is_link_like(path):
                raise CustomerBackupError(f"백업 대상에 링크 또는 junction이 포함되어 있습니다: {relative}")
            if path.is_file():
                _validate_source_file(base_dir, path, relative)
                sources.append((path, relative))
    return sources


def _validate_source_file(base_dir: Path, path: Path, archive_name: str) -> None:
    if _path_is_link_like(path) or not path.is_file():
        raise CustomerBackupError(f"백업 대상이 안전한 일반 파일이 아닙니다: {archive_name}")
    try:
        path.resolve().relative_to(base_dir)
    except ValueError as exc:
        raise CustomerBackupError(f"백업 대상이 데이터 폴더 밖을 가리킵니다: {archive_name}") from exc
    _validate_member_path(archive_name, is_directory=False)
    size = path.stat().st_size
    if size > MAX_FILE_SIZE:
        raise CustomerBackupError(f"백업 파일이 허용 크기를 초과합니다: {archive_name}")


def _write_source_to_archive(archive: zipfile.ZipFile, source_path: Path, archive_name: str) -> _ManifestEntry:
    digest = hashlib.sha256()
    size = 0
    with source_path.open("rb") as source, archive.open(archive_name, "w", force_zip64=True) as target:
        while chunk := source.read(COPY_CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                raise CustomerBackupError(f"백업 중 파일 크기가 허용 한도를 초과했습니다: {archive_name}")
            digest.update(chunk)
            target.write(chunk)
    return _ManifestEntry(path=archive_name, size=size, sha256=digest.hexdigest())


def _entry_for_bytes(path: str, content: bytes) -> _ManifestEntry:
    return _ManifestEntry(path=path, size=len(content), sha256=hashlib.sha256(content).hexdigest())


def _format_legacy_manifest(base_dir: Path, entries: list[_ManifestEntry]) -> str:
    lines = [
        "채움랩 고객 데이터 백업",
        f"생성시간: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"기준폴더: {base_dir.name}",
        "",
        "포함 파일",
    ]
    lines.extend(f"- {entry.path}" for entry in sorted(entries, key=lambda item: item.path))
    lines.extend(
        [
            "",
            "주의",
            "- 이 백업에는 설정, 상품 DB, 인쇄 데이터, 라벨 템플릿과 도안 이미지가 포함됩니다.",
            "- EXE 실행 파일, out 폴더, 실행 로그, 지원 ZIP은 포함하지 않습니다.",
        ]
    )
    return "\n".join(lines) + "\n"


def _flush_file(path: Path) -> None:
    with path.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def _validate_backup_archive(archive_path: Path, extract_dir: Path | None = None) -> list[_ManifestEntry]:
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            file_infos = _validate_zip_infos(infos)
            manifest_info = file_infos.get(MANIFEST_FILE)
            if manifest_info is None:
                raise CustomerBackupError(f"채움랩 고객 데이터 백업 ZIP이 아닙니다. {MANIFEST_FILE}이 없습니다.")
            if LEGACY_MANIFEST_FILE not in file_infos:
                raise CustomerBackupError(f"채움랩 고객 데이터 백업 ZIP이 아닙니다. {LEGACY_MANIFEST_FILE}가 없습니다.")

            manifest_bytes = _read_member_bytes(archive, manifest_info, MAX_MANIFEST_SIZE)
            entries = _parse_manifest(manifest_bytes)
            expected = {entry.path: entry for entry in entries}
            payload_infos = {name: info for name, info in file_infos.items() if name != MANIFEST_FILE}
            if set(expected) != set(payload_infos):
                missing = sorted(set(payload_infos) - set(expected))
                extra = sorted(set(expected) - set(payload_infos))
                details = []
                if missing:
                    details.append("manifest 누락: " + ", ".join(missing))
                if extra:
                    details.append("ZIP 누락: " + ", ".join(extra))
                raise CustomerBackupError("백업 manifest와 ZIP 파일 목록이 일치하지 않습니다. " + "; ".join(details))

            if extract_dir is not None:
                extract_dir.mkdir(parents=True, exist_ok=True)
            for name, info in payload_infos.items():
                entry = expected[name]
                if info.file_size != entry.size:
                    raise CustomerBackupError(f"백업 파일 크기가 manifest와 다릅니다: {name}")
                destination = None
                if extract_dir is not None and _is_managed_file(name):
                    destination = _safe_extract_destination(extract_dir, name)
                _read_and_verify_member(archive, info, entry, destination)
            return entries
    except CustomerBackupError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise CustomerBackupError(f"백업 ZIP 무결성 검증에 실패했습니다: {exc}") from exc


def _validate_zip_infos(infos: list[zipfile.ZipInfo]) -> dict[str, zipfile.ZipInfo]:
    if not infos:
        raise CustomerBackupError("백업 ZIP이 비어 있습니다.")
    canonical: dict[str, tuple[str, bool]] = {}
    files: dict[str, zipfile.ZipInfo] = {}
    total_size = 0

    for info in infos:
        is_directory = info.is_dir()
        name = _validate_member_path(info.filename, is_directory=is_directory)
        key = _windows_path_key(name)
        if key in canonical:
            previous = canonical[key][0]
            raise CustomerBackupError(f"백업 ZIP에 중복 경로가 있습니다: {previous}, {info.filename}")
        canonical[key] = (name, is_directory)

        if info.flag_bits & 0x1:
            raise CustomerBackupError(f"암호화된 ZIP 항목은 복원할 수 없습니다: {name}")
        unix_type = (info.external_attr >> 16) & 0o170000
        if unix_type == stat.S_IFLNK:
            raise CustomerBackupError(f"심볼릭 링크 ZIP 항목은 복원할 수 없습니다: {name}")
        if unix_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise CustomerBackupError(f"일반 파일이 아닌 ZIP 항목은 복원할 수 없습니다: {name}")
        if info.file_size < 0 or info.file_size > MAX_FILE_SIZE:
            raise CustomerBackupError(f"백업 ZIP 항목 크기가 허용 한도를 초과합니다: {name}")
        total_size += info.file_size
        if total_size > MAX_TOTAL_SIZE:
            raise CustomerBackupError("백업 ZIP 전체 크기가 허용 한도를 초과합니다.")

        if is_directory:
            if not _is_managed_directory(name):
                raise CustomerBackupError(f"백업 ZIP 안에 복원 대상이 아닌 폴더가 있습니다: {name}")
        else:
            if name not in {MANIFEST_FILE, LEGACY_MANIFEST_FILE} and not _is_managed_file(name):
                raise CustomerBackupError(f"백업 ZIP 안에 복원 대상이 아닌 파일이 있습니다: {name}")
            files[name] = info

    file_keys = {key for key, (_, is_directory) in canonical.items() if not is_directory}
    for key, (name, _) in canonical.items():
        parts = key.split("/")
        for index in range(1, len(parts)):
            if "/".join(parts[:index]) in file_keys:
                raise CustomerBackupError(f"백업 ZIP에 파일/폴더 충돌 경로가 있습니다: {name}")
    return files


def _validate_member_path(raw_name: str, *, is_directory: bool) -> str:
    if not isinstance(raw_name, str) or not raw_name or "\x00" in raw_name:
        raise CustomerBackupError("백업 ZIP 안에 비어 있거나 잘못된 경로가 있습니다.")
    if "\\" in raw_name or raw_name.startswith("/"):
        raise CustomerBackupError(f"백업 ZIP 안에 허용되지 않는 경로가 있습니다: {raw_name}")
    if is_directory:
        if not raw_name.endswith("/"):
            raise CustomerBackupError(f"백업 ZIP 폴더 경로 형식이 잘못되었습니다: {raw_name}")
        raw_name = raw_name[:-1]
    elif raw_name.endswith("/"):
        raise CustomerBackupError(f"백업 ZIP 파일 경로 형식이 잘못되었습니다: {raw_name}")
    if not raw_name or "//" in raw_name:
        raise CustomerBackupError(f"백업 ZIP 안에 허용되지 않는 경로가 있습니다: {raw_name}")

    parsed = PurePosixPath(raw_name)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise CustomerBackupError(f"백업 ZIP 안에 허용되지 않는 경로가 있습니다: {raw_name}")
    for part in parsed.parts:
        if part.endswith((" ", ".")) or ":" in part:
            raise CustomerBackupError(f"백업 ZIP 안에 Windows에서 위험한 경로가 있습니다: {raw_name}")
        if any(character in _WINDOWS_INVALID_CHARS or ord(character) < 32 for character in part):
            raise CustomerBackupError(f"백업 ZIP 안에 Windows에서 허용되지 않는 경로가 있습니다: {raw_name}")
        stem = part.rstrip(" .").split(".", 1)[0].rstrip(" ").upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise CustomerBackupError(f"백업 ZIP 안에 Windows 예약 이름이 있습니다: {raw_name}")
    return parsed.as_posix()


def _windows_path_key(path: str) -> str:
    return "/".join(unicodedata.normalize("NFC", part).casefold() for part in path.split("/"))


def _parse_manifest(content: bytes) -> list[_ManifestEntry]:
    try:
        manifest = json.loads(content.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CustomerBackupError(f"백업 manifest JSON을 읽을 수 없습니다: {exc}") from exc
    if not isinstance(manifest, dict):
        raise CustomerBackupError("백업 manifest JSON 형식이 잘못되었습니다.")
    if manifest.get("format") != BACKUP_FORMAT or manifest.get("version") != BACKUP_VERSION:
        raise CustomerBackupError("지원하지 않는 고객 데이터 백업 형식 또는 버전입니다.")
    raw_entries = manifest.get("files")
    if not isinstance(raw_entries, list):
        raise CustomerBackupError("백업 manifest에 files 목록이 없습니다.")

    entries: list[_ManifestEntry] = []
    keys: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {"path", "size", "sha256"}:
            raise CustomerBackupError("백업 manifest 파일 항목 형식이 잘못되었습니다.")
        path = raw_entry["path"]
        size = raw_entry["size"]
        sha256 = raw_entry["sha256"]
        if not isinstance(path, str):
            raise CustomerBackupError("백업 manifest 파일 경로 형식이 잘못되었습니다.")
        path = _validate_member_path(path, is_directory=False)
        key = _windows_path_key(path)
        if key in keys:
            raise CustomerBackupError(f"백업 manifest에 중복 경로가 있습니다: {path}")
        keys.add(key)
        if not isinstance(size, int) or isinstance(size, bool) or size < 0 or size > MAX_FILE_SIZE:
            raise CustomerBackupError(f"백업 manifest 파일 크기가 잘못되었습니다: {path}")
        if not isinstance(sha256, str) or len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
            raise CustomerBackupError(f"백업 manifest SHA-256 값이 잘못되었습니다: {path}")
        if path == MANIFEST_FILE or (path != LEGACY_MANIFEST_FILE and not _is_managed_file(path)):
            raise CustomerBackupError(f"백업 manifest에 복원 대상이 아닌 파일이 있습니다: {path}")
        entries.append(_ManifestEntry(path=path, size=size, sha256=sha256))
    return entries


def _read_member_bytes(archive: zipfile.ZipFile, info: zipfile.ZipInfo, maximum: int) -> bytes:
    if info.file_size > maximum:
        raise CustomerBackupError(f"백업 manifest가 허용 크기를 초과합니다: {info.filename}")
    with archive.open(info, "r") as source:
        content = source.read(maximum + 1)
    if len(content) != info.file_size or len(content) > maximum:
        raise CustomerBackupError(f"백업 ZIP 항목의 실제 크기가 올바르지 않습니다: {info.filename}")
    return content


def _read_and_verify_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    expected: _ManifestEntry,
    destination: Path | None,
) -> None:
    digest = hashlib.sha256()
    size = 0
    target: BinaryIO | None = None
    try:
        if destination is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            target = destination.open("xb")
        with archive.open(info, "r") as source:
            while chunk := source.read(COPY_CHUNK_SIZE):
                size += len(chunk)
                if size > expected.size or size > MAX_FILE_SIZE:
                    raise CustomerBackupError(f"백업 ZIP 항목의 실제 크기가 올바르지 않습니다: {expected.path}")
                digest.update(chunk)
                if target is not None:
                    target.write(chunk)
    finally:
        if target is not None:
            target.close()
    if size != expected.size:
        raise CustomerBackupError(f"백업 파일 크기가 manifest와 다릅니다: {expected.path}")
    if digest.hexdigest() != expected.sha256:
        raise CustomerBackupError(f"백업 파일 SHA-256 검증에 실패했습니다: {expected.path}")


def _safe_extract_destination(root: Path, member_name: str) -> Path:
    destination = (root / Path(*member_name.split("/"))).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as exc:
        raise CustomerBackupError(f"백업 ZIP 경로가 staging 폴더 밖을 가리킵니다: {member_name}") from exc
    return destination


def _apply_exact_snapshot(base_dir: Path, payload_dir: Path, rollback_dir: Path) -> int:
    managed_targets = [*BACKUP_FILES, *BACKUP_DIRS]
    moved_old: list[str] = []
    installed_new: list[str] = []
    rollback_dir.mkdir(parents=True, exist_ok=False)

    try:
        for relative in managed_targets:
            live = base_dir / Path(*relative.split("/"))
            staged = payload_dir / Path(*relative.split("/"))
            saved = rollback_dir / Path(*relative.split("/"))
            _validate_live_parent(base_dir, live.parent)
            if live.exists() or live.is_symlink():
                saved.parent.mkdir(parents=True, exist_ok=True)
                os.replace(live, saved)
                moved_old.append(relative)
            if staged.exists():
                live.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, live)
                installed_new.append(relative)
    except Exception as apply_error:
        rollback_errors: list[str] = []
        for relative in reversed(installed_new):
            live = base_dir / Path(*relative.split("/"))
            try:
                _remove_path(live)
            except OSError as exc:
                rollback_errors.append(f"새 데이터 제거 실패 {relative}: {exc}")
        for relative in reversed(moved_old):
            live = base_dir / Path(*relative.split("/"))
            saved = rollback_dir / Path(*relative.split("/"))
            try:
                if live.exists() or live.is_symlink():
                    _remove_path(live)
                live.parent.mkdir(parents=True, exist_ok=True)
                os.replace(saved, live)
            except OSError as exc:
                rollback_errors.append(f"기존 데이터 복구 실패 {relative}: {exc}")
        if rollback_errors:
            details = "\n".join(rollback_errors)
            raise RestoreRollbackError(
                f"복원 적용과 자동 rollback에 실패했습니다: {apply_error}\n{details}\n수동 복구 폴더: {rollback_dir}",
                rollback_dir,
            ) from apply_error
        raise CustomerBackupError(f"복원 적용에 실패하여 기존 데이터로 rollback했습니다: {apply_error}") from apply_error

    shutil.rmtree(rollback_dir)
    return sum(1 for path in _iter_managed_payload_files(payload_dir, base_dir) if path.is_file())


def _iter_managed_payload_files(payload_dir: Path, base_dir: Path):
    # Installed files now live under base_dir; payload_dir is mostly empty after directory moves.
    del payload_dir
    for file_name in BACKUP_FILES:
        path = base_dir / file_name
        if path.is_file():
            yield path
    for dir_name in BACKUP_DIRS:
        root = base_dir / Path(*dir_name.split("/"))
        if root.is_dir():
            yield from (path for path in root.rglob("*") if path.is_file())


def _validate_live_parent(base_dir: Path, parent: Path) -> None:
    if parent == base_dir:
        return
    current = parent
    while current != base_dir:
        if current.exists():
            if _path_is_link_like(current) or not current.is_dir():
                raise CustomerBackupError(f"복원 대상 상위 경로가 안전한 폴더가 아닙니다: {current}")
            try:
                current.resolve().relative_to(base_dir)
            except ValueError as exc:
                raise CustomerBackupError(f"복원 대상 상위 경로가 데이터 폴더 밖을 가리킵니다: {current}") from exc
        current = current.parent


def _remove_path(path: Path) -> None:
    if _path_is_link_like(path) or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _is_managed_file(path: str) -> bool:
    if path in BACKUP_FILES:
        return True
    return any(path.startswith(directory + "/") for directory in BACKUP_DIRS)


def _is_managed_directory(path: str) -> bool:
    allowed = set()
    for directory in BACKUP_DIRS:
        parts = directory.split("/")
        for index in range(1, len(parts) + 1):
            allowed.add("/".join(parts[:index]))
    return path in allowed or any(path.startswith(directory + "/") for directory in BACKUP_DIRS)


def _path_is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())
