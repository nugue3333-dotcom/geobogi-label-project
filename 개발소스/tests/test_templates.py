from __future__ import annotations

from barcode_label_automation.config import BarcodeConfig
from barcode_label_automation.excel_reader import LabelRow
from barcode_label_automation.templates import render_label, render_slcs, render_tspl, render_zpl


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
    assert "T154,50,b,1,1,0,0,N,N,'ITEM: SENSOR BRACKET'" in command
    assert "T202,84,c,1,1,0,0,N,N,'CODE: A1001'" in command
    assert "B162,113,1,2,6,83,0,1,'A1001-250531'" in command
    assert "T154,242,c,1,1,0,0,N,N,'LOT: LOT250531 / QTY: 100'" in command
    assert command.endswith("P1\n")


def test_render_tspl_uses_tsc_template():
    command = render_tspl(ROW, 50, 30, 203, 3)

    assert command.startswith(b"SIZE 50 mm,30 mm\nGAP 3 mm,0 mm\nCODEPAGE UTF-8\n")
    assert b"DENSITY 8\nSPEED 4\n" in command
    assert b"SET RIBBON OFF\n" in command
    assert b"SET CUTTER OFF\nSET PEEL OFF\nSET TEAR ON\n" in command
    assert command.count(b"BITMAP ") == 3
    assert b'TEXT 30,30,"3"' not in command
    assert b'BARCODE 24,76,"128",80,1,0,2,4,"A1001-250531"' in command
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

    assert command.startswith("^XA\n^CI28\n^MTD\n^MMT\n^PR4\n^MD10\n^PW400\n^LL240\n")
    assert "^FO24,24^FB352,1,0,C,0^A0N,20,20^FDITEM: SENSOR BRACKET^FS" in command
    assert "^FO24,76^BY2,2,80^BCN,80,Y,N,N^FDA1001-250531^FS" in command
    assert command.endswith("^PQ1\n^XZ\n")


def test_render_label_accepts_supported_printer_languages():
    assert render_label("slcs", ROW, 60, 40, 203).startswith("CB\n")
    assert render_label("tspl", ROW, 50, 30, 203).startswith(b"SIZE 50 mm,30 mm\n")
    assert render_label("zpl", ROW, 50, 30, 203).startswith("^XA\n")


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


def test_render_label_applies_media_handling_options():
    assert "CUTy\n" in render_label("slcs", ROW, 60, 40, 203, media_handling="cutter")
    assert b"SET CUTTER 1\nSET PEEL OFF\nSET TEAR OFF\n" in render_label("tspl", ROW, 50, 30, 203, media_handling="cutter")
    assert "^MMC\n" in render_label("zpl", ROW, 50, 30, 203, media_handling="cutter")

    assert "CUTn\n" in render_label("slcs", ROW, 60, 40, 203, media_handling="peeler")
    assert b"SET CUTTER OFF\nSET PEEL ON\nSET TEAR OFF\n" in render_label("tspl", ROW, 50, 30, 203, media_handling="peeler")
    assert "^MMP\n" in render_label("zpl", ROW, 50, 30, 203, media_handling="peeler")


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
