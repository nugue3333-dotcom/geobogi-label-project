from __future__ import annotations

from barcode_label_automation.settings_app import PrinterSettings, load_settings, save_settings


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
