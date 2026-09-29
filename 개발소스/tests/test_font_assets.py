from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from barcode_label_automation.font_assets import (
    APP_FONT_FAMILY,
    APP_FONT_RELATIVE_PATH,
    APP_FONT_SHA256,
    bundled_font_path,
    register_bundled_font,
)
from barcode_label_automation.label_designer_app import DEFAULT_FONT_NAME, _load_font
from barcode_label_automation.release_manifest import MANIFEST_FILES
from barcode_label_automation.ui_tokens import TYPOGRAPHY


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_moneygraphy_font_asset_matches_supplied_file() -> None:
    path = PROJECT_ROOT / APP_FONT_RELATIVE_PATH

    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == APP_FONT_SHA256
    assert bundled_font_path(base_dir=PROJECT_ROOT) == path


def test_all_program_typography_tokens_use_moneygraphy() -> None:
    assert TYPOGRAPHY.page_title[0] == APP_FONT_FAMILY
    assert TYPOGRAPHY.section_title[0] == APP_FONT_FAMILY
    assert TYPOGRAPHY.body[0] == APP_FONT_FAMILY
    assert TYPOGRAPHY.caption[0] == APP_FONT_FAMILY
    assert TYPOGRAPHY.table_text[0] == APP_FONT_FAMILY
    assert TYPOGRAPHY.button_text[0] == APP_FONT_FAMILY
    assert DEFAULT_FONT_NAME == APP_FONT_FAMILY


@pytest.mark.skipif(os.name != "nt", reason="Windows GDI font registration")
def test_bundled_font_registers_and_strictly_loads_for_label_rendering() -> None:
    assert register_bundled_font(base_dir=PROJECT_ROOT)
    assert _load_font(14, APP_FONT_FAMILY).getname()[0] == "MoneygraphyTTF Rounded"


def test_three_gui_specs_bundle_font_assets() -> None:
    for spec_name in ("label_designer.spec", "label_manager.spec", "printer_settings.spec"):
        source = (PROJECT_ROOT / spec_name).read_text(encoding="utf-8")
        assert 'collect_data_tree("assets/fonts", "assets/fonts")' in source
        assert "+ font_datas" in source


def test_customer_manifest_and_first_run_include_font_installation() -> None:
    manifest_paths = {item.path.replace("\\", "/") for item in MANIFEST_FILES}
    assert APP_FONT_RELATIVE_PATH.as_posix() in manifest_paths
    assert "assets/fonts/README.txt" in manifest_paths
    assert "scripts/install_chaeumlab_font.ps1" in manifest_paths

    first_run = (PROJECT_ROOT / "처음실행_점검.cmd").read_text(encoding="utf-8")
    installer = (PROJECT_ROOT / "00_install_trusted_location.cmd").read_text(encoding="utf-8")
    assert "install_chaeumlab_font.ps1" in first_run
    assert "install_chaeumlab_font.ps1" in installer
