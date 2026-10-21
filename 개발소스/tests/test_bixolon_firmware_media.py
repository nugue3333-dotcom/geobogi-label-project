"""Firmware settings survive rendering; these checks never use a printer."""
from configparser import ConfigParser
from dataclasses import replace

import pytest

from barcode_label_automation.config import DEFAULTS, load_config
from barcode_label_automation.errors import ConfigError
from barcode_label_automation.excel_reader import LabelRow
from barcode_label_automation.label_designer_app import normalize_template
from barcode_label_automation.label_media import write_config_atomic
from barcode_label_automation.settings_app import load_settings, save_settings
from barcode_label_automation.template_output import render_command
from barcode_label_automation.templates import render_label


def configuration(tmp_path, handling="printer_default", distance="auto"):
    parser = ConfigParser(interpolation=None)
    parser.read_dict(DEFAULTS)
    for section, key, value in (
        ("printer", "brand", "bixolon"), ("printer", "mode", "network"),
        ("printer", "media_handling", handling),
        ("label", "width_mm", "60"), ("label", "height_mm", "150"),
        ("label", "media_type", "black_mark"),
        ("label", "gap_offset_mm", distance), ("label", "feed_offset_mm", "auto"),
        ("label", "offsets_profile", "bixolon"),
    ):
        parser.set(section, key, value)
    path = tmp_path / "config.ini"
    write_config_atomic(path, parser)
    return path


def output_pair(tmp_path, config, copies):
    row = LabelRow("001", "TEST", "001234567890", "LOT", 1, copies)
    auto = render_label(
        "slcs", row, 60, 150, config.label.dpi, 3,
        media_handling=config.printer.media_handling, media_type="black_mark",
        gap_offset_mm=config.label.gap_offset_mm, feed_offset_mm=config.label.feed_offset_mm,
        offset_x_mm=config.label.offset_x_mm,
        bixolon_extended_stop=config.label.bixolon_extended_stop,
    )
    template = normalize_template({"label": {"width_mm": 60, "height_mm": 150},
        "elements": [{"id": "text", "type": "text", "text": "TEST", "x": 3,
                      "y": 3, "width": 20, "height": 5, "font_size": 9}]})
    saved = render_command(template, {}, config, tmp_path, copies)
    return [(value.encode("cp949") if isinstance(value, str) else value).replace(b"\r\n", b"\n")
            for value in (auto, saved)]


@pytest.mark.parametrize("copies", [1, 3])
@pytest.mark.parametrize("offset", [0, 1.25])
def test_firmware_mode_omits_all_cutter_sensor_and_stop_overrides(tmp_path, copies, offset):
    path = configuration(tmp_path)
    settings = load_settings(path)
    save_settings(path, settings)
    config = load_config(path)
    assert config.printer.media_handling == "printer_default"
    config = replace(config, label=replace(config.label, offset_x_mm=offset))
    for payload in output_pair(tmp_path, config, copies):
        header = payload.split(b"BMP", 1)[0]
        assert not any(line.startswith((b"CUT", b"SL", b"SF", b"SA", b"TA"))
                       for line in header.splitlines())
        assert payload.endswith(f"P{copies}\n".encode())


@pytest.mark.parametrize("distance", [0, 1, -1, 2])
@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_standard_sensor_offset_reaches_auto_and_saved_output(tmp_path, distance, dpi):
    config = load_config(configuration(tmp_path, "cutter", str(distance)))
    config = replace(config, label=replace(config.label, dpi=dpi))
    for payload in output_pair(tmp_path, config, 1):
        expected = round(distance * dpi / 25.4)
        header = payload.split(b"BMP", 1)[0]
        assert f",B,{expected}\n".encode() in header
        assert b"CUTy\n" in header
        assert not any(line.startswith(b"TA") for line in header.splitlines())


@pytest.mark.parametrize("distance", ["0", "30"])
def test_firmware_mode_rejects_conflicting_explicit_distance(tmp_path, distance):
    path = configuration(tmp_path, distance=distance)
    with pytest.raises(ConfigError, match="본체"):
        load_config(path)
    with pytest.raises(ValueError, match="본체"):
        save_settings(path, load_settings(path))


@pytest.mark.parametrize("stop", [-20, 20])
@pytest.mark.parametrize("extended", [False, True])
def test_removed_custom_extension_cannot_bypass_standard_limit(tmp_path, stop, extended):
    path = configuration(tmp_path, "cutter")
    with pytest.raises(ValueError):
        save_settings(path, replace(load_settings(path), feed_offset_mm=stop,
                                  bixolon_extended_stop=extended))


@pytest.mark.parametrize("dpi,limit", [(203,12), (300,8.4), (600,4.2)])
@pytest.mark.parametrize("field", ["gap_offset_mm", "feed_offset_mm"])
@pytest.mark.parametrize("sign", [-1, 1])
def test_standard_limits_save_render_and_reject_overflow(tmp_path, dpi, limit, field, sign):
    path = configuration(tmp_path, "cutter")
    settings = replace(load_settings(path), dpi=dpi, **{field: sign*limit})
    save_settings(path, settings)
    config = load_config(path)
    for payload in output_pair(tmp_path, config, 1):
        expected = round(sign*limit*dpi/25.4)
        header = payload.split(b"BMP",1)[0]
        assert (f"TA{expected}\n".encode() if field == "feed_offset_mm" else f",B,{expected}\n".encode()) in header
    before = path.read_bytes()
    with pytest.raises(ValueError, match="범위"):
        save_settings(path, replace(settings, **{field: sign*(limit+0.1)}))
    assert path.read_bytes() == before
