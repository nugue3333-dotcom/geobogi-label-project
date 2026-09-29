from __future__ import annotations

import hashlib
import json
from pathlib import Path

from barcode_label_automation.release_manifest import (
    MANIFEST_FILES,
    SPEC_NAMES,
    validate_release_manifest,
    write_release_manifest,
)


def _write_manifest_fixture(base_dir: Path) -> None:
    for item in MANIFEST_FILES:
        if not item.required:
            continue
        path = base_dir / item.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture:{item.path}", encoding="utf-8")


def _write_specs(source_root: Path) -> None:
    for name in SPEC_NAMES:
        (source_root / name).write_text(f"spec:{name}", encoding="utf-8")


def test_write_release_manifest_records_full_payload_and_build_metadata(tmp_path: Path) -> None:
    package_dir = tmp_path / "customer"
    source_root = tmp_path / "source"
    package_dir.mkdir()
    source_root.mkdir()
    _write_manifest_fixture(package_dir)
    _write_specs(source_root)
    nested_payload = package_dir / "tools" / "ocr" / "runtime.dll"
    nested_payload.parent.mkdir(parents=True, exist_ok=True)
    nested_payload.write_bytes(b"runtime")
    (package_dir / "out").mkdir()
    (package_dir / "out" / "last_run.log").write_text("runtime", encoding="utf-8")
    (package_dir / "_backup").mkdir()
    (package_dir / "_backup" / "labels.before-test.xlsm").write_text("runtime", encoding="utf-8")

    json_path, text_path = write_release_manifest(
        package_dir,
        package_name="테스트패키지",
        package_version="2026.07.14",
        source_root=source_root,
        build_id="build-001",
        test_result="42 passed",
        python_version="3.13.7",
        pyinstaller_version="6.14.2",
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    paths = {entry["path"] for entry in payload["files"]}
    version_text = (package_dir / "버전정보.txt").read_text(encoding="utf-8-sig")
    assert payload["schema_version"] == 2
    assert payload["brand"] == "채움랩"
    assert payload["package"] == {"name": "테스트패키지", "version": "2026.07.14"}
    assert payload["build"]["id"] == "build-001"
    assert payload["build"]["python_version"] == "3.13.7"
    assert payload["build"]["pyinstaller_version"] == "6.14.2"
    assert payload["build"]["test_result"] == "42 passed"
    assert len(payload["build"]["specs"]) == 6
    assert all(spec["exists"] and len(spec["sha256"]) == 64 for spec in payload["build"]["specs"])
    expected_hash = hashlib.sha256((source_root / SPEC_NAMES[0]).read_bytes()).hexdigest()
    assert payload["build"]["specs"][0]["sha256"] == expected_hash
    assert "tools/ocr/runtime.dll" in paths
    assert "버전정보.txt" in paths
    assert "release_manifest.json" not in paths
    assert "배포_파일목록.txt" in paths
    assert "out/last_run.log" not in paths
    assert "_backup/labels.before-test.xlsm" not in paths
    assert all(entry["size"] >= 0 and len(entry["sha256"]) == 64 for entry in payload["files"])
    assert payload["summary"]["missing_required_files"] == 0
    assert "버전: 2026.07.14" in version_text
    assert "테스트패키지" in text_path.read_text(encoding="utf-8-sig")
    assert validate_release_manifest(package_dir) == (True, "release_manifest.json 기준 필수 파일 확인")


def test_validate_release_manifest_detects_changed_file(tmp_path: Path) -> None:
    _write_manifest_fixture(tmp_path)
    write_release_manifest(tmp_path)
    (tmp_path / "라벨디자이너.exe").write_text("changed", encoding="utf-8")

    ok, message = validate_release_manifest(tmp_path)

    assert not ok
    assert "배포 후 변경된 파일" in message
    assert "라벨디자이너.exe" in message


def test_validate_release_manifest_allows_expected_customer_data_changes(tmp_path: Path) -> None:
    _write_manifest_fixture(tmp_path)
    write_release_manifest(tmp_path)
    (tmp_path / "print_queue.xlsx").write_text("customer queue changed", encoding="utf-8")
    (tmp_path / "config.ini").write_text("customer settings changed", encoding="utf-8")
    (tmp_path / "templates" / "default_label.json").write_text('{"elements":[{"type":"text"}]}', encoding="utf-8")

    assert validate_release_manifest(tmp_path) == (True, "release_manifest.json 기준 필수 파일 확인")


def test_validate_release_manifest_detects_missing_file(tmp_path: Path) -> None:
    _write_manifest_fixture(tmp_path)
    write_release_manifest(tmp_path)
    (tmp_path / "프린터설정.exe").unlink()

    ok, message = validate_release_manifest(tmp_path)

    assert not ok
    assert "누락 필수 파일" in message
    assert "프린터설정.exe" in message


def test_validate_release_manifest_detects_unexpected_file(tmp_path: Path) -> None:
    _write_manifest_fixture(tmp_path)
    write_release_manifest(tmp_path)
    (tmp_path / "unexpected.txt").write_text("new", encoding="utf-8")

    ok, message = validate_release_manifest(tmp_path)

    assert not ok
    assert "manifest에 없는 추가 파일" in message
    assert "unexpected.txt" in message


def test_validate_release_manifest_rejects_forbidden_file_even_if_manifested(tmp_path: Path) -> None:
    _write_manifest_fixture(tmp_path)
    (tmp_path / "print_labels.exe").write_text("old alias", encoding="utf-8")
    write_release_manifest(tmp_path)

    ok, message = validate_release_manifest(tmp_path)

    assert not ok
    assert "추가 금지 파일" in message
    assert "print_labels.exe" in message


def test_validate_release_manifest_ignores_runtime_generated_files(tmp_path: Path) -> None:
    _write_manifest_fixture(tmp_path)
    write_release_manifest(tmp_path)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "last_run.log").write_text("runtime", encoding="utf-8")
    (tmp_path / "print_log.xlsx").write_text("runtime", encoding="utf-8")

    assert validate_release_manifest(tmp_path) == (True, "release_manifest.json 기준 필수 파일 확인")


def test_validate_release_manifest_rejects_path_traversal(tmp_path: Path) -> None:
    _write_manifest_fixture(tmp_path)
    json_path, _ = write_release_manifest(tmp_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload["files"][0]["path"] = "../outside.txt"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    ok, message = validate_release_manifest(tmp_path)

    assert not ok
    assert "파일 경로가 잘못되었습니다" in message
