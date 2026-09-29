from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.metadata
import json
import platform
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any


BRAND_NAME = "채움랩"
KST = timezone(timedelta(hours=9), name="KST")
MANIFEST_SCHEMA_VERSION = 2
SPEC_NAMES = (
    "customer_preflight.spec",
    "label_designer.spec",
    "label_job_runner.spec",
    "label_manager.spec",
    "print_labels.spec",
    "printer_settings.spec",
)


@dataclass(frozen=True)
class ManifestFile:
    path: str
    required: bool = True


# This remains the minimum customer-package contract. The manifest inventory is
# broader: every deployable file found below base_dir is recorded recursively.
MANIFEST_FILES = (
    ManifestFile("README_먼저읽기.txt"),
    ManifestFile("버전정보.txt"),
    ManifestFile("사용안내.txt"),
    ManifestFile("설치_및_사용_메뉴얼.txt"),
    ManifestFile("라벨출력패키지_고객용_매뉴얼.docx"),
    ManifestFile("라벨디자이너.exe"),
    ManifestFile("라벨출력관리.exe"),
    ManifestFile("프린터설정.exe"),
    ManifestFile("고객환경점검.exe"),
    ManifestFile("라벨작업실행기.exe"),
    ManifestFile("라벨출력엔진.exe"),
    ManifestFile("config.ini"),
    ManifestFile("config.example.ini"),
    ManifestFile("barcode_db.xlsx"),
    ManifestFile("print_queue.xlsx"),
    ManifestFile("labels.xlsm"),
    ManifestFile("templates/default_label.json"),
    ManifestFile("assets/brand/chaeumlab_logo_header.png"),
    ManifestFile("assets/brand/chaeumlab_logo_compact.png"),
    ManifestFile("assets/brand/chaeumlab_app_icon.ico"),
    ManifestFile("assets/brand/chaeumlab_app_icon_white.ico"),
    ManifestFile("assets/brand/chaeumlab_label_file_icon_white.ico"),
    ManifestFile("assets/fonts/MONEYGRAPHY-ROUNDED.TTF"),
    ManifestFile("assets/fonts/README.txt"),
    ManifestFile("register_label_filetype.ps1"),
    ManifestFile("register_label_filetype.cmd"),
    ManifestFile("시작하기.cmd"),
    ManifestFile("처음실행_점검.cmd"),
    ManifestFile("고객데이터_백업.cmd"),
    ManifestFile("고객데이터_복원.cmd"),
    ManifestFile("00_install_trusted_location.cmd"),
    ManifestFile("run_label_job.cmd"),
    ManifestFile("00_고객PC_실행전점검.cmd"),
    ManifestFile("01_output_check.cmd"),
    ManifestFile("02_print_labels.cmd"),
    ManifestFile("03_open_output_folder.cmd"),
    ManifestFile("04_open_last_log.cmd"),
    ManifestFile("scripts/install_tesseract_ocr.ps1"),
    ManifestFile("scripts/install_chaeumlab_font.ps1"),
    ManifestFile("tools/ocr/README.txt"),
    ManifestFile("tools/ocr/tesseract.exe", required=False),
    ManifestFile("tools/ocr/tessdata/kor.traineddata", required=False),
    ManifestFile("tools/ocr/tessdata/eng.traineddata", required=False),
)

MANIFEST_CONTROL_FILES = frozenset({"release_manifest.json"})
RUNTIME_DIRECTORY_NAMES = frozenset({"_backup", "out", "chaeumlab", "tmp", "__pycache__", ".pytest_cache"})
RUNTIME_FILE_PATTERNS = (
    "*.log",
    "*.tmp",
    "*.bak",
    "desktop.ini",
    "thumbs.db",
    "print_log.xlsx",
    "selected_print_queue.xlsx",
    "customer_preflight_report.txt",
    "customer_support_package.zip",
)
# These files are customer data or settings. They must exist in a release, but
# the customer is expected to edit them after installation, so their hashes are
# recorded for inventory only and are not treated as post-install tampering.
MUTABLE_CUSTOMER_FILES = frozenset(
    {
        "config.ini",
        "barcode_db.xlsx",
        "print_queue.xlsx",
        "labels.xlsm",
        "templates/default_label.json",
    }
)
FORBIDDEN_RELATIVE_PATHS = frozenset(
    {
        "customer_preflight.exe",
        "label_designer.exe",
        "label_job_runner.exe",
        "label_manager.exe",
        "print_labels.exe",
        "printer_settings.exe",
        "db/123.xlsm",
        "db/test.xlsx",
        "tools/tools",
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


def build_release_manifest(
    base_dir: str | Path,
    *,
    package_name: str | None = None,
    package_version: str | None = None,
    generated_at: str | None = None,
    source_root: str | Path | None = None,
    build_id: str | None = None,
    test_result: Any = None,
    python_version: str | None = None,
    pyinstaller_version: str | None = None,
) -> dict[str, object]:
    base = Path(base_dir).resolve()
    timestamp = generated_at or datetime.now(KST).isoformat(timespec="seconds")
    resolved_name = package_name or base.name
    resolved_version = package_version or "unversioned"
    required_files = sorted(item.path.replace("\\", "/") for item in MANIFEST_FILES if item.required)
    inventory = _payload_inventory(base)
    inventory_paths = {str(entry["path"]) for entry in inventory}
    missing_required = [path for path in required_files if path not in inventory_paths]
    forbidden = find_forbidden_additions(base)
    build = _build_metadata(
        source_root=source_root,
        generated_at=timestamp,
        build_id=build_id,
        test_result=test_result,
        python_version=python_version,
        pyinstaller_version=pyinstaller_version,
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "brand": BRAND_NAME,
        "package": {"name": resolved_name, "version": resolved_version},
        "package_name": resolved_name,
        "version": resolved_version,
        "generated_at": timestamp,
        "base_folder": base.name,
        "build": build,
        "required_files": required_files,
        "excluded": {
            "manifest_control_files": sorted(MANIFEST_CONTROL_FILES),
            "runtime_generated": True,
        },
        "summary": {
            "listed_files": len(inventory),
            "present_files": len(inventory),
            "missing_required_files": len(missing_required),
            "forbidden_files": len(forbidden),
            "total_present_bytes": sum(int(entry["size"]) for entry in inventory),
        },
        "missing_required_files": missing_required,
        "forbidden_files": forbidden,
        "files": inventory,
    }


def write_release_manifest(
    base_dir: str | Path,
    *,
    package_name: str | None = None,
    package_version: str | None = None,
    source_root: str | Path | None = None,
    build_id: str | None = None,
    test_result: Any = None,
    python_version: str | None = None,
    pyinstaller_version: str | None = None,
) -> tuple[Path, Path]:
    base = Path(base_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    resolved_package_name = package_name or base.name
    resolved_package_version = package_version or "unversioned"
    generated_at = datetime.now(KST).isoformat(timespec="seconds")
    (base / "버전정보.txt").write_text(
        format_version_info(
            package_name=resolved_package_name,
            package_version=resolved_package_version,
            generated_at=generated_at,
        ),
        encoding="utf-8-sig",
    )
    json_path = base / "release_manifest.json"
    text_path = base / "배포_파일목록.txt"
    if text_path.exists():
        text_path.unlink()
    preliminary_manifest = build_release_manifest(
        base,
        package_name=resolved_package_name,
        package_version=resolved_package_version,
        generated_at=generated_at,
        source_root=source_root,
        build_id=build_id,
        test_result=test_result,
        python_version=python_version,
        pyinstaller_version=pyinstaller_version,
    )
    text_path.write_text(format_manifest_text(preliminary_manifest), encoding="utf-8-sig")
    manifest = build_release_manifest(
        base,
        package_name=resolved_package_name,
        package_version=resolved_package_version,
        generated_at=generated_at,
        source_root=source_root,
        build_id=build_id,
        test_result=test_result,
        python_version=python_version,
        pyinstaller_version=pyinstaller_version,
    )
    json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return json_path, text_path


def format_version_info(*, package_name: str, generated_at: str, package_version: str = "unversioned") -> str:
    lines = [
        f"{BRAND_NAME} 라벨 출력 패키지 버전 정보",
        "",
        f"패키지명: {package_name}",
        f"버전: {package_version}",
        f"배포 생성시간: {generated_at}",
        "브랜드: 채움랩",
        "용도: 바코드 프린터 + 스캐너 + 라벨 발행 프로그램 + 설치지원 패키지",
        "",
        "고객 첫 실행 순서",
        "1. 시작하기.cmd 실행",
        "2. 1번 처음 실행 점검 선택",
        "3. 프린터설정.exe에서 장비/라벨 크기 확인",
        "4. 라벨출력관리.exe에서 1장 테스트 출력",
        "5. PC 교체 시 고객데이터_백업.cmd로 만든 ZIP을 고객데이터_복원.cmd에서 선택",
        "",
        "지원 문의 시 전달할 정보",
        "- 이 버전정보.txt",
        "- out\\customer_support_package.zip",
        "- 프린터 모델명, 연결 방식, 라벨지 크기",
        "",
        "주의",
        "- 실제 출력 성공은 프린터 상태, 용지, 리본, 센서 설정까지 확인해야 합니다.",
        "- 자세한 파일 해시와 누락 여부는 release_manifest.json 및 배포_파일목록.txt에서 확인합니다.",
    ]
    return "\n".join(lines) + "\n"


def format_manifest_text(manifest: dict[str, object]) -> str:
    summary = manifest["summary"]  # type: ignore[index]
    files = manifest["files"]  # type: ignore[index]
    build = manifest["build"]  # type: ignore[index]
    lines = [
        f"{manifest['brand']} 라벨 출력 패키지 배포 파일 목록",
        f"패키지명: {manifest['package_name']}",
        f"버전: {manifest['version']}",
        f"빌드 ID: {build['id']}",  # type: ignore[index]
        f"생성시간: {manifest['generated_at']}",
        "",
        "요약",
        f"- 배포 파일 수: {summary['listed_files']}",  # type: ignore[index]
        f"- 누락 필수 파일 수: {summary['missing_required_files']}",  # type: ignore[index]
        f"- 추가 금지 파일 수: {summary['forbidden_files']}",  # type: ignore[index]
        "",
        "파일 목록",
    ]
    for entry in files:  # type: ignore[assignment]
        mutable_marker = " / 고객 수정 허용" if entry.get("mutable") else ""
        lines.append(f"- [OK] {entry['path']} / {entry['size']} bytes / sha256 {entry['sha256']}{mutable_marker}")
    lines.extend(
        [
            "",
            "사용 전 확인",
            "1. 시작하기.cmd를 열고 1번 처음 실행 점검을 선택하세요.",
            "2. 처음실행_점검.cmd는 실행 전 점검, 출력 파일 생성 테스트, 고객 데이터 백업을 순서대로 실행합니다.",
            "3. 프린터설정.exe에서 실제 장비와 라벨 크기를 확인하세요.",
            "4. 실제 출력은 02_print_labels.cmd 또는 라벨출력관리.exe의 인쇄 메뉴를 사용하세요.",
            "5. PC 교체나 재설치 후에는 고객데이터_복원.cmd로 백업 ZIP을 복원하세요.",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_release_manifest(base_dir: str | Path) -> tuple[bool, str]:
    base = Path(base_dir).resolve()
    manifest_path = base / "release_manifest.json"
    if not manifest_path.exists():
        return False, "release_manifest.json 파일이 없습니다."
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return False, f"release_manifest.json 읽기 실패: {exc}"
    files = manifest.get("files")
    if not isinstance(files, list):
        return False, "release_manifest.json files 배열이 없습니다."

    entries: dict[str, dict[str, object]] = {}
    for raw_entry in files:
        if not isinstance(raw_entry, dict):
            return False, "release_manifest.json 파일 항목 형식이 잘못되었습니다."
        relative = _validated_manifest_path(raw_entry.get("path"))
        if relative is None:
            return False, "release_manifest.json 파일 경로가 잘못되었습니다."
        if relative in entries:
            return False, f"release_manifest.json 중복 파일 경로: {relative}"
        expected_hash = raw_entry.get("sha256")
        expected_size = raw_entry.get("size", raw_entry.get("size_bytes"))
        if not isinstance(expected_size, int) or expected_size < 0:
            return False, f"release_manifest.json 파일 크기가 잘못되었습니다: {relative}"
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            return False, f"release_manifest.json sha256이 잘못되었습니다: {relative}"
        try:
            int(expected_hash, 16)
        except ValueError:
            return False, f"release_manifest.json sha256이 잘못되었습니다: {relative}"
        entries[relative] = raw_entry

    required = manifest.get("required_files", [item.path for item in MANIFEST_FILES if item.required])
    if not isinstance(required, list) or not all(isinstance(path, str) for path in required):
        return False, "release_manifest.json required_files 배열이 잘못되었습니다."
    required_paths: list[str] = []
    for value in required:
        relative = _validated_manifest_path(value)
        if relative is None:
            return False, "release_manifest.json 필수 파일 경로가 잘못되었습니다."
        required_paths.append(relative)

    forbidden = find_forbidden_additions(base)
    if forbidden:
        return False, "추가 금지 파일: " + ", ".join(forbidden[:5])

    missing = sorted(path for path in set(entries).union(required_paths) if not (base / path).is_file())
    if missing:
        return False, "누락 필수 파일: " + ", ".join(missing[:5])

    changed: list[str] = []
    for relative, entry in entries.items():
        path = base / relative
        expected_size = int(entry.get("size", entry.get("size_bytes", -1)))
        expected_hash = str(entry["sha256"])
        if relative in MUTABLE_CUSTOMER_FILES:
            continue
        if path.stat().st_size != expected_size or _sha256(path) != expected_hash:
            changed.append(relative)
    if changed:
        return False, "배포 후 변경된 파일: " + ", ".join(changed[:5])

    actual_paths = {str(entry["path"]) for entry in _payload_inventory(base)}
    unexpected = sorted(actual_paths.difference(entries))
    if unexpected:
        return False, "manifest에 없는 추가 파일: " + ", ".join(unexpected[:5])
    return True, "release_manifest.json 기준 필수 파일 확인"


def find_forbidden_additions(base_dir: str | Path) -> list[str]:
    base = Path(base_dir).resolve()
    findings: set[str] = set()
    if not base.exists():
        return []
    for path in base.rglob("*"):
        relative = path.relative_to(base).as_posix()
        if _is_runtime_artifact(relative):
            continue
        lowered = relative.lower()
        if _matches_forbidden_relative(lowered):
            findings.add(relative)
            continue
        if path.is_file():
            name = path.name.lower()
            if name in FORBIDDEN_FILE_NAMES or name.endswith((".html", ".jar")):
                findings.add(relative)
            elif fnmatch.fnmatchcase(name, "labels.before-*.xlsm"):
                findings.add(relative)
    return sorted(findings)


def _payload_inventory(base: Path) -> list[dict[str, object]]:
    if not base.is_dir():
        return []
    required_paths = {item.path.replace("\\", "/") for item in MANIFEST_FILES if item.required}
    entries: list[dict[str, object]] = []
    for path in sorted((item for item in base.rglob("*") if item.is_file()), key=lambda item: item.relative_to(base).as_posix().lower()):
        relative = path.relative_to(base).as_posix()
        if _is_manifest_control_file(relative) or _is_runtime_artifact(relative):
            continue
        size = path.stat().st_size
        entries.append(
            {
                "path": relative,
                "size": size,
                "size_bytes": size,
                "sha256": _sha256(path),
                "required": relative in required_paths,
                "mutable": relative in MUTABLE_CUSTOMER_FILES,
            }
        )
    return entries


def _build_metadata(
    *,
    source_root: str | Path | None,
    generated_at: str,
    build_id: str | None,
    test_result: Any,
    python_version: str | None,
    pyinstaller_version: str | None,
) -> dict[str, object]:
    specs: list[dict[str, object]] = []
    if source_root is not None:
        root = Path(source_root).resolve()
        for name in SPEC_NAMES:
            path = root / name
            specs.append(
                {
                    "path": name,
                    "size": path.stat().st_size if path.is_file() else 0,
                    "sha256": _sha256(path) if path.is_file() else "",
                    "exists": path.is_file(),
                }
            )
    return {
        "id": build_id or generated_at,
        "python_version": python_version or platform.python_version(),
        "pyinstaller_version": pyinstaller_version or _installed_version("pyinstaller"),
        "specs": specs,
        "test_result": test_result,
    }


def _installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _validated_manifest_path(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or normalized.startswith("/"):
        return None
    return pure.as_posix()


def _is_manifest_control_file(relative: str) -> bool:
    return relative.lower() in {path.lower() for path in MANIFEST_CONTROL_FILES}


def _is_runtime_artifact(relative: str) -> bool:
    lowered = relative.replace("\\", "/").lower().strip("/")
    parts = lowered.split("/") if lowered else []
    if any(part in RUNTIME_DIRECTORY_NAMES or part.startswith("_mei") for part in parts[:-1]):
        return True
    name = parts[-1] if parts else lowered
    if name.startswith("_mei"):
        return True
    return any(fnmatch.fnmatchcase(name, pattern.lower()) for pattern in RUNTIME_FILE_PATTERNS)


def _matches_forbidden_relative(lowered: str) -> bool:
    for forbidden in FORBIDDEN_RELATIVE_PATHS:
        if lowered == forbidden or lowered.startswith(f"{forbidden}/"):
            return True
    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create and validate a customer release manifest.")
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--package-name")
    parser.add_argument("--package-version")
    parser.add_argument("--build-id")
    parser.add_argument("--test-result")
    args = parser.parse_args(argv)
    json_path, text_path = write_release_manifest(
        args.base_dir,
        source_root=args.source_root,
        package_name=args.package_name,
        package_version=args.package_version,
        build_id=args.build_id,
        test_result=args.test_result,
    )
    ok, message = validate_release_manifest(args.base_dir)
    print(json_path)
    print(text_path)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_main())
