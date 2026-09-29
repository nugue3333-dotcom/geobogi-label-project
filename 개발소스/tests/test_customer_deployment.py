from __future__ import annotations

import json
import subprocess
import sys
import os
from pathlib import Path

import pytest

from barcode_label_automation.customer_deployment import (
    CustomerDeploymentError,
    assert_clean_deploy,
    create_customer_deployment,
    find_forbidden_deploy_items,
    next_deploy_dir,
    should_exclude,
)
from barcode_label_automation.release_manifest import MANIFEST_FILES, validate_release_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_required_customer_files(base_dir: Path) -> None:
    for item in MANIFEST_FILES:
        if not item.required:
            continue
        path = base_dir / item.path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            path.write_text('{"elements":[]}', encoding="utf-8")
        else:
            path.write_bytes(f"{path.name}\n".encode("utf-8"))


def test_next_deploy_dir_uses_next_available_suffix(tmp_path: Path) -> None:
    (tmp_path / "채움랩_라벨출력_고객용_20260708_01").mkdir()
    (tmp_path / "채움랩_라벨출력_고객용_20260708_02").mkdir()

    target = next_deploy_dir(tmp_path, date_stamp="20260708")

    assert target.name == "채움랩_라벨출력_고객용_20260708_03"


@pytest.mark.parametrize(
    ("relative", "is_dir"),
    [
        ("_backup/old.txt", False),
        ("tmp/cache.txt", False),
        ("out/test.tspl", False),
        ("_MEI12345/pkg.dll", False),
        ("ChaeumLAB/LabelPrint/config.ini", False),
        ("last_run.log", False),
        ("labels.before-test.xlsm", False),
        ("print_log.xlsx", False),
        ("out", True),
    ],
)
def test_should_exclude_runtime_artifacts(relative: str, is_dir: bool) -> None:
    assert should_exclude(relative, is_dir=is_dir)


def test_create_customer_deployment_copies_clean_tree_and_regenerates_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    deploy_root = tmp_path / "deploy"
    _write_required_customer_files(source)
    (source / "_backup").mkdir()
    (source / "_backup" / "old.txt").write_text("backup", encoding="utf-8")
    (source / "tmp").mkdir()
    (source / "tmp" / "cache.txt").write_text("cache", encoding="utf-8")
    (source / "out").mkdir()
    (source / "out" / "dry-run.tspl").write_text("dry", encoding="utf-8")
    (source / "ChaeumLAB" / "LabelPrint").mkdir(parents=True)
    (source / "ChaeumLAB" / "LabelPrint" / "config.ini").write_text("runtime copy", encoding="utf-8")
    (source / "last_run.log").write_text("log", encoding="utf-8")
    (source / "labels.before-db-sync.20260708.xlsm").write_text("old", encoding="utf-8")
    (source / "db").mkdir(exist_ok=True)
    (source / "db" / "test.xlsx").write_text("sample", encoding="utf-8")
    (source / "tools" / "tools").mkdir(parents=True)
    (source / "tools" / "tools" / "copy.txt").write_text("nested", encoding="utf-8")
    (source / "tools" / "ocr" / "lstmtraining.exe").write_bytes(b"training")
    (source / "tools" / "ocr" / "manual.html").write_text("<html>", encoding="utf-8")
    (source / "tools" / "ocr" / "helper.jar").write_bytes(b"jar")
    (source / "tools" / "ocr" / "tessdata").mkdir(parents=True, exist_ok=True)
    (source / "tools" / "ocr" / "tessdata" / "osd.traineddata").write_bytes(b"osd")

    result = create_customer_deployment(source, deploy_root, date_stamp="20260708")

    assert result.target_dir.name == "채움랩_라벨출력_고객용_20260708_01"
    assert (result.target_dir / "라벨디자이너.exe").is_file()
    assert (result.target_dir / "release_manifest.json").is_file()
    assert validate_release_manifest(result.target_dir) == (True, "release_manifest.json 기준 필수 파일 확인")
    assert find_forbidden_deploy_items(result.target_dir) == []
    assert not (result.target_dir / "_backup").exists()
    assert not (result.target_dir / "tmp").exists()
    assert not (result.target_dir / "out").exists()
    assert not (result.target_dir / "ChaeumLAB").exists()


def test_create_customer_deployment_preserves_source_release_version(tmp_path: Path) -> None:
    source = tmp_path / "source"
    deploy_root = tmp_path / "deploy"
    _write_required_customer_files(source)
    (source / "release_manifest.json").write_text(
        json.dumps({"version": "2026.07.15.1100"}),
        encoding="utf-8",
    )

    result = create_customer_deployment(source, deploy_root, date_stamp="20260715")

    manifest = json.loads((result.target_dir / "release_manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "2026.07.15.1100"
    assert "버전: 2026.07.15.1100" in (result.target_dir / "버전정보.txt").read_text(encoding="utf-8-sig")


def test_assert_clean_deploy_rejects_forbidden_customer_files(tmp_path: Path) -> None:
    target = tmp_path / "deploy"
    target.mkdir()
    (target / "label_manager.exe").write_bytes(b"duplicate alias")
    (target / "db").mkdir()
    (target / "db" / "test.xlsx").write_bytes(b"sample")

    with pytest.raises(CustomerDeploymentError, match="고객배포 제외 대상"):
        assert_clean_deploy(target)


def test_create_customer_deployment_script_outputs_created_folder(tmp_path: Path) -> None:
    source = tmp_path / "source"
    deploy_root = tmp_path / "deploy"
    _write_required_customer_files(source)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "create_customer_deployment.py"),
            "--source",
            str(source),
            "--deploy-root",
            str(deploy_root),
            "--date-stamp",
            "20260708",
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "채움랩_라벨출력_고객용_20260708_01" in completed.stdout
    assert (deploy_root / "채움랩_라벨출력_고객용_20260708_01" / "release_manifest.json").is_file()
