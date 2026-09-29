from __future__ import annotations

import fnmatch
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .release_manifest import KST, validate_release_manifest, write_release_manifest


DEFAULT_PACKAGE_PREFIX = "채움랩_라벨출력_고객용"
EXCLUDED_DIR_NAMES = frozenset({"_backup", "tmp", "out", "__pycache__", ".pytest_cache", "ChaeumLAB"})
EXCLUDED_FILE_PATTERNS = frozenset(
    {
        "*.log",
        "*.tmp",
        "*.bak",
        "desktop.ini",
        "Thumbs.db",
        "labels.before*.xlsm",
        "print_log.xlsx",
        "selected_print_queue.xlsx",
        "customer_preflight_report.txt",
        "customer_support_package.zip",
    }
)
FORBIDDEN_RELATIVE_PATHS = frozenset(
    {
        "label_designer.exe",
        "label_job_runner.exe",
        "label_manager.exe",
        "print_labels.exe",
        "printer_settings.exe",
        "customer_preflight.exe",
        "db/123.xlsm",
        "db/test.xlsx",
        "tools/tools",
        "ChaeumLAB",
        "tools/ocr/tessdata/osd.traineddata",
    }
)
FORBIDDEN_FILE_NAMES = frozenset(
    {
        "ambiguous_words.exe",
        "classifier_tester.exe",
        "cntraining.exe",
        "combine_lang_model.exe",
        "combine_tessdata.exe",
        "dawg2wordlist.exe",
        "lstmeval.exe",
        "lstmtraining.exe",
        "merge_unicharsets.exe",
        "mftraining.exe",
        "set_unicharset_properties.exe",
        "shapeclustering.exe",
        "tesseract-uninstall.exe",
        "text2image.exe",
        "unicharset_extractor.exe",
        "wordlist2dawg.exe",
    }
)


class CustomerDeploymentError(RuntimeError):
    pass


@dataclass(frozen=True)
class CopyStats:
    files: int = 0
    directories: int = 0
    bytes: int = 0


@dataclass(frozen=True)
class DeploymentResult:
    target_dir: Path
    files: int
    directories: int
    bytes: int
    manifest_message: str


def next_deploy_dir(
    deploy_root: str | Path,
    *,
    package_prefix: str = DEFAULT_PACKAGE_PREFIX,
    date_stamp: str | None = None,
) -> Path:
    root = Path(deploy_root).resolve()
    stamp = date_stamp or datetime.now(KST).strftime("%Y%m%d")
    for index in range(1, 1000):
        candidate = root / f"{package_prefix}_{stamp}_{index:02d}"
        if not candidate.exists():
            return candidate
    raise CustomerDeploymentError(f"배포 폴더 번호를 만들 수 없습니다: {root}")


def should_exclude(relative_path: str | Path, *, is_dir: bool) -> bool:
    normalized = _normalize_relative(relative_path)
    parts = normalized.split("/") if normalized else []
    if any(part in EXCLUDED_DIR_NAMES or part.startswith("_MEI") for part in parts):
        return True
    if _is_forbidden_relative(normalized):
        return True
    if is_dir:
        return False
    name = parts[-1] if parts else normalized
    lower_name = name.lower()
    if lower_name in FORBIDDEN_FILE_NAMES or lower_name.endswith(".html") or lower_name.endswith(".jar"):
        return True
    return any(fnmatch.fnmatchcase(lower_name, pattern.lower()) for pattern in EXCLUDED_FILE_PATTERNS)


def copy_customer_tree(source_dir: str | Path, target_dir: str | Path) -> CopyStats:
    source = Path(source_dir).resolve()
    target = Path(target_dir).resolve()
    if not source.is_dir():
        raise CustomerDeploymentError(f"고객용 실행폴더를 찾을 수 없습니다: {source}")
    if target.exists() and any(target.iterdir()):
        raise CustomerDeploymentError(f"비어 있지 않은 배포 폴더에는 복사하지 않습니다: {target}")
    target.mkdir(parents=True, exist_ok=True)

    file_count = 0
    dir_count = 0
    byte_count = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if should_exclude(relative, is_dir=path.is_dir()):
            continue
        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            dir_count += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        file_count += 1
        byte_count += destination.stat().st_size
    return CopyStats(files=file_count, directories=dir_count, bytes=byte_count)


def find_forbidden_deploy_items(base_dir: str | Path) -> list[str]:
    base = Path(base_dir).resolve()
    if not base.exists():
        return [str(base)]
    findings: list[str] = []
    for path in base.rglob("*"):
        relative = _normalize_relative(path.relative_to(base))
        name = path.name.lower()
        if path.is_dir():
            if should_exclude(relative, is_dir=True) or relative.lower() in FORBIDDEN_RELATIVE_PATHS:
                findings.append(relative)
            continue
        if should_exclude(relative, is_dir=False):
            findings.append(relative)
            continue
        if relative.lower() in FORBIDDEN_RELATIVE_PATHS:
            findings.append(relative)
            continue
        if name in FORBIDDEN_FILE_NAMES or name.endswith(".html") or name.endswith(".jar"):
            findings.append(relative)
    return findings


def assert_clean_deploy(base_dir: str | Path) -> None:
    findings = find_forbidden_deploy_items(base_dir)
    if findings:
        shown = ", ".join(findings[:10])
        raise CustomerDeploymentError(f"고객배포 제외 대상이 남아 있습니다: {shown}")


def create_customer_deployment(
    source_dir: str | Path,
    deploy_root: str | Path,
    *,
    package_prefix: str = DEFAULT_PACKAGE_PREFIX,
    date_stamp: str | None = None,
) -> DeploymentResult:
    source = Path(source_dir).resolve()
    root = Path(deploy_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = next_deploy_dir(root, package_prefix=package_prefix, date_stamp=date_stamp)
    _assert_child_path(root, target)

    try:
        stats = copy_customer_tree(source, target)
        write_release_manifest(
            target,
            package_name=target.name,
            package_version=_source_release_version(source),
        )
        ok, message = validate_release_manifest(target)
        if not ok:
            raise CustomerDeploymentError(message)
        assert_clean_deploy(target)
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        raise

    return DeploymentResult(
        target_dir=target,
        files=stats.files,
        directories=stats.directories,
        bytes=stats.bytes,
        manifest_message=message,
    )


def _assert_child_path(parent: Path, child: Path) -> None:
    parent_resolved = parent.resolve()
    child_resolved = child.resolve()
    try:
        child_resolved.relative_to(parent_resolved)
    except ValueError as exc:
        raise CustomerDeploymentError(f"배포 대상이 배포 루트 밖입니다: {child_resolved}") from exc


def _source_release_version(source: Path) -> str | None:
    manifest_path = source / "release_manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str):
        return None
    normalized = version.strip()
    return normalized if normalized and normalized != "unversioned" else None


def _is_forbidden_relative(relative: str) -> bool:
    lowered = relative.lower()
    for forbidden in FORBIDDEN_RELATIVE_PATHS:
        if lowered == forbidden or lowered.startswith(f"{forbidden}/"):
            return True
    return False


def _normalize_relative(path: str | Path) -> str:
    return Path(path).as_posix().strip("/")
