from __future__ import annotations

import inspect
from types import SimpleNamespace

from configparser import ConfigParser

import pytest

from barcode_label_automation import config as config_module
from barcode_label_automation.settings_app import PrinterSettings, SettingsApp, load_settings, main, save_settings, validate_settings


def test_save_settings_updates_config_ini(tmp_path):
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="zebra",
        mode="windows_raw",
        print_method="thermal_transfer",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="ZDesigner Label Printer",
        width_mm=80,
        height_mm=40,
        dpi=300,
        gap_mm=2.5,
    )

    save_settings(config_path, settings)
    loaded = load_settings(config_path)

    assert loaded == settings
    parser = ConfigParser()
    parser.read(config_path, encoding="utf-8-sig")
    assert not parser.has_option("printer", "model")


def test_save_settings_keeps_barcode_options(tmp_path):
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="tsc",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=3,
        barcode_type="qr",
        barcode_auto_layout=False,
        barcode_x=120,
        barcode_y=90,
        barcode_rotation=90,
        one_d_height=70,
        one_d_narrow=2,
        one_d_wide=3,
        one_d_human_readable=False,
        qr_model=2,
        qr_ecc="Q",
        qr_cell_size=5,
        datamatrix_cell_size=6,
        pdf417_rows=20,
        pdf417_columns=4,
        pdf417_security_level=3,
        pdf417_module_width=4,
        pdf417_module_height=12,
    )

    save_settings(config_path, settings)
    loaded = load_settings(config_path)

    assert loaded == settings


def test_save_settings_keeps_media_handling_option(tmp_path):
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="tsc",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=3,
        media_handling="peeler",
    )

    save_settings(config_path, settings)
    loaded = load_settings(config_path)

    assert loaded.media_handling == "peeler"


def test_save_settings_keeps_print_orientation_option(tmp_path):
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="bixolon",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=3,
        print_orientation="rotate_180",
    )

    save_settings(config_path, settings)

    assert load_settings(config_path).print_orientation == "rotate_180"


def test_validate_settings_rejects_unknown_print_orientation():
    settings = PrinterSettings(
        brand="tsc",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=3,
        print_orientation="sideways",
    )

    assert any("인쇄 방향" in error for error in validate_settings(settings).errors)


def test_save_settings_keeps_media_type_option(tmp_path):
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="zebra",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=3,
        media_type="black_mark",
    )

    save_settings(config_path, settings)
    loaded = load_settings(config_path)

    assert loaded.media_type == "black_mark"


def test_save_settings_rejects_gap_media_without_gap_value(tmp_path):
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="tsc",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=0,
        media_type="gap",
    )

    with pytest.raises(ValueError, match="갭 용지와 블랙마크 용지"):
        save_settings(config_path, settings)


def test_save_settings_allows_continuous_media_with_zero_gap(tmp_path):
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="tsc",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=0,
        media_type="continuous",
    )

    save_settings(config_path, settings)
    loaded = load_settings(config_path)

    assert loaded.media_type == "continuous"
    assert loaded.gap_mm == 0


def test_validate_settings_reports_customer_ready_warnings():
    settings = PrinterSettings(
        brand="tsc",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9101,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=0,
        media_type="continuous",
    )

    report = validate_settings(settings)

    assert report.ok
    assert any("9100" in warning for warning in report.warnings)


def test_save_settings_keeps_release_approved_sewoo_zpl_brand_with_tear_off(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "APPROVED_SEWOO_ZPL_MODELS", frozenset({"SW-TEST-VERIFIED"}))
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="sewoo",
        model="SW-TEST-VERIFIED",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=3,
        media_handling="tear_off",
    )

    save_settings(config_path, settings)
    loaded = load_settings(config_path)

    assert loaded.brand == "sewoo"
    assert loaded.model == "SW-TEST-VERIFIED"
    assert loaded.media_handling == "tear_off"
    assert loaded.one_d_wide == 2


def test_save_settings_rejects_unapproved_sewoo_model(tmp_path):
    settings = PrinterSettings(
        brand="sewoo",
        model="UNVERIFIED-MODEL",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=3,
    )

    with pytest.raises(ValueError, match="PRODUCT_PACKAGES.md"):
        save_settings(tmp_path / "config.ini", settings)


@pytest.mark.parametrize("media_handling", ["cutter", "peeler"])
def test_save_settings_rejects_sewoo_postprocessing_even_for_approved_model(
    tmp_path, monkeypatch, media_handling
):
    monkeypatch.setattr(config_module, "APPROVED_SEWOO_ZPL_MODELS", frozenset({"SW-TEST-VERIFIED"}))
    settings = PrinterSettings(
        brand="sewoo",
        model="SW-TEST-VERIFIED",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=3,
        media_handling=media_handling,
    )

    with pytest.raises(ValueError, match="뜯어내기만"):
        save_settings(tmp_path / "config.ini", settings)


def test_settings_ui_contains_media_type_control():
    source = inspect.getsource(SettingsApp._build_label_section)

    assert "용지 유형" in source
    assert "MEDIA_TYPE_VALUES" in source


def test_settings_ui_contains_pre_save_validation_panel():
    source = inspect.getsource(SettingsApp._build_validation_section)

    assert "저장 전 점검" in source
    assert "설정 점검" in source


def test_settings_ui_uses_ribbon_workbench_and_validation_side_panel():
    source = inspect.getsource(SettingsApp._build_ui)

    assert "Ribbon.TFrame" in source
    assert "self._build_settings_flow(flow_inner)" in source
    assert "self._build_validation_section(validation_inner, 0)" in source
    assert "설정 저장" in source


def test_settings_ui_renames_media_handling_to_print_afterwork():
    source = inspect.getsource(SettingsApp._build_printer_section)

    assert "인쇄후작업" in source
    assert "배출 옵션" not in source


def test_settings_ui_hides_model_name_and_keeps_brand_postprocessing_guardrails():
    printer_source = inspect.getsource(SettingsApp._build_printer_section)
    sync_source = inspect.getsource(SettingsApp._sync_media_handling_state)

    assert r"\ubaa8\ub378\uba85" not in printer_source
    assert "model_var" not in printer_source
    assert "<<ComboboxSelected>>" in printer_source
    assert 'button.pack_forget()' in sync_source
    assert 'button.configure(state="normal")' in sync_source


def test_settings_ui_includes_whole_label_180_degree_orientation_control():
    source = inspect.getsource(SettingsApp._build_printer_section)

    assert "print_orientation_var" in source
    assert "PRINT_ORIENTATION_VALUES" in source
    assert "180도 회전" in inspect.getsource(__import__("barcode_label_automation.settings_app", fromlist=["PRINT_ORIENTATION_LABELS"]))


def test_save_settings_rejects_bixolon_peeler_until_slcs_command_is_confirmed(tmp_path):
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="bixolon",
        mode="network",
        print_method="direct_thermal",
        ip="192.168.0.88",
        port=9100,
        windows_printer_name="auto",
        width_mm=60,
        height_mm=40,
        dpi=203,
        gap_mm=3,
        media_handling="peeler",
    )

    with pytest.raises(ValueError, match="BIXOLON/SLCS 필러"):
        save_settings(config_path, settings)


def test_save_settings_rejects_missing_usb_printer_name(tmp_path):
    config_path = tmp_path / "config.ini"
    settings = PrinterSettings(
        brand="tsc",
        mode="windows_raw",
        print_method="direct_thermal",
        ip="",
        port=9100,
        windows_printer_name="auto",
        width_mm=50,
        height_mm=30,
        dpi=203,
        gap_mm=3,
    )

    try:
        save_settings(config_path, settings)
    except ValueError as exc:
        assert "Windows 프린터 이름" in str(exc)
    else:
        raise AssertionError("missing USB printer name should be rejected")


def test_settings_app_smoke_accepts_base_dir_argument(tmp_path):
    config_path = tmp_path / "config.ini"
    save_settings(
        config_path,
        PrinterSettings(
            brand="tsc",
            mode="network",
            print_method="direct_thermal",
            ip="192.168.0.88",
            port=9100,
            windows_printer_name="auto",
            width_mm=50,
            height_mm=30,
            dpi=203,
            gap_mm=3,
        ),
    )

    assert main(["--base-dir", str(tmp_path), "--smoke-test"]) == 0


def test_settings_ui_explains_auto_barcode_layout_locked_fields():
    source = inspect.getsource(SettingsApp._build_barcode_section)

    assert "자동 배치가 켜져 있으면 X/Y" in source


def test_settings_ui_protects_unsaved_changes_before_reload_or_close():
    source = inspect.getsource(SettingsApp)

    assert "_install_dirty_tracking" in source
    assert "WM_DELETE_WINDOW" in source
    assert "저장하지 않은 변경사항" in source
    assert "confirm_discard" in str(inspect.signature(SettingsApp.load_from_file))


def test_settings_secondary_action_uses_the_existing_validation_handler():
    source = inspect.getsource(SettingsApp._build_buttons)

    assert "command=self.validate_current_settings" in source
    assert "_validate_only" not in source


def test_settings_suite_menu_has_only_supported_file_tools_help_actions():
    source = inspect.getsource(SettingsApp._build_menu_surface)
    positions = [source.index(f'("{name}",') for name in ("파일", "도구", "도움말")]
    assert positions == sorted(positions)
    assert '("보기",' not in source
    assert '"인쇄"' not in source
    actions = inspect.getsource(SettingsApp._build_buttons)
    assert actions.count("ttk.Button(") == 4
    assert all(command in actions for command in ("self.load_from_file", "self.check_connection",
                                                 "self.validate_current_settings", "self.save_to_file"))


def test_settings_saved_state_header_tracks_changes():
    app = SettingsApp.__new__(SettingsApp)
    app._base_title = "채움랩 프린터 설정"
    titles = []
    states = []
    app.title = titles.append
    app.document_state_var = SimpleNamespace(set=states.append)
    app._set_settings_dirty(True)
    app._set_settings_dirty(False)
    assert titles == ["채움랩 프린터 설정 *", "채움랩 프린터 설정"]
    assert states == ["변경사항 있음 · 저장 필요", "저장됨"]
    assert not app._settings_dirty


def test_dirty_tracking_covers_every_saved_printer_and_barcode_field():
    app = SettingsApp.__new__(SettingsApp)
    names = (
        "brand", "mode", "print_method", "print_orientation", "media_handling", "print_speed",
        "print_density", "ip", "port", "printer_name", "width", "height", "dpi", "gap", "media_type",
        "barcode_type", "barcode_auto_layout", "barcode_x", "barcode_y", "barcode_rotation", "one_d_height",
        "one_d_narrow", "one_d_wide", "one_d_human_readable", "qr_model", "qr_ecc", "qr_cell_size",
        "datamatrix_cell_size", "pdf417_rows", "pdf417_columns", "pdf417_security", "pdf417_module_width",
        "pdf417_module_height",
    )
    variables = []
    for name in names:
        variable = object()
        setattr(app, f"{name}_var", variable)
        variables.append(variable)
    assert app._settings_variables() == tuple(variables)


@pytest.mark.parametrize("brand,supported", [("bixolon", {"tear_off", "cutter"}),
                                             ("tsc", {"tear_off", "cutter", "peeler"}),
                                             ("sewoo", {"tear_off"})])
def test_unsupported_manufacturer_postprocessing_is_hidden_and_current_value_safe(brand, supported):
    from barcode_label_automation.settings_app import BRAND_LABELS, MEDIA_HANDLING_LABELS
    app = SettingsApp.__new__(SettingsApp)
    app.brand_var = SimpleNamespace(get=lambda: BRAND_LABELS[brand])
    handling = {"value": MEDIA_HANDLING_LABELS["peeler"]}
    app.media_handling_var = SimpleNamespace(get=lambda: handling["value"], set=lambda value: handling.update(value=value))
    visibility = {}
    app.media_handling_buttons = {}
    for value in ("tear_off", "cutter", "peeler"):
        app.media_handling_buttons[value] = SimpleNamespace(
            configure=lambda **kwargs: None,
            pack=lambda _value=value, **kwargs: visibility.update({_value: True}),
            pack_forget=lambda _value=value: visibility.update({_value: False}),
        )
    app._sync_media_handling_state()
    assert {value for value, shown in visibility.items() if shown} == supported
    assert handling["value"] == MEDIA_HANDLING_LABELS["peeler" if "peeler" in supported else "tear_off"]


def test_settings_help_prefers_new_brand_manual_and_retains_legacy_fallback(monkeypatch, tmp_path):
    import barcode_label_automation.settings_app as module
    app = SettingsApp.__new__(SettingsApp)
    app.base_dir = app.install_dir = tmp_path
    folder = tmp_path / "고객용_매뉴얼"
    folder.mkdir()
    legacy = folder / "채움LAB_프린터설정_고객용_매뉴얼.pdf"
    current = folder / "채움랩_프린터설정_고객용_매뉴얼.pdf"
    legacy.write_bytes(b"old")
    current.write_bytes(b"new")
    opened = []
    monkeypatch.setattr(module.os, "startfile", opened.append)
    app.open_manual()
    assert opened == [current]
    current.unlink()
    app.open_manual()
    assert opened[-1] == legacy
