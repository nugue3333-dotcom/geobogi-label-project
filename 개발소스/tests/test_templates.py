from __future__ import annotations

import pytest
from openpyxl import Workbook

from barcode_label_automation.config import BarcodeConfig
from barcode_label_automation.excel_reader import LabelRow, read_labels
from barcode_label_automation.templates import (
    _auto_label_layout,
    _max_text_lines,
    default_barcode_config,
    mm_to_dots,
    print_orientation_command,
    render_label,
    render_slcs,
    render_tspl,
    render_zpl,
)


ROW = LabelRow(
    item_code="A1001",
    item_name="SENSOR BRACKET",
    barcode="A1001-250531",
    lot_no="LOT250531",
    qty=100,
    print_qty=1,
)


def test_render_slcs_uses_bixolon_60x40mm_template():
    command = render_slcs(ROW)

    assert command.startswith("CB\nSS3\nSD20\nCS13,0\nSTd\nCUTn\nSW480\nSL320,24,G\nSOT\n")
    assert "ITEM:" not in command
    assert "CODE:" not in command
    assert "T24," in command
    assert command.count("\nT") == 4
    assert "B162," in command
    assert command.endswith("P1\n")


def test_render_tspl_uses_tsc_template():
    command = render_tspl(ROW, 50, 30, 203, 3)

    assert command.startswith(b"SIZE 50 mm,30 mm\nGAP 3 mm,0 mm\nCODEPAGE UTF-8\n")
    assert b"DENSITY 8\nSPEED 4\n" in command
    assert b"SET RIBBON OFF\n" in command
    assert b"SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n" in command
    assert command.count(b"BITMAP ") == 3
    assert b'TEXT 30,30,"3"' not in command
    assert b'BARCODE 22,' in command
    assert command.endswith(b"PRINT 1,1\n")


def test_render_tspl_bitmap_uses_white_background_black_text():
    command = render_tspl(ROW, 50, 30, 203, 3)
    first_bitmap = command.split(b"BITMAP ", 1)[1]
    fields = first_bitmap.split(b",", 5)
    width_bytes = int(fields[2])
    height = int(fields[3])
    mode = fields[4]
    payload = fields[5][: width_bytes * height]

    assert mode == b"0"
    assert payload[0] == 0xFF
    assert any(byte != 0xFF for byte in payload)


def test_render_tspl_can_still_use_korean_codepage_949_when_requested():
    command = render_tspl(ROW, 50, 30, 203, 3, command_encoding="cp949")

    assert command.startswith(b"SIZE 50 mm,30 mm\nGAP 3 mm,0 mm\nCODEPAGE 949\n")


def test_render_zpl_uses_zebra_template():
    command = render_zpl(ROW, 50, 30, 203, 3)

    assert command.startswith("^XA\n^CI28\n^PON\n^MTD\n^MMT\n^MNY\n^PR4\n^MD10\n^PW400\n^LL240\n")
    assert "ITEM:" not in command
    assert "CODE:" not in command
    assert "^FO20," in command
    assert "^BY2,2," in command
    assert "^FDA1001-250531^FS" in command
    assert command.endswith("^PQ1\n^XZ\n")


def test_render_label_accepts_supported_printer_languages():
    assert render_label("slcs", ROW, 60, 40, 203).startswith("CB\n")
    assert render_label("tspl", ROW, 50, 30, 203).startswith(b"SIZE 50 mm,30 mm\n")
    assert render_label("zpl", ROW, 50, 30, 203).startswith("^XA\n")


@pytest.mark.parametrize(
    ("language", "print_orientation", "expected"),
    [
        ("slcs", "normal", "SOT\n"),
        ("slcs", "rotate_180", "SOB\n"),
        ("tspl", "normal", "DIRECTION 1\n"),
        ("tspl", "rotate_180", "DIRECTION 0\n"),
        ("zpl", "normal", "^PON\n"),
        ("zpl", "rotate_180", "^POI\n"),
    ],
)
def test_print_orientation_uses_documented_whole_label_commands(language, print_orientation, expected):
    assert print_orientation_command(language, print_orientation) == expected
    command = render_label(
        language,
        ROW,
        60 if language == "slcs" else 50,
        40 if language == "slcs" else 30,
        203,
        print_orientation=print_orientation,
    )
    encoded_expected = expected.encode("ascii") if isinstance(command, bytes) else expected
    assert encoded_expected in command


def test_print_orientation_rejects_unknown_value():
    with pytest.raises(ValueError, match="print_orientation"):
        print_orientation_command("tspl", "sideways")


def test_render_label_applies_thermal_transfer_print_method():
    assert "STt\n" in render_label("slcs", ROW, 60, 40, 203, print_method="thermal_transfer")
    assert b"SET RIBBON ON\n" in render_label("tspl", ROW, 50, 30, 203, print_method="thermal_transfer")
    assert "^MTT\n" in render_label("zpl", ROW, 50, 30, 203, print_method="thermal_transfer")


def test_render_label_applies_print_speed_and_density_without_reverse_commands():
    slcs = render_label("slcs", ROW, 60, 40, 203, print_speed=5, print_density=18)
    tspl = render_label("tspl", ROW, 50, 30, 203, print_speed=6, print_density=10)
    zpl = render_label("zpl", ROW, 50, 30, 203, print_speed=7, print_density=11)

    assert "SS5\nSD18\n" in slcs
    assert b"DENSITY 10\nSPEED 6\n" in tspl
    assert "^PR7\n^MD11\n" in zpl
    assert "REVERSE" not in slcs.upper()
    assert b"REVERSE" not in tspl.upper()


@pytest.mark.parametrize(
    ("language", "media_handling", "expected"),
    [
        ("slcs", "tear_off", "CUTn\n"),
        ("slcs", "cutter", "CUTy\n"),
        ("tspl", "tear_off", b"SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n"),
        ("tspl", "cutter", b"SET PEEL OFF\nSET CUTTER 1\n"),
        ("tspl", "peeler", b"SET CUTTER OFF\nSET PEEL ON\n"),
        ("zpl", "tear_off", "^MMT\n"),
        ("zpl", "cutter", "^MMC\n"),
        ("zpl", "peeler", "^MMP\n"),
    ],
)
def test_render_label_applies_supported_media_handling_commands(language, media_handling, expected):
    command = render_label(language, ROW, 60 if language == "slcs" else 50, 40 if language == "slcs" else 30, 203, media_handling=media_handling)

    assert expected in command


@pytest.mark.parametrize(
    ("language", "media_type", "expected"),
    [
        ("slcs", "gap", "SL320,24,G\n"),
        ("slcs", "black_mark", "SL320,24,B\n"),
        ("slcs", "continuous", "SL320,0,C\n"),
        ("tspl", "gap", b"GAP 3 mm,0 mm\n"),
        ("tspl", "black_mark", b"BLINE 3 mm,0 mm\n"),
        ("tspl", "continuous", b"GAP 0,0\n"),
        ("zpl", "gap", "^MNY\n"),
        ("zpl", "black_mark", "^MNM,0\n"),
        ("zpl", "continuous", "^MNN\n"),
    ],
)
def test_render_label_applies_supported_media_type_commands(language, media_type, expected):
    command = render_label(
        language,
        ROW,
        60 if language == "slcs" else 50,
        40 if language == "slcs" else 30,
        203,
        media_type=media_type,
    )

    assert expected in command


def test_render_label_rejects_unknown_media_type():
    with pytest.raises(ValueError, match="media_type"):
        render_label("tspl", ROW, 50, 30, 203, media_type="notch")


def test_render_label_rejects_slcs_peeler_until_command_is_confirmed():
    with pytest.raises(ValueError, match="BIXOLON/SLCS peeler"):
        render_label("slcs", ROW, 60, 40, 203, media_handling="peeler")


def test_tspl_peeler_command_is_sent_immediately_before_print():
    command = render_label("tspl", ROW, 50, 40, 203, media_handling="peeler")

    assert b"SET TEAR OFF\n" not in command
    assert command.rfind(b"SET PEEL ON\n") < command.rfind(b"PRINT 1,1\n")
    assert command.rfind(b"BARCODE ") < command.rfind(b"SET PEEL ON\n")


def test_tspl_40mm_label_uses_balanced_barcode_height():
    command = render_label("tspl", ROW, 50, 40, 203)

    assert b'BARCODE 22,' in command
    assert b'"128"' in command


def test_render_label_tspl_renders_korean_text_as_bitmap():
    row = LabelRow(
        item_code="K1001",
        item_name="한글품목테스트",
        barcode="KOR-TEST-001",
        lot_no="LOT-HANGUL",
        qty=10,
        print_qty=1,
    )

    command = render_label("tspl", row, 50, 30, 203, command_encoding="utf-8")

    assert isinstance(command, bytes)
    assert b"CODEPAGE UTF-8" in command
    assert command.count(b"BITMAP ") == 3
    assert b"TEXT " not in command
    assert "한글품목테스트".encode("utf-8") not in command


def test_render_label_uses_db_source_fields_as_left_aligned_text():
    row = LabelRow(
        item_code="10000",
        item_name="가나",
        barcode="123456789",
        lot_no="",
        qty=1,
        print_qty=1,
        source_fields=(("가격", "10000"), ("품명", "가나")),
    )

    slcs = render_slcs(row)
    tspl = render_tspl(row, 50, 30, 203, 3)
    zpl = render_zpl(row, 50, 30, 203, 3)

    assert "ITEM:" not in slcs
    assert "CODE:" not in slcs
    assert "10000" in slcs
    assert "T24," in slcs
    assert tspl.count(b"BITMAP ") == 2
    assert "^FB360,1,0,L,0" in zpl
    assert "가격: 10000" in zpl


def test_render_label_keeps_product_name_price_and_code_inside_label(tmp_path):
    path = tmp_path / "print_queue.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["item_code", "item_name", "barcode", "lot_no", "qty", "print_qty", "판매가"])
    sheet.append(["ACC-001", "미니 하트 귀걸이", "880100000001", "ACC-20260727-001", "10", "1", "₩4,600"])
    workbook.save(path)

    row = read_labels(path)[0]
    command = render_zpl(row, 50, 40, 203, 3)

    assert "상품명: 미니 하트 귀걸이" in command
    assert "판매가: 4,600원" in command
    assert "상품코드: ACC-001" in command
    assert command.count("^FB") == 3


@pytest.mark.parametrize("width_mm,height_mm", [(50, 30), (50, 40), (100, 100)])
def test_auto_layout_keeps_text_and_barcode_inside_configured_label(width_mm, height_mm):
    width_dot = mm_to_dots(width_mm, 203)
    height_dot = mm_to_dots(height_mm, 203)
    layout = _auto_label_layout(
        width_dot,
        height_dot,
        default_barcode_config(),
        "880100000001",
        text_line_count=3,
        max_text_chars=32,
    )

    assert layout["text_line_ys"][0] >= layout["margin_y"]
    assert layout["content_bottom"] <= layout["label_bottom"]


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize(
    ("width_mm", "height_mm"),
    [(20, 15), (30, 20), (40, 30), (50, 40), (80, 60), (100, 100), (120, 120), (200, 150), (300, 300)],
)
@pytest.mark.parametrize("language", ["tspl", "zpl", "slcs"])
def test_auto_layout_supports_configured_size_and_dpi_across_printer_languages(
    language,
    width_mm,
    height_mm,
    dpi,
):
    source_fields = (
        ("품목명", "테스트 상품"),
        ("판매가", "5,300원"),
        ("상품코드", "ACC-001"),
        ("원산지", "국내산"),
        ("분류", "악세사리"),
        ("색상", "골드"),
        ("규격", "소형"),
        ("비고", "샘플"),
    )
    line_count = _max_text_lines(height_mm)
    row = LabelRow(
        item_code="ACC-001",
        item_name="테스트 상품",
        barcode="880100000001",
        lot_no="",
        qty=1,
        print_qty=1,
        source_fields=source_fields[:line_count],
    )
    width_dot = mm_to_dots(width_mm, dpi)
    height_dot = mm_to_dots(height_mm, dpi)
    layout = _auto_label_layout(
        width_dot,
        height_dot,
        default_barcode_config(),
        row.barcode,
        text_line_count=line_count,
        max_text_chars=20,
        large_label=width_mm >= 80 and height_mm >= 80,
    )

    assert layout["content_bottom"] <= layout["label_bottom"]
    assert render_label(
        language,
        row,
        width_mm,
        height_mm,
        dpi,
        barcode_config=default_barcode_config(),
    )


def test_auto_layout_fills_a_100mm_square_label_without_centering_a_small_stack():
    width_dot = mm_to_dots(100, 203)
    height_dot = mm_to_dots(100, 203)
    layout = _auto_label_layout(
        width_dot,
        height_dot,
        default_barcode_config(),
        "880100000001",
        text_line_count=3,
        max_text_chars=24,
    )

    assert layout["text_line_ys"][0] == layout["margin_y"]
    assert layout["barcode_height"] >= round(height_dot * 0.35)
    assert layout["content_bottom"] < layout["label_bottom"]
    assert layout["label_bottom"] - layout["content_bottom"] <= round(height_dot * 0.08)


def test_bixolon_100mm_accessory_label_uses_the_printable_height() -> None:
    """Keep the live 100 x 100 mm BIXOLON layout from regressing to a small stack."""
    row = LabelRow(
        item_code="ACC-002",
        item_name="미니 하트 귀걸이",
        barcode="8801000000002",
        lot_no="",
        qty=1,
        print_qty=1,
        source_fields=(
            ("상품명", "미니 하트 귀걸이"),
            ("판매가", "5,300원"),
            ("상품코드", "ACC-002"),
        ),
    )

    command = render_slcs(
        row,
        width_mm=100,
        height_mm=100,
        dpi=203,
        gap_mm=3,
        print_method="direct_thermal",
        barcode_config=default_barcode_config(one_d_wide=6),
        print_speed=4,
        print_density=10,
        media_handling="cutter",
        media_type="black_mark",
    )

    assert "SW799\nSL799,24,B\n" in command
    assert "V40,32,K,42,68,0,N,N,N,0,L,0,'상품명: 미니 하트 귀걸이'" in command
    assert "V40,114,K,42,68,0,N,N,N,0,L,0,'판매가: 5,300원'" in command
    assert "V40,196,K,42,68,0,N,N,N,0,L,0,'상품코드: ACC-002'" in command
    assert "B1116,350,1,3,9,240,0,5,'8801000000002'" in command


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_40mm_label_renders_four_db_fields_independently_of_dpi(language, dpi):
    row = LabelRow(
        item_code="A100",
        item_name="센서",
        barcode="A100-LOT01",
        lot_no="LOT01",
        qty=12,
        print_qty=1,
        source_fields=(("품명", "센서"), ("코드", "A100"), ("LOT", "LOT01"), ("수량", "12")),
    )

    command = render_label(language, row, 50, 40, dpi)

    if language == "slcs":
        assert command.count("\nT") == 4
        assert all(value in command for value in ("센서", "A100", "LOT01", "12"))
    elif language == "tspl":
        assert command.count(b"BITMAP ") == 4
    else:
        assert command.count("^FB") == 4
        assert all(value in command for value in ("센서", "A100", "LOT01", "12"))


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_40mm_label_fits_five_nonempty_db_fields(language):
    row = LabelRow(
        item_code="A100",
        item_name="센서",
        barcode="A100-LOT01",
        lot_no="LOT01",
        qty=12,
        print_qty=1,
        source_fields=(("A", "1"), ("B", "2"), ("C", "3"), ("D", "4"), ("E", "5")),
    )

    command = render_label(language, row, 50, 40, 203)

    if language == "slcs":
        assert command.count("\nT") == 5
    elif language == "tspl":
        assert command.count(b"BITMAP ") == 5
    else:
        assert command.count("^FB") == 5


def test_render_label_uses_qr_barcode_config_for_2d():
    config = BarcodeConfig(
        barcode_type="qr",
        auto_layout=False,
        x=120,
        y=90,
        rotation=90,
        one_d_height=80,
        one_d_narrow=2,
        one_d_wide=2,
        one_d_human_readable=True,
        qr_model=2,
        qr_ecc="Q",
        qr_cell_size=5,
        datamatrix_cell_size=4,
        pdf417_rows=30,
        pdf417_columns=5,
        pdf417_security_level=2,
        pdf417_module_width=3,
        pdf417_module_height=10,
    )

    assert "B2120,90,Q,2,Q,5,1,'A1001-250531'" in render_label("slcs", ROW, 60, 40, 203, barcode_config=config)
    assert b'QRCODE 120,90,Q,5,A,90,M2,S7,"A1001-250531"' in render_label(
        "tspl", ROW, 60, 40, 203, barcode_config=config
    )
    assert "^FO120,90^BQR,2,5^FDLA,A1001-250531^FS" in render_label(
        "zpl", ROW, 60, 40, 203, barcode_config=config
    )
