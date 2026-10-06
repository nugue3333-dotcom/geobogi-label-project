from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook

from barcode_label_automation.customer_preflight import (
    REQUIRED_BRAND_ASSET_FILES,
    _check_dry_run,
    _check_runtime_temp_hygiene,
    default_report_path,
    default_support_package_path,
    main,
    run_preflight,
    write_report,
    write_support_package,
)
from barcode_label_automation.data_store import save_label_rows
from barcode_label_automation.release_manifest import MANIFEST_FILES, write_release_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_workbook(path: Path) -> None:
    workbook = Workbook()
    workbook.active["A1"] = "barcode"
    workbook.save(path)


def _write_deploy_fixture(base_dir: Path) -> None:
    for name in (
        "라벨디자이너.exe",
        "라벨출력관리.exe",
        "프린터설정.exe",
        "라벨작업실행기.exe",
        "라벨출력엔진.exe",
        "고객환경점검.exe",
    ):
        (base_dir / name).write_bytes(b"stub")
    for name in ("README_먼저읽기.txt", "사용안내.txt", "설치_및_사용_메뉴얼.txt", "라벨출력패키지_고객용_매뉴얼.docx"):
        (base_dir / name).write_text("manual", encoding="utf-8")
    (base_dir / "config.ini").write_text(
        """
[printer]
brand = tsc
mode = network
ip = 127.0.0.1
port = 9100

[label]
width_mm = 58
height_mm = 40
dpi = 203

[data]
excel_file = print_queue.xlsx
output_dir = out
""".strip(),
        encoding="utf-8",
    )
    (base_dir / "templates").mkdir()
    (base_dir / "templates" / "default_label.json").write_text(
        json.dumps({"label": {"width_mm": 58, "height_mm": 40}, "elements": []}),
        encoding="utf-8",
    )
    _write_workbook(base_dir / "barcode_db.xlsx")
    save_label_rows(
        base_dir / "print_queue.xlsx",
        [
            {
                "item_code": "A1001",
                "item_name": "SENSOR BRACKET",
                "barcode": "088023502",
                "lot_no": "LOT250531",
                "qty": "100",
                "print_qty": "1",
            }
        ],
    )
    _write_workbook(base_dir / "labels.xlsm")
    _write_workbook(base_dir / "print_log.xlsx")
    font_target = base_dir / "assets" / "fonts" / "MONEYGRAPHY-ROUNDED.TTF"
    font_target.parent.mkdir(parents=True, exist_ok=True)
    font_target.write_bytes((PROJECT_ROOT / "assets" / "fonts" / "MONEYGRAPHY-ROUNDED.TTF").read_bytes())
    for item in MANIFEST_FILES:
        if not item.required:
            continue
        path = base_dir / item.path
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stub", encoding="utf-8")
    for relative in REQUIRED_BRAND_ASSET_FILES:
        path = base_dir / relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"brand fixture")
    write_release_manifest(base_dir, package_name="test-package")


def test_run_preflight_accepts_ready_customer_folder(tmp_path):
    _write_deploy_fixture(tmp_path)

    report = run_preflight(tmp_path, run_dry_run=False)

    assert report.ok
    assert report.install_dir == tmp_path
    assert report.data_dir == tmp_path


def test_preflight_dry_run_uses_disposable_copy(tmp_path, monkeypatch):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "라벨작업실행기.exe").write_bytes(b"runner")
    (install_dir / "라벨출력엔진.exe").write_bytes(b"engine")
    (install_dir / "config.ini").write_text("[data]\nexcel_file = labels.xlsm\noutput_dir = out\n", encoding="utf-8")
    (install_dir / "labels.xlsm").write_bytes(b"labels")
    original_queue = install_dir / "print_queue.xlsx"
    original_queue.write_bytes(b"original queue")
    captured: dict[str, Path] = {}

    def fake_run(command, *, cwd, **_kwargs):
        isolated = Path(cwd)
        captured["cwd"] = isolated
        (isolated / "out").mkdir()
        (isolated / "print_queue.xlsx").write_bytes(b"rewritten queue")
        return subprocess.CompletedProcess(command, 0, stdout="isolated dry-run\n", stderr="")

    monkeypatch.setattr("barcode_label_automation.customer_preflight.subprocess.run", fake_run)

    result = _check_dry_run(install_dir, install_dir, install_dir / "config.ini", 5)

    assert result.ok
    assert original_queue.read_bytes() == b"original queue"
    assert not (install_dir / "out").exists()
    assert captured["cwd"] != install_dir
    assert not captured["cwd"].exists()


def test_run_preflight_reports_missing_required_file(tmp_path):
    _write_deploy_fixture(tmp_path)
    (tmp_path / "라벨출력관리.exe").unlink()

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    assert any(result.name == "실행 파일 라벨출력관리.exe" and not result.ok for result in report.results)


def test_run_preflight_reports_invalid_config(tmp_path):
    _write_deploy_fixture(tmp_path)
    (tmp_path / "config.ini").write_text("[printer]\nbrand = unknown\n", encoding="utf-8")

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    assert any(result.name == "config.ini 설정" and not result.ok for result in report.results)


def test_main_returns_nonzero_on_failed_preflight(tmp_path, capsys):
    _write_deploy_fixture(tmp_path)
    (tmp_path / "print_queue.xlsx").unlink()

    assert main(["--base-dir", str(tmp_path), "--skip-dry-run"]) == 1
    assert "오류" in capsys.readouterr().out


def test_write_report_creates_support_diagnostic_file(tmp_path):
    _write_deploy_fixture(tmp_path)
    report = run_preflight(tmp_path, run_dry_run=False)

    report_path = write_report(report)

    assert report_path == tmp_path / "out" / "customer_preflight_report.txt"
    text = report_path.read_text(encoding="utf-8-sig")
    assert "채움랩 라벨 출력 패키지 실행 전 점검" in text
    assert "점검 결과: 정상" in text
    assert "배포 파일 release_manifest.json" in text
    assert "배포 파일 시작하기.cmd" in text
    assert "배포 파일 처음실행_점검.cmd" in text
    assert "배포 파일 버전정보.txt" in text
    assert "배포 파일 고객데이터_백업.cmd" in text
    assert "배포 파일 고객데이터_복원.cmd" in text
    assert "배포 파일 00_install_trusted_location.cmd" in text
    assert "배포 파일 register_label_filetype.cmd" in text
    assert "배포 폴더 정리" in text
    assert "런타임 임시 폴더" in text
    assert "브랜드 로고" in text
    assert "실행 파일 release_manifest.json" not in text
    assert str(tmp_path) not in text
    assert "<INSTALL_DIR>" in text


def test_run_preflight_reports_duplicate_or_temporary_distribution_artifacts(tmp_path):
    _write_deploy_fixture(tmp_path)
    (tmp_path / "label_designer.exe").write_bytes(b"duplicate")
    (tmp_path / "tools" / "tools").mkdir(parents=True)
    (tmp_path / "_MEI12345").mkdir()
    (tmp_path / "labels.before-db-sync.20260604-154908.xlsm").write_bytes(b"backup")
    (tmp_path / "db").mkdir(exist_ok=True)
    (tmp_path / "db" / "test.xlsx").write_bytes(b"sample")

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    hygiene = next(result for result in report.results if result.name == "배포 폴더 정리")
    assert not hygiene.ok
    assert "label_designer.exe" in hygiene.message
    assert "tools/tools" in hygiene.message
    assert "_MEI12345" in hygiene.message
    assert "labels.before-db-sync.20260604-154908.xlsm" in hygiene.message


def test_run_preflight_reports_unneeded_ocr_training_artifacts(tmp_path):
    _write_deploy_fixture(tmp_path)
    ocr_dir = tmp_path / "tools" / "ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    (ocr_dir / "lstmtraining.exe").write_bytes(b"training")
    (ocr_dir / "tesseract.1.html").write_text("manual", encoding="utf-8")
    (ocr_dir / "tessdata").mkdir(parents=True, exist_ok=True)
    (ocr_dir / "tessdata" / "osd.traineddata").write_bytes(b"osd")

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    hygiene = next(result for result in report.results if result.name == "OCR 런타임 정리")
    assert not hygiene.ok
    assert "lstmtraining.exe" in hygiene.message
    assert "tesseract.1.html" in hygiene.message
    assert "tessdata/osd.traineddata" in hygiene.message


def test_run_preflight_reports_missing_brand_logo_asset(tmp_path):
    _write_deploy_fixture(tmp_path)
    (tmp_path / "assets" / "brand" / "chaeumlab_logo_header.png").unlink()

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    logo = next(result for result in report.results if result.name == "브랜드 로고")
    assert not logo.ok
    assert "chaeumlab_logo_header.png" in logo.message


@pytest.mark.parametrize("filename", [
    "chaeumlab_designer_icon.ico",
    "chaeumlab_manager_icon.ico",
    "chaeumlab_settings_icon.ico",
    "chaeumlab_project_file_icon_white.ico",
])
@pytest.mark.parametrize("empty", [False, True])
def test_run_preflight_requires_role_and_project_icons(tmp_path, filename, empty):
    _write_deploy_fixture(tmp_path)
    icon = tmp_path / "assets" / "brand" / filename
    if empty:
        icon.write_bytes(b"")
    else:
        icon.unlink()

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    brand = next(result for result in report.results if result.name == "브랜드 로고")
    assert not brand.ok
    assert filename in brand.message


def test_run_preflight_rejects_nonblank_default_template(tmp_path):
    _write_deploy_fixture(tmp_path)
    (tmp_path / "templates" / "default_label.json").write_text(
        json.dumps(
            {
                "label": {"width_mm": 58, "height_mm": 40},
                "elements": [{"type": "text", "text": "OLD", "x": 1, "y": 1, "width": 10, "height": 5}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    template = next(result for result in report.results if result.name == "기본 템플릿")
    assert not template.ok
    assert "빈 배열" in template.message


def test_run_preflight_reports_empty_print_queue(tmp_path):
    _write_deploy_fixture(tmp_path)
    save_label_rows(tmp_path / "print_queue.xlsx", [])

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    readiness = next(result for result in report.results if result.name == "인쇄 데이터 준비")
    assert not readiness.ok
    assert "인쇄할 유효한 행이 없습니다" in readiness.message


def test_run_preflight_reports_missing_print_queue_barcode(tmp_path):
    _write_deploy_fixture(tmp_path)
    save_label_rows(
        tmp_path / "print_queue.xlsx",
        [{"item_code": "A1001", "item_name": "SENSOR BRACKET", "barcode": "", "lot_no": "LOT250531", "qty": "100", "print_qty": "1"}],
    )

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    readiness = next(result for result in report.results if result.name == "인쇄 데이터 준비")
    assert not readiness.ok
    assert "1행 바코드가 비어 있습니다" in readiness.message


def test_run_preflight_reports_invalid_print_quantity(tmp_path):
    _write_deploy_fixture(tmp_path)
    save_label_rows(
        tmp_path / "print_queue.xlsx",
        [
            {
                "item_code": "A1001",
                "item_name": "SENSOR BRACKET",
                "barcode": "088023502",
                "lot_no": "LOT250531",
                "qty": "100",
                "print_qty": "0",
            }
        ],
    )

    report = run_preflight(tmp_path, run_dry_run=False)

    assert not report.ok
    readiness = next(result for result in report.results if result.name == "인쇄 데이터 준비")
    assert not readiness.ok
    assert "출력 매수는 1부터 1000 사이" in readiness.message


def test_run_preflight_ignores_active_pyinstaller_temp_dir(monkeypatch, tmp_path):
    _write_deploy_fixture(tmp_path)
    active_mei = tmp_path / "_MEI99999"
    active_mei.mkdir()
    monkeypatch.setattr("sys._MEIPASS", str(active_mei), raising=False)

    report = run_preflight(tmp_path, run_dry_run=False)

    assert report.ok
    hygiene = next(result for result in report.results if result.name == "배포 폴더 정리")
    assert hygiene.ok


def test_runtime_temp_hygiene_removes_old_pyinstaller_dirs(tmp_path):
    runtime_dir = tmp_path / "ChaeumLABRuntime"
    old_dir = runtime_dir / "_MEIold"
    old_dir.mkdir(parents=True)
    (old_dir / "runtime.dll").write_bytes(b"stale")
    now = 1_700_000_000
    os.utime(old_dir, (now - 7200, now - 7200))

    result = _check_runtime_temp_hygiene(runtime_dir, max_age_seconds=3600, now=now, allow_cleanup=True)

    assert result.ok
    assert "오래된 폴더 1개 정리" in result.message
    assert not old_dir.exists()


def test_runtime_temp_hygiene_keeps_active_and_recent_dirs(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "ChaeumLABRuntime"
    active_dir = runtime_dir / "_MEIactive"
    recent_dir = runtime_dir / "_MEIrecent"
    active_dir.mkdir(parents=True)
    recent_dir.mkdir()
    now = 1_700_000_000
    os.utime(active_dir, (now - 7200, now - 7200))
    os.utime(recent_dir, (now - 60, now - 60))
    monkeypatch.setattr("sys._MEIPASS", str(active_dir), raising=False)

    result = _check_runtime_temp_hygiene(runtime_dir, max_age_seconds=3600, now=now, allow_cleanup=True)

    assert result.ok
    assert "실행 중 1개 보류" in result.message
    assert "최근 폴더 1개 보류" in result.message
    assert active_dir.exists()
    assert recent_dir.exists()


def test_runtime_temp_hygiene_reports_protected_stale_directory_as_nonfatal_warning(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "ChaeumLABRuntime"
    protected_dir = runtime_dir / "_MEIprotected"
    protected_dir.mkdir(parents=True)
    now = 1_700_000_000
    os.utime(protected_dir, (now - 7200, now - 7200))

    def deny_delete(_path):
        raise PermissionError(5, "access denied")

    monkeypatch.setattr("barcode_label_automation.customer_preflight.shutil.rmtree", deny_delete)

    result = _check_runtime_temp_hygiene(runtime_dir, max_age_seconds=3600, now=now, allow_cleanup=True)

    assert result.ok
    assert "보류" in result.message
    assert "프로그램 실행과 고객 데이터에는 영향이 없습니다" in result.message
    assert protected_dir.exists()


def test_main_writes_report_by_default(tmp_path):
    _write_deploy_fixture(tmp_path)

    assert main(["--base-dir", str(tmp_path), "--skip-dry-run"]) == 0

    assert default_report_path(run_preflight(tmp_path, run_dry_run=False)).exists()
    assert default_support_package_path(run_preflight(tmp_path, run_dry_run=False)).exists()


def test_main_can_skip_report_file(tmp_path):
    _write_deploy_fixture(tmp_path)

    assert main(["--base-dir", str(tmp_path), "--skip-dry-run", "--no-report", "--no-support-package"]) == 0

    assert not (tmp_path / "out" / "customer_preflight_report.txt").exists()


def test_write_support_package_excludes_raw_customer_workbooks(tmp_path):
    _write_deploy_fixture(tmp_path)
    report = run_preflight(tmp_path, run_dry_run=False)

    package_path = write_support_package(report)

    assert package_path == tmp_path / "out" / "customer_support_package.zip"
    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        assert "customer_preflight_report.txt" in names
        assert "config_summary.txt" in names
        assert "environment_summary.txt" in names
        assert "file_inventory.txt" in names
        assert "release_manifest_summary.txt" in names
        assert "print_log_summary.txt" in names
        assert "barcode_db.xlsx" not in names
        assert "print_queue.xlsx" not in names
        assert "labels.xlsm" not in names
        report_text = archive.read("customer_preflight_report.txt").decode("utf-8")
        config_text = archive.read("config_summary.txt").decode("utf-8")
        environment_text = archive.read("environment_summary.txt").decode("utf-8")
    assert str(tmp_path) not in report_text
    assert "printer_ip=127.0.0.xxx" in config_text
    assert "runtime_storage=install_folder" in environment_text
    assert str(tmp_path) not in environment_text
