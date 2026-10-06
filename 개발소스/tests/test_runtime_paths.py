from __future__ import annotations

from pathlib import Path

from barcode_label_automation.config import load_config
from barcode_label_automation.runtime_paths import runtime_base_dir


def _expected_user_data_dir(local_app_data: Path) -> Path:
    return local_app_data / "ChaeumLAB" / "LabelPrint"


def test_runtime_base_dir_uses_local_app_data_for_program_files(monkeypatch, tmp_path):
    local_app_data = tmp_path / "LocalAppData"
    program_files = tmp_path / "Program Files (x86)"
    install_dir = program_files / "ChaeumLABLabel"
    install_dir.mkdir(parents=True)
    (install_dir / "config.ini").write_text("[printer]\n", encoding="utf-8")
    (install_dir / "templates").mkdir()
    (install_dir / "templates" / "default_label.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("ProgramFiles(x86)", str(program_files))

    base_dir = runtime_base_dir(install_dir)

    assert base_dir == _expected_user_data_dir(local_app_data)
    assert (base_dir / "config.ini").exists()
    assert (base_dir / "templates" / "default_label.json").exists()


def test_load_config_redirects_relative_data_paths_for_program_files(monkeypatch, tmp_path):
    local_app_data = tmp_path / "LocalAppData"
    program_files = tmp_path / "Program Files"
    install_dir = program_files / "ChaeumLABLabel"
    install_dir.mkdir(parents=True)
    config_path = install_dir / "config.ini"
    config_path.write_text(
        """
[printer]
brand = bixolon
mode = network
ip = 127.0.0.1
port = 9100

[data]
excel_file = print_queue.xlsx
output_dir = out
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("ProgramFiles", str(program_files))

    config = load_config(config_path)

    expected_base = _expected_user_data_dir(local_app_data)
    assert config.data.excel_file == expected_base / "print_queue.xlsx"
    assert config.data.output_dir == expected_base / "out"


def test_runtime_base_dir_preserves_existing_local_config_for_program_files(monkeypatch, tmp_path):
    local_app_data = tmp_path / "LocalAppData"
    program_files = tmp_path / "Program Files"
    install_dir = program_files / "ChaeumLABLabel"
    install_dir.mkdir(parents=True)
    source_config = install_dir / "config.ini"
    source_config.write_text("[printer]\nmedia_handling = peeler\n", encoding="utf-8")

    target_dir = _expected_user_data_dir(local_app_data)
    target_dir.mkdir(parents=True)
    target_config = target_dir / "config.ini"
    target_config.write_text("[printer]\nmedia_handling = tear_off\n", encoding="utf-8")
    old_time = 1_700_000_000
    new_time = 1_800_000_000
    target_config.touch()
    source_config.touch()
    import os

    os.utime(target_config, (old_time, old_time))
    os.utime(source_config, (new_time, new_time))

    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("ProgramFiles", str(program_files))

    base_dir = runtime_base_dir(install_dir)

    assert base_dir == target_dir
    assert "media_handling = tear_off" in target_config.read_text(encoding="utf-8")
    assert not list(target_dir.glob("config.*.bak"))


def test_runtime_base_dir_migrates_legacy_geobogi_local_data(monkeypatch, tmp_path):
    local_app_data = tmp_path / "LocalAppData"
    program_files = tmp_path / "Program Files"
    install_dir = program_files / "ChaeumLABLabel"
    install_dir.mkdir(parents=True)
    (install_dir / "config.ini").write_text("[printer]\nmedia_handling = tear_off\n", encoding="utf-8")

    legacy_dir = local_app_data / "GeobogiLabel"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "barcode_db.xlsx").write_bytes(b"legacy-db")
    (legacy_dir / "templates").mkdir()
    (legacy_dir / "templates" / "default_label.json").write_text('{"elements":[]}', encoding="utf-8")

    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("ProgramFiles", str(program_files))

    base_dir = runtime_base_dir(install_dir)

    expected_base = _expected_user_data_dir(local_app_data)
    assert base_dir == expected_base
    assert (expected_base / "barcode_db.xlsx").read_bytes() == b"legacy-db"
    assert (expected_base / "templates" / "default_label.json").exists()
    assert legacy_dir.exists()


def test_runtime_base_dir_uses_public_documents_when_user_env_is_missing(monkeypatch, tmp_path):
    public_dir = tmp_path / "Public"
    program_files = tmp_path / "Program Files"
    install_dir = program_files / "ChaeumLABLabel"
    install_dir.mkdir(parents=True)
    (install_dir / "config.ini").write_text("[printer]\n", encoding="utf-8")

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.setenv("PUBLIC", str(public_dir))
    monkeypatch.setenv("ProgramFiles", str(program_files))

    base_dir = runtime_base_dir(install_dir)

    assert base_dir == public_dir / "Documents" / "ChaeumLAB" / "LabelPrint"
    assert (base_dir / "config.ini").exists()


def test_upgrade_adds_new_examples_without_overwriting_customer_templates(monkeypatch, tmp_path):
    install_dir = tmp_path / "Program Files" / "ChaeumLAB"
    templates = install_dir / "templates"
    templates.mkdir(parents=True)
    (templates / "default_label.json").write_bytes(b'{"elements":[]}')
    (templates / "sample_excel_product.cllabel").write_bytes(b"new example")
    (templates / "sample_direct_open.cllabel").write_bytes(b"supplied example")
    target = _expected_user_data_dir(tmp_path / "Local")
    (target / "templates").mkdir(parents=True)
    (target / "templates" / "sample_direct_open.cllabel").write_bytes(b"customer edited example")
    (target / "templates" / "old.gblabel").write_bytes(b"legacy customer label")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
    result = runtime_base_dir(install_dir)
    assert result == target
    assert (target / "templates" / "sample_excel_product.cllabel").read_bytes() == b"new example"
    assert (target / "templates" / "sample_direct_open.cllabel").read_bytes() == b"customer edited example"
    assert (target / "templates" / "old.gblabel").read_bytes() == b"legacy customer label"


def test_initial_seed_keeps_blank_default_alongside_new_example(monkeypatch, tmp_path):
    install_dir = tmp_path / "Program Files" / "ChaeumLAB"
    templates = install_dir / "templates"
    templates.mkdir(parents=True)
    (templates / "default_label.json").write_bytes(b'{"elements":[]}')
    (templates / "sample_excel_product.cllabel").write_bytes(b"new example")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
    target = runtime_base_dir(install_dir)
    assert (target / "templates" / "default_label.json").read_bytes() == b'{"elements":[]}'
    assert (target / "templates" / "sample_excel_product.cllabel").read_bytes() == b"new example"
