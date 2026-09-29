from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_DIR = PROJECT_ROOT / "고객용_실행폴더"


def test_customer_folder_does_not_ship_duplicate_gui_aliases() -> None:
    duplicate_aliases = [
        "label_designer.exe",
        "label_manager.exe",
        "printer_settings.exe",
    ]

    for name in duplicate_aliases:
        assert not (CUSTOMER_DIR / name).exists()


def test_customer_folder_keeps_required_internal_executables() -> None:
    required = [
        "라벨디자이너.exe",
        "라벨출력관리.exe",
        "프린터설정.exe",
        "고객환경점검.exe",
        "라벨작업실행기.exe",
        "라벨출력엔진.exe",
    ]

    for name in required:
        assert (CUSTOMER_DIR / name).is_file()


def test_customer_folder_includes_backup_and_restore_commands() -> None:
    assert (CUSTOMER_DIR / "고객데이터_백업.cmd").is_file()
    assert (CUSTOMER_DIR / "고객데이터_복원.cmd").is_file()


def test_customer_folder_does_not_ship_nested_tools_copy() -> None:
    assert not (CUSTOMER_DIR / "tools" / "tools").exists()


def test_customer_folder_does_not_ship_runtime_artifacts() -> None:
    assert not (CUSTOMER_DIR / "out").exists()
    assert not (CUSTOMER_DIR / "ChaeumLAB").exists()
    assert not (CUSTOMER_DIR / "last_run.log").exists()
    assert not (CUSTOMER_DIR / "print_log.xlsx").exists()
    assert not list(CUSTOMER_DIR.glob("_MEI*"))


def test_pyinstaller_runtime_temp_uses_public_ascii_path() -> None:
    spec_names = [
        "customer_preflight.spec",
        "label_designer.spec",
        "label_job_runner.spec",
        "label_manager.spec",
        "print_labels.spec",
        "printer_settings.spec",
    ]

    for spec_name in spec_names:
        text = (PROJECT_ROOT / spec_name).read_text(encoding="utf-8")
        assert r"runtime_tmpdir=r'C:\Users\Public\ChaeumLABRuntime'" in text
        assert "runtime_tmpdir='.'" not in text
        assert 'runtime_tmpdir="."' not in text
        assert "runtime_tmpdir=None" not in text


def test_release_build_gate_covers_all_six_specs_and_korean_executables() -> None:
    script = (PROJECT_ROOT / "scripts" / "build_release_exes.ps1").read_text(encoding="utf-8")
    expected_pairs = {
        "customer_preflight.spec": "고객환경점검.exe",
        "label_designer.spec": "라벨디자이너.exe",
        "label_job_runner.spec": "라벨작업실행기.exe",
        "label_manager.spec": "라벨출력관리.exe",
        "print_labels.spec": "라벨출력엔진.exe",
        "printer_settings.spec": "프린터설정.exe",
    }

    for spec_name, exe_name in expected_pairs.items():
        assert spec_name in script
        assert exe_name in script
    assert "--clean --noconfirm" in script
    assert "Assert-ExactExecutables" in script
    assert "$SyncRoots = @($ProjectRoot, $CustomerRoot, $FinalRoot)" in script
    assert "Get-FileSha256" in script
    assert "EXE 동기화 해시 불일치" in script
    assert "-m barcode_label_automation.release_manifest" in script
    assert "--source-root $ProjectRoot" in script
    assert "--test-result $TestResult" in script


def test_customer_folder_does_not_ship_development_sample_workbooks() -> None:
    assert not list(CUSTOMER_DIR.glob("labels.before-*.xlsm"))
    assert not (CUSTOMER_DIR / "db" / "123.xlsm").exists()
    assert not (CUSTOMER_DIR / "db" / "test.xlsx").exists()


def test_customer_cmd_files_set_utf8_codepage() -> None:
    for path in CUSTOMER_DIR.glob("*.cmd"):
        text = path.read_text(encoding="utf-8-sig")
        assert "chcp 65001 >nul" in "\n".join(text.splitlines()[:3]), path.name


def test_customer_folder_has_no_old_brand_text_in_text_files() -> None:
    old_terms = ["거복이의꿈", "Geobogi Dream", "GeobogiDream", "Geobogi label", "Geobok Dream"]
    extensions = {".cmd", ".ps1", ".txt", ".json", ".ini", ".md", ".csv"}

    for path in CUSTOMER_DIR.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        for term in old_terms:
            assert term not in text, f"{term!r} remained in {path}"


def test_customer_docs_use_chaeumlab_user_data_folder() -> None:
    doc_names = ["README_먼저읽기.txt", "사용안내.txt", "설치_및_사용_메뉴얼.txt"]

    for name in doc_names:
        text = (CUSTOMER_DIR / name).read_text(encoding="utf-8-sig")
        assert r"%LOCALAPPDATA%\ChaeumLAB\LabelPrint" in text, name
        assert r"저장됩니다. 고객 PC 백업 시 이 폴더" not in text, name
        assert r"자동으로 %LOCALAPPDATA%\GeobogiLabel" not in text, name
        assert r"%LOCALAPPDATA%\GeobogiLabel 폴더에 저장됩니다" not in text, name


def test_customer_runner_uses_chaeumlab_user_data_folder() -> None:
    text = (CUSTOMER_DIR / "run_label_job.ps1").read_text(encoding="utf-8-sig")

    assert '"ChaeumLAB"' in text
    assert '"LabelPrint"' in text
    assert "$LegacyUserDataDir" in text
    assert 'Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "GeobogiLabel"' not in text


def test_customer_folder_ocr_runtime_excludes_training_tools() -> None:
    ocr_dir = CUSTOMER_DIR / "tools" / "ocr"
    if not ocr_dir.exists():
        return
    forbidden_names = {
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
    for name in forbidden_names:
        assert not (ocr_dir / name).exists(), name
    assert not (ocr_dir / "tessdata" / "osd.traineddata").exists()
    assert not list(ocr_dir.rglob("*.html"))
    assert not list(ocr_dir.rglob("*.jar"))


def test_customer_folder_includes_chaeumlab_brand_assets() -> None:
    brand_dir = CUSTOMER_DIR / "assets" / "brand"

    assert (brand_dir / "chaeumlab_logo_header.png").is_file()
    assert (brand_dir / "chaeumlab_logo_compact.png").is_file()
    assert (brand_dir / "chaeumlab_app_icon.ico").is_file()
    assert (brand_dir / "chaeumlab_app_icon_white.ico").is_file()
    assert (brand_dir / "chaeumlab_label_file_icon_white.ico").is_file()
