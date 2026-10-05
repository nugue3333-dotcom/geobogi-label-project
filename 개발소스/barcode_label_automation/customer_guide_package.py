"""Prepare a guide-only package copy without changing its EXE build evidence."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

from .customer_deployment import assert_clean_deploy, should_exclude
from .release_manifest import (
    KST,
    MANIFEST_FILES,
    MANIFEST_SCHEMA_VERSION,
    build_release_manifest,
    format_manifest_text,
    validate_release_manifest,
)

GUIDE_NAMES = ("한눈에_사용안내.pdf", "README_먼저읽기.txt", "사용안내.txt")
MANIFEST_NAME = "release_manifest.json"
FILE_LIST_NAME = "배포_파일목록.txt"


class GuidePackageError(RuntimeError):
    pass


@dataclass(frozen=True)
class GuidePackageResult:
    target_dir: Path
    applied: bool
    build_id: str
    manifest_message: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reject_links(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise GuidePackageError(f"링크 경로는 사용하지 않습니다: {part}")


def _checked_path(value: str | Path) -> Path:
    path = Path(os.path.abspath(value))
    _reject_links(path)
    return path.resolve()


def _relative_payload_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise GuidePackageError("manifest에는 일반 상대 파일 경로만 사용할 수 있습니다.")
    pure = PurePosixPath(value)
    if pure.is_absolute() or PureWindowsPath(value).drive or ".." in pure.parts or pure.as_posix() != value:
        raise GuidePackageError("manifest 파일 경로가 고객 폴더 밖을 가리킵니다.")
    return value


def _payload_path(root: Path, relative: str) -> Path:
    path = root / _relative_payload_path(relative)
    _reject_links(path)
    if not path.resolve().is_relative_to(root):
        raise GuidePackageError("manifest 파일 경로가 고객 폴더 밖을 가리킵니다.")
    return path


def _source_manifest(source: Path) -> tuple[dict, bytes]:
    manifest_path = source / MANIFEST_NAME
    _reject_links(manifest_path)
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GuidePackageError("유효한 고객 release_manifest.json이 필요합니다.") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise GuidePackageError("지원하는 고객 manifest schema가 아닙니다.")
    if not isinstance(manifest.get("build"), dict) or not isinstance(manifest["build"].get("id"), str):
        raise GuidePackageError("원본 EXE 빌드 정보를 확인할 수 없습니다.")
    for key in ("brand", "package_name", "version", "generated_at"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise GuidePackageError(f"원본 manifest 정보가 없습니다: {key}")
    if not isinstance(manifest.get("docs_updates", []), list):
        raise GuidePackageError("기존 안내 갱신 이력 형식이 잘못되었습니다.")
    entries = manifest.get("files")
    required = manifest.get("required_files")
    if not isinstance(entries, list) or not isinstance(required, list):
        raise GuidePackageError("원본 manifest의 파일 목록 형식이 잘못되었습니다.")
    names = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise GuidePackageError("원본 manifest의 파일 항목 형식이 잘못되었습니다.")
        relative = _relative_payload_path(entry.get("path"))
        if relative.casefold() in names:
            raise GuidePackageError("원본 manifest에 대소문자가 겹치는 파일 경로가 있습니다.")
        names.add(relative.casefold())
        _payload_path(source, relative)
    for relative in required:
        _payload_path(source, _relative_payload_path(relative))
    ok, message = validate_release_manifest(source)
    if not ok:
        raise GuidePackageError(f"원본 고객 패키지 검증 실패: {message}")
    recorded = {entry["path"] for entry in manifest["files"]}
    minimum = {item.path for item in MANIFEST_FILES if item.required}
    if not minimum.issubset(recorded):
        raise GuidePackageError("원본 manifest에 고객 패키지 필수 구성이 없습니다.")
    for relative in recorded:
        _payload_path(source, relative)
        if should_exclude(relative, is_dir=False):
            raise GuidePackageError(f"배포 목록에 고객 전달 제외 파일이 있습니다: {relative}")
    payload_paths = {entry["path"] for entry in build_release_manifest(source)["files"]}
    if recorded != payload_paths:
        raise GuidePackageError("원본 manifest의 고객 payload 목록이 일치하지 않습니다.")
    return manifest, raw


def _guide_bytes(guides: Path) -> dict[str, bytes]:
    result = {}
    for name in GUIDE_NAMES:
        path = guides / name
        _reject_links(path)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise GuidePackageError(f"원본 안내 파일이 없습니다: {name}") from exc
        if name.endswith(".pdf"):
            if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-1024:]:
                raise GuidePackageError("안내 PDF의 파일 형식을 확인하세요.")
        else:
            try:
                if not data.decode("utf-8-sig").strip():
                    raise GuidePackageError(f"안내 파일이 비어 있습니다: {name}")
            except UnicodeError as exc:
                raise GuidePackageError(f"안내 파일은 UTF-8이어야 합니다: {name}") from exc
        result[name] = data
    return result


def _inventory_manifest(stage: Path, original: dict) -> dict:
    # Read payload hashes only. Preserve the original build/runtime provenance.
    inventory = build_release_manifest(stage)
    updated = copy.deepcopy(original)
    updated["files"] = inventory["files"]
    updated["summary"] = inventory["summary"]
    updated["missing_required_files"] = inventory["missing_required_files"]
    updated["forbidden_files"] = inventory["forbidden_files"]
    return updated


def _copy_payload(source: Path, stage: Path, original: dict, raw_manifest: bytes) -> None:
    # Copy the validated payload allowlist, never walk runtime/backup folders.
    for entry in original["files"]:
        relative = entry["path"]
        source_file = _payload_path(source, relative)
        target = _payload_path(stage, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)
    (stage / MANIFEST_NAME).write_bytes(raw_manifest)


def _write_document_manifest(stage: Path, original: dict) -> None:
    (stage / FILE_LIST_NAME).unlink(missing_ok=True)
    preliminary = _inventory_manifest(stage, original)
    stamp = datetime.now(KST).isoformat(timespec="seconds")
    text = format_manifest_text(preliminary) + f"\n안내 갱신: {stamp} (EXE 재빌드 없음)\n"
    (stage / FILE_LIST_NAME).write_text(text, encoding="utf-8-sig")
    updated = _inventory_manifest(stage, original)
    history = updated.get("docs_updates", [])
    if not isinstance(history, list):
        raise GuidePackageError("기존 안내 갱신 이력 형식이 잘못되었습니다.")
    updated["docs_updates"] = history + [{
        "updated_at": stamp,
        "type": "guide-only-copy",
        "guides": {name: _sha256(stage / name) for name in GUIDE_NAMES},
        "exe_rebuilt": False,
    }]
    (stage / MANIFEST_NAME).write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _verify_output(source: Path, stage: Path, original: dict, raw_manifest: bytes) -> str:
    _, current_manifest = _source_manifest(source)
    if current_manifest != raw_manifest:
        raise GuidePackageError("복사 중 원본 manifest가 변경되었습니다. 다시 점검하세요.")
    ok, message = validate_release_manifest(stage)
    if not ok:
        raise GuidePackageError(f"안내 갱신본 검증 실패: {message}")
    assert_clean_deploy(stage)
    for entry in original["files"]:
        relative = entry["path"]
        if relative in (*GUIDE_NAMES, FILE_LIST_NAME):
            continue
        if _sha256(_payload_path(source, relative)) != _sha256(_payload_path(stage, relative)):
            raise GuidePackageError(f"원본과 복사본이 다릅니다: {relative}")
    return "안내 갱신본 manifest 통과 / EXE·고객 데이터·버전정보 보존"


def create_guide_package(
    customer_dir: str | Path,
    guides_dir: str | Path,
    output_dir: str | Path,
    *,
    apply: bool = False,
) -> GuidePackageResult:
    source, guides, target = map(_checked_path, (customer_dir, guides_dir, output_dir))
    if target.exists():
        raise GuidePackageError("출력 폴더가 이미 있습니다. 새 폴더를 지정하세요.")
    for origin in (source, guides):
        if target.is_relative_to(origin) or origin.is_relative_to(target):
            raise GuidePackageError("출력 폴더는 원본 폴더와 겹치면 안 됩니다.")
    if (guides / ".build_release_exes.lock").exists():
        raise GuidePackageError("EXE 릴리스 빌드가 진행 중입니다. 완료 후 다시 실행하세요.")
    original, raw_manifest = _source_manifest(source)
    data = _guide_bytes(guides)
    result = GuidePackageResult(target, apply, original["build"]["id"], "원본 검증 통과 / 안내 3개 복사 준비")
    if not apply:
        return result
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent / f".{target.name}.guide-update.lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise GuidePackageError("같은 출력 폴더의 안내 복사 작업이 진행 중입니다.") from exc
    os.close(descriptor)
    stage = None
    try:
        if target.exists():
            raise GuidePackageError("출력 폴더가 이미 있습니다. 새 폴더를 지정하세요.")
        stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.guide-stage-", dir=target.parent))
        _copy_payload(source, stage, original, raw_manifest)
        for name, content in data.items():
            (stage / name).write_bytes(content)
        _write_document_manifest(stage, original)
        message = _verify_output(source, stage, original, raw_manifest)
        if target.exists():
            raise GuidePackageError("복사 중 출력 폴더가 생성되었습니다. 덮어쓰지 않습니다.")
        stage.rename(target)
        return GuidePackageResult(target, True, original["build"]["id"], message)
    finally:
        try:
            if stage is not None and stage.exists():
                shutil.rmtree(stage)
        finally:
            lock.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="기존 EXE 빌드 정보를 유지한 고객 안내 갱신본 준비")
    parser.add_argument("--customer-dir", type=Path, required=True)
    parser.add_argument("--guides-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="검증 후 신규 출력 폴더 생성")
    mode.add_argument("--dry-run", action="store_true", help="검증만 수행 (기본값)")
    args = parser.parse_args(argv)
    try:
        result = create_guide_package(args.customer_dir, args.guides_dir, args.output_dir, apply=args.apply)
    except (GuidePackageError, OSError, ValueError, RuntimeError) as exc:
        print(f"안내 갱신본 준비 실패: {exc}", file=sys.stderr)
        return 1
    print(f"모드: {'신규 폴더 생성' if result.applied else 'dry-run (쓰기 없음)'}")
    print(f"출력 폴더: {result.target_dir}")
    print(f"원본 EXE 빌드 ID: {result.build_id}")
    print(result.manifest_message)
    print("Windows 실행·프린터 출력·고객 배포 검증 결과는 포함하지 않습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
