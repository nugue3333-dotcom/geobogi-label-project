from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from barcode_label_automation import customer_guide_package as guides
from barcode_label_automation.release_manifest import (
    MANIFEST_FILES,
    SPEC_NAMES,
    validate_release_manifest,
    write_release_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def package_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    source, documents, output = (tmp_path / name for name in ("customer", "guides", "new-customer"))
    source.mkdir()
    documents.mkdir()
    for item in MANIFEST_FILES:
        if item.required:
            path = source / item.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"fixture:{item.path}".encode("utf-8"))
    specs = tmp_path / "original-build"
    specs.mkdir()
    for name in SPEC_NAMES:
        (specs / name).write_text(f"original-spec:{name}", encoding="utf-8")
    write_release_manifest(
        source,
        package_name="테스트 원본",
        package_version="2026.10.01",
        source_root=specs,
        build_id="original-exe-build",
        python_version="original-python-version",
        pyinstaller_version="original-pyinstaller-version",
        test_result="original build evidence, fixture only",
    )
    (documents / "한눈에_사용안내.pdf").write_bytes((PROJECT_ROOT / "한눈에_사용안내.pdf").read_bytes())
    for name in guides.GUIDE_NAMES[1:]:
        (documents / name).write_text(f"업데이트한 안내: {name}", encoding="utf-8")
    return source, documents, output


def snapshot(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_default_validation_does_not_write_anything(package_inputs: tuple[Path, Path, Path]) -> None:
    source, documents, output = package_inputs
    before = snapshot(source.parent)
    result = guides.create_guide_package(source, documents, output)
    assert not result.applied
    assert snapshot(source.parent) == before


def test_copy_preserves_build_evidence_and_all_other_payload_bytes(package_inputs: tuple[Path, Path, Path]) -> None:
    source, documents, output = package_inputs
    before = snapshot(source)
    old_manifest = json.loads(before[guides.MANIFEST_NAME])
    # These edits are valid customer-managed data and must survive the copy.
    (source / "config.ini").write_bytes(b"transport=tcp\n")
    (source / "barcode_db.xlsx").write_bytes(b"updated customer DB fixture 00123456")
    (source / "out").mkdir()
    (source / "out" / "private-runtime.log").write_bytes(b"excluded runtime fixture")
    (source / "_backup").mkdir()
    (source / "_backup" / "previous.zip").write_bytes(b"excluded backup fixture")
    current_source = snapshot(source)

    result = guides.create_guide_package(source, documents, output, apply=True)

    assert result.applied
    assert snapshot(source) == current_source
    assert validate_release_manifest(output)[0]
    new_manifest = json.loads((output / guides.MANIFEST_NAME).read_text())
    for key in ("build", "package", "package_name", "version", "generated_at", "base_folder"):
        assert new_manifest[key] == old_manifest[key]
    for relative, data in current_source.items():
        if relative in (*guides.GUIDE_NAMES, guides.FILE_LIST_NAME, guides.MANIFEST_NAME) or relative.startswith(("out/", "_backup/")):
            continue
        assert (output / relative).read_bytes() == data
    for name in guides.GUIDE_NAMES:
        assert (output / name).read_bytes() == (documents / name).read_bytes()
        entry = next(e for e in new_manifest["files"] if e["path"] == name)
        assert entry["sha256"] == hashlib.sha256((documents / name).read_bytes()).hexdigest()
    assert not (output / "out").exists()
    assert not (output / "_backup").exists()
    assert new_manifest["docs_updates"][-1]["exe_rebuilt"] is False
    assert "EXE 재빌드 없음" in (output / guides.FILE_LIST_NAME).read_text(encoding="utf-8-sig")
    assert not list(output.parent.glob(".*.guide-stage-*"))
    assert not list(output.parent.glob("*.guide-update.lock"))


@pytest.mark.parametrize("damage", ["missing-exe", "changed-exe", "forbidden-html", "unrecorded-file", "bad-schema", "empty-required-contract", "bad-history"])
def test_rejects_invalid_packages_without_publishing_or_changing_source(package_inputs: tuple[Path, Path, Path], damage: str) -> None:
    source, documents, output = package_inputs
    if damage == "missing-exe":
        (source / "라벨출력관리.exe").unlink()
    elif damage == "changed-exe":
        (source / "라벨출력관리.exe").write_bytes(b"unexpected replacement")
    elif damage == "forbidden-html":
        (source / "preview.html").write_text("forbidden", encoding="utf-8")
    elif damage == "unrecorded-file":
        (source / "unrecorded.pdf").write_bytes(b"unrecorded")
    else:
        path = source / guides.MANIFEST_NAME
        manifest = json.loads(path.read_text())
        if damage == "bad-schema":
            manifest["schema_version"] = 999
        elif damage == "empty-required-contract":
            manifest["files"] = []
            manifest["required_files"] = []
            for candidate in list(source.iterdir()):
                if candidate.is_file() and candidate != path:
                    candidate.unlink()
            import shutil
            for candidate in list(source.iterdir()):
                if candidate.is_dir():
                    shutil.rmtree(candidate)
        elif damage == "bad-history":
            manifest["docs_updates"] = "invalid"
        path.write_text(json.dumps(manifest), encoding="utf-8")
    before = snapshot(source)
    with pytest.raises(guides.GuidePackageError):
        guides.create_guide_package(source, documents, output, apply=True)
    assert snapshot(source) == before
    assert not output.exists()
    assert not list(output.parent.glob(".*.guide-stage-*"))


@pytest.mark.parametrize("invalid", ["bad-pdf", "missing-guide", "empty-text", "invalid-encoding"])
def test_rejects_invalid_guides(package_inputs: tuple[Path, Path, Path], invalid: str) -> None:
    source, documents, output = package_inputs
    if invalid == "bad-pdf":
        (documents / guides.GUIDE_NAMES[0]).write_bytes(b"not a PDF")
    elif invalid == "missing-guide":
        (documents / guides.GUIDE_NAMES[1]).unlink()
    elif invalid == "empty-text":
        (documents / guides.GUIDE_NAMES[1]).write_bytes(b" ")
    else:
        (documents / guides.GUIDE_NAMES[1]).write_bytes(b"\xff")
    before = snapshot(source.parent)
    with pytest.raises(guides.GuidePackageError):
        guides.create_guide_package(source, documents, output, apply=True)
    assert snapshot(source.parent) == before


@pytest.mark.parametrize("overlap", ["customer", "guides"])
def test_rejects_overlapping_output(package_inputs: tuple[Path, Path, Path], overlap: str) -> None:
    source, documents, _ = package_inputs
    output = (source if overlap == "customer" else documents) / "new-copy"
    with pytest.raises(guides.GuidePackageError, match="겹치면"):
        guides.create_guide_package(source, documents, output, apply=True)


def test_existing_output_and_active_lock_are_preserved(package_inputs: tuple[Path, Path, Path]) -> None:
    source, documents, output = package_inputs
    output.mkdir()
    (output / "keep.txt").write_bytes(b"keep output")
    with pytest.raises(guides.GuidePackageError, match="이미"):
        guides.create_guide_package(source, documents, output, apply=True)
    assert (output / "keep.txt").read_bytes() == b"keep output"
    (output / "keep.txt").unlink()
    output.rmdir()
    lock = output.parent / f".{output.name}.guide-update.lock"
    lock.write_bytes(b"another copy operation")
    with pytest.raises(guides.GuidePackageError, match="진행 중"):
        guides.create_guide_package(source, documents, output, apply=True)
    assert lock.read_bytes() == b"another copy operation"


def test_rejects_linked_guide(package_inputs: tuple[Path, Path, Path]) -> None:
    source, documents, output = package_inputs
    original = documents / guides.GUIDE_NAMES[1]
    linked = documents / "actual-guide.txt"
    original.rename(linked)
    original.symlink_to(linked)
    with pytest.raises(guides.GuidePackageError, match="링크"):
        guides.create_guide_package(source, documents, output, apply=True)
    assert not output.exists()


@pytest.mark.parametrize("failure", ["copy", "verify"])
def test_failure_keeps_original_and_cleans_unpublished_copy(package_inputs: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    source, documents, output = package_inputs
    before = snapshot(source)
    if failure == "copy":
        def fail_copy(origin: Path, stage: Path, *args: object) -> None:
            (stage / "partial.exe").write_bytes(b"partial copy")
            raise OSError("injected copy failure")
        monkeypatch.setattr(guides, "_copy_payload", fail_copy)
    else:
        def fail_verify(*args: object) -> None:
            raise guides.GuidePackageError("injected final validation failure")
        monkeypatch.setattr(guides, "_verify_output", fail_verify)
    with pytest.raises((OSError, guides.GuidePackageError)):
        guides.create_guide_package(source, documents, output, apply=True)
    assert snapshot(source) == before
    assert not output.exists()
    assert not list(output.parent.glob(".*.guide-stage-*"))
    assert not list(output.parent.glob("*.guide-update.lock"))


def test_source_change_during_copy_prevents_publication(package_inputs: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    source, documents, output = package_inputs
    real_copy = guides._copy_payload
    def copy_then_change(origin: Path, stage: Path, *args: object) -> None:
        real_copy(origin, stage, *args)
        (origin / "barcode_db.xlsx").write_bytes(b"concurrent DB write")
    monkeypatch.setattr(guides, "_copy_payload", copy_then_change)
    with pytest.raises(guides.GuidePackageError, match="다릅니다"):
        guides.create_guide_package(source, documents, output, apply=True)
    assert not output.exists()


def test_cli_defaults_to_dry_run_and_apply_creates_verified_copy(package_inputs: tuple[Path, Path, Path]) -> None:
    source, documents, output = package_inputs
    arguments = [sys.executable, "-m", "barcode_label_automation.customer_guide_package", "--customer-dir", str(source), "--guides-dir", str(documents), "--output-dir", str(output)]
    dry_run = subprocess.run(arguments, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    assert dry_run.returncode == 0, dry_run.stderr
    assert "dry-run (쓰기 없음)" in dry_run.stdout
    assert not output.exists()
    applied = subprocess.run(arguments + ["--apply"], cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    assert applied.returncode == 0, applied.stderr
    assert validate_release_manifest(output)[0]


@pytest.mark.parametrize("runtime_dir", ["OUT", "_BACKUP", "TMP", "ChAeUmLaB", "__PYCACHE__"])
def test_unrecorded_runtime_folders_are_never_copied_regardless_of_case(package_inputs: tuple[Path, Path, Path], runtime_dir: str) -> None:
    source, documents, output = package_inputs
    private_folder = source / runtime_dir
    private_folder.mkdir()
    (private_folder / "private-fixture.txt").write_bytes(b"excluded runtime fixture")
    assert validate_release_manifest(source)[0]
    guides.create_guide_package(source, documents, output, apply=True)
    assert validate_release_manifest(output)[0]
    assert not (output / runtime_dir).exists()


def test_dry_run_also_rejects_invalid_update_history(package_inputs: tuple[Path, Path, Path]) -> None:
    source, documents, output = package_inputs
    path = source / guides.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    manifest["docs_updates"] = "invalid"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    before = snapshot(source.parent)
    with pytest.raises(guides.GuidePackageError, match="이력"):
        guides.create_guide_package(source, documents, output)
    assert snapshot(source.parent) == before


def test_link_inserted_during_copy_prevents_publication(package_inputs: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    source, documents, output = package_inputs
    real_copy = guides._copy_payload
    def copy_then_link(origin: Path, stage: Path, *args: object) -> None:
        real_copy(origin, stage, *args)
        config = origin / "config.ini"
        saved = source.parent / "same-config.ini"
        config.rename(saved)
        config.symlink_to(saved)
    monkeypatch.setattr(guides, "_copy_payload", copy_then_link)
    with pytest.raises(guides.GuidePackageError, match="링크"):
        guides.create_guide_package(source, documents, output, apply=True)
    assert not output.exists()


@pytest.mark.parametrize("invalid_path", ["C:/outside.txt", "C:outside.txt", "//server/share/secret.txt", "../outside.txt", "config.ini:stream"])
@pytest.mark.parametrize("location", ["files", "required_files"])
def test_rejects_windows_and_traversal_paths_before_copy(package_inputs: tuple[Path, Path, Path], invalid_path: str, location: str) -> None:
    source, documents, output = package_inputs
    path = source / guides.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    if location == "files":
        entry = dict(manifest["files"][0])
        entry["path"] = invalid_path
        manifest["files"].append(entry)
    else:
        manifest["required_files"].append(invalid_path)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    before = snapshot(source.parent)
    with pytest.raises(guides.GuidePackageError, match="경로"):
        guides.create_guide_package(source, documents, output, apply=True)
    assert snapshot(source.parent) == before


def test_rejects_casefold_duplicate_manifest_paths(package_inputs: tuple[Path, Path, Path]) -> None:
    source, documents, output = package_inputs
    path = source / guides.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    entry = dict(next(e for e in manifest["files"] if e["path"] == "README_먼저읽기.txt"))
    entry["path"] = "readme_먼저읽기.txt"
    manifest["files"].append(entry)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(guides.GuidePackageError, match="대소문자"):
        guides.create_guide_package(source, documents, output, apply=True)
    assert not output.exists()
