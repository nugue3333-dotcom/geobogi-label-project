from __future__ import annotations

import pytest

from barcode_label_automation.config import load_config
from barcode_label_automation.errors import ConfigError


def write_config(tmp_path, brand: str, language: str = "auto"):
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        f"""
[printer]
brand = {brand}
mode = network
print_method = direct_thermal
speed = auto
density = auto
language = {language}
ip = 127.0.0.1
port = 9100
windows_printer_name = auto
command_encoding = auto

[brand.bixolon]
language = slcs
command_encoding = cp949
windows_printer_name = BIXOLON Label Printer

[brand.tsc]
language = tspl
command_encoding = utf-8
windows_printer_name = TSC Label Printer

[brand.zebra]
language = zpl
command_encoding = utf-8
windows_printer_name = ZDesigner Label Printer

[label]
width_mm = 50
height_mm = 30
dpi = 203
gap_mm = 3

[data]
excel_file = print_queue.xlsx
output_dir = out
""".strip(),
        encoding="utf-8",
    )
    return config_path


@pytest.mark.parametrize(
    ("brand", "language", "printer_name"),
    [
        ("bixolon", "slcs", "BIXOLON Label Printer"),
        ("tsc", "tspl", "TSC Label Printer"),
        ("zebra", "zpl", "ZDesigner Label Printer"),
    ],
)
def test_brand_selects_matching_language_and_printer_name(tmp_path, brand, language, printer_name):
    config = load_config(write_config(tmp_path, brand))

    assert config.printer.brand == brand
    assert config.printer.print_method == "direct_thermal"
    assert config.printer.media_handling == "tear_off"
    assert config.printer.print_speed > 0
    assert config.printer.print_density >= 0
    assert config.printer.language == language
    assert config.printer.windows_printer_name == printer_name


@pytest.mark.parametrize(
    ("brand", "encoding"),
    [
        ("bixolon", "cp949"),
        ("tsc", "utf-8"),
        ("zebra", "utf-8"),
    ],
)
def test_brand_selects_matching_command_encoding(tmp_path, brand, encoding):
    config = load_config(write_config(tmp_path, brand))

    assert config.printer.command_encoding == encoding


def test_brand_rejects_mismatched_language(tmp_path):
    with pytest.raises(ConfigError, match="brand 'tsc'"):
        load_config(write_config(tmp_path, "tsc", "zpl"))


def test_config_allows_utf8_bom(tmp_path):
    config_path = write_config(tmp_path, "zebra")
    config_path.write_bytes(b"\xef\xbb\xbf" + config_path.read_bytes())

    config = load_config(config_path)

    assert config.printer.language == "zpl"


def test_config_reads_thermal_transfer_print_method(tmp_path):
    config_path = write_config(tmp_path, "bixolon")
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(text.replace("print_method = direct_thermal", "print_method = thermal_transfer"), encoding="utf-8")

    config = load_config(config_path)

    assert config.printer.print_method == "thermal_transfer"


def test_config_reads_media_handling_option(tmp_path):
    config_path = write_config(tmp_path, "tsc")
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(text.replace("print_method = direct_thermal", "print_method = direct_thermal\nmedia_handling = cutter"), encoding="utf-8")

    config = load_config(config_path)

    assert config.printer.media_handling == "cutter"


def test_config_rejects_unknown_media_handling_option(tmp_path):
    config_path = write_config(tmp_path, "zebra")
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(text.replace("print_method = direct_thermal", "print_method = direct_thermal\nmedia_handling = rewind"), encoding="utf-8")

    with pytest.raises(ConfigError, match="printer.media_handling"):
        load_config(config_path)


def test_config_reads_print_speed_and_density(tmp_path):
    config_path = write_config(tmp_path, "tsc")
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace("speed = auto", "speed = 5").replace("density = auto", "density = 12"),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.printer.print_speed == 5
    assert config.printer.print_density == 12


def test_config_reads_barcode_options(tmp_path):
    config_path = write_config(tmp_path, "tsc")
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + """

[barcode]
type = qr
auto_layout = no
x = 120
y = 90
rotation = 90

[barcode.1d]
height = 70
narrow = 2
wide = 3
human_readable = no

[barcode.qr]
model = 2
ecc = Q
cell_size = 5

[barcode.datamatrix]
cell_size = 6

[barcode.pdf417]
rows = 20
columns = 4
security_level = 3
module_width = 4
module_height = 12
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.barcode.barcode_type == "qr"
    assert config.barcode.auto_layout is False
    assert config.barcode.x == 120
    assert config.barcode.y == 90
    assert config.barcode.rotation == 90
    assert config.barcode.one_d_wide == 3
    assert config.barcode.one_d_human_readable is False
    assert config.barcode.qr_ecc == "Q"
    assert config.barcode.qr_cell_size == 5


def test_config_auto_1d_wide_tracks_printer_language(tmp_path):
    assert load_config(write_config(tmp_path, "bixolon")).barcode.one_d_wide == 6
    assert load_config(write_config(tmp_path, "tsc")).barcode.one_d_wide == 2
    assert load_config(write_config(tmp_path, "zebra")).barcode.one_d_wide == 2
