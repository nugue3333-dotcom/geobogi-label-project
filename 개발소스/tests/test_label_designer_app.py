from __future__ import annotations

import inspect
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image, ImageChops

from barcode_label_automation.label_designer_app import (
    BARCODE_1D_BITMAP_TYPES,
    BARCODE_2D_BITMAP_TYPES,
    BARCODE_TYPES,
    DESIGNER_PRINT_SUPPORTED_BARCODE_TYPES,
    LABEL_FILE_EXTENSION,
    LABEL_FILE_TYPES,
    LabelDesignerApp,
    _element,
    load_template_file,
    main,
    _render_1d_barcode_image,
    _render_2d_barcode_image,
    _render_qr_code_image,
    default_template,
    normalize_template,
    render_template_text,
)
from barcode_label_automation.templates import mm_to_dots


def test_render_template_text_replaces_db_fields():
    row = {"item_name": "SENSOR BRACKET", "barcode": "88023502", "qty": "100"}

    assert render_template_text("ITEM: {{item_name}} / {{barcode}} / {{qty}}", row) == "ITEM: SENSOR BRACKET / 88023502 / 100"


def test_default_template_starts_blank():
    template = default_template(50, 40)

    assert template["label"] == {"width_mm": 50, "height_mm": 40}
    assert template["elements"] == []


def test_saved_label_file_extension_is_primary_template_format():
    assert LABEL_FILE_EXTENSION == ".gblabel"
    assert LABEL_FILE_TYPES[0] == ("거복이 라벨 파일", "*.gblabel")


def test_saved_label_file_loads_like_template(tmp_path):
    label_file = tmp_path / "shipping_label.gblabel"
    label_file.write_text(json.dumps(default_template(60, 35), ensure_ascii=False), encoding="utf-8")

    template = load_template_file(label_file)

    assert template["label"] == {"width_mm": 60, "height_mm": 35}


def test_main_smoke_test_accepts_saved_label_file(tmp_path):
    label_file = tmp_path / "product_label.gblabel"
    label_file.write_text(json.dumps(default_template(70, 40), ensure_ascii=False), encoding="utf-8")

    assert main(["--base-dir", str(tmp_path), "--smoke-test", str(label_file)]) == 0


def test_normalize_template_keeps_known_element_values():
    template = normalize_template(
        {
            "label": {"width_mm": "60", "height_mm": "45"},
            "elements": [{"type": "field", "text": "{{lot_no}}", "x": "3", "y": "4", "width": "20", "height": "5"}],
        }
    )

    assert template["label"] == {"width_mm": 60, "height_mm": 45}
    assert template["elements"][0]["type"] == "field"
    assert template["elements"][0]["x"] == 3.0


def test_normalize_template_keeps_barcode_type():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [{"type": "barcode", "text": "12345", "barcode_type": "datamatrix"}],
        }
    )

    assert template["elements"][0]["type"] == "barcode"
    assert template["elements"][0]["barcode_type"] == "datamatrix"


def test_normalize_template_keeps_table_shape_and_reverse_text():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [
                {"type": "table", "table_rows": "4", "table_cols": "2"},
                {"type": "text", "text": "A", "reverse": True},
            ],
        }
    )

    assert template["elements"][0]["type"] == "table"
    assert template["elements"][0]["table_rows"] == 4
    assert template["elements"][0]["table_cols"] == 2
    assert template["elements"][0]["arrange"] == "behind"
    assert template["elements"][1]["reverse"] is True


def test_normalize_template_keeps_image_path_and_arrange_mode():
    template = normalize_template(
        {
            "label": {"width_mm": 50, "height_mm": 40},
            "elements": [{"type": "image", "image_path": "assets/images/sample.jpg", "arrange": "front"}],
        }
    )

    assert template["elements"][0]["type"] == "image"
    assert template["elements"][0]["image_path"] == "assets/images/sample.jpg"
    assert template["elements"][0]["arrange"] == "front"


def test_barcode_type_list_has_1d_and_2d_choices():
    assert "Code 128" in BARCODE_TYPES.values()
    assert "Aztec" in BARCODE_TYPES.values()
    assert "DataMatrix" in BARCODE_TYPES.values()
    assert "MaxiCode" in BARCODE_TYPES.values()
    assert "Micro QR" in BARCODE_TYPES.values()
    assert "MicroPDF417" in BARCODE_TYPES.values()
    assert "PDF417" in BARCODE_TYPES.values()
    assert "QR" in BARCODE_TYPES.values()


def test_new_basic_barcode_object_is_not_db_connected_by_default():
    element = _element("barcode", "12345678", 7, 14, 36, 12)

    assert element["field"] == ""
    assert element["text"] == "12345678"
    assert element["font_name"] == "Malgun Gothic"


def test_designer_visible_copy_keeps_db_ui_minimal_until_connection():
    source = "\n".join(
        inspect.getsource(method)
        for method in (
            LabelDesignerApp._build_menu,
            LabelDesignerApp._build_ui,
            LabelDesignerApp._build_tool_panel,
            LabelDesignerApp._build_canvas_toolbar,
            LabelDesignerApp._build_property_panel,
            LabelDesignerApp.refresh_data_panel,
            LabelDesignerApp.reload_db,
        )
    )

    assert "add_cascade" not in inspect.getsource(LabelDesignerApp._build_menu)
    assert "DB 필드" not in source
    assert "DB 값" not in source
    assert "데이터 필드" not in source
    assert "필드 삽입" not in source
    assert "라벨디자이너 Pro" not in source
    assert "데이터 원본 연결" not in source
    assert "DB 연결" in source
    assert "DB 해제" in source
    tool_source = inspect.getsource(LabelDesignerApp._build_tool_panel)
    assert "삭제" not in tool_source
    assert "앞으로" not in tool_source
    assert "뒤로" not in tool_source
    assert "미리보기" not in tool_source
    assert "그림" in source


def test_tool_panel_separator_uses_dynamic_tool_row_count():
    source = inspect.getsource(LabelDesignerApp._build_tool_panel)

    assert "tool_rows = (len(tools) + 1) // 2" in source
    assert "row += 3" not in source


def test_designer_table_behind_does_not_block_text_selection():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.origin_x = 0
    app.origin_y = 0
    app.scale = 10
    table = _element("table", "", 0, 0, 50, 30)
    text = _element("text", "A", 10, 10, 10, 5)
    app.elements = [text, table]

    selected = app.find_element_at(105, 105)

    assert selected is text


def test_designer_data_panel_is_hidden_until_db_connection():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app._refreshing_data_panel = False
    app.data_source_path = None
    app.data_card = _FakeCard()
    app.data_tree = None
    app.queue_tree = None
    app.db_rows = []
    app.selected_data_indexes = set()
    app.preview_row = {}
    app.data_source_label_var = SimpleNamespace(set=lambda _value: None)
    app.record_count_var = SimpleNamespace(set=lambda _value: None)
    app.queue_status_var = SimpleNamespace(set=lambda _value: None)

    app.refresh_data_panel()

    assert app.data_card.removed == 1
    assert app.data_card.shown == 0


def test_designer_data_panel_shows_after_db_connection(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app._refreshing_data_panel = False
    app.base_dir = tmp_path
    app.data_source_path = tmp_path / "barcode_db.xlsx"
    app.data_card = _FakeCard()
    app.data_tree = None
    app.queue_tree = None
    app.db_rows = []
    app.selected_data_indexes = set()
    app.preview_row = {}
    app.data_source_label_var = SimpleNamespace(set=lambda _value: None)
    app.record_count_var = SimpleNamespace(set=lambda _value: None)
    app.queue_status_var = SimpleNamespace(set=lambda _value: None)

    app.refresh_data_panel()

    assert app.data_card.shown == 1
    assert app.data_card.removed == 0


def test_designer_output_row_uses_selected_data_and_preserves_leading_zeroes():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.preview_row = {}
    source_row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "001234567890",
        "lot_no": "LOT250532",
        "qty": "010",
        "print_qty": "3",
    }

    row = app._output_test_row(7, source_row=source_row)

    assert row["barcode"] == "001234567890"
    assert row["qty"] == "010"
    assert row["print_qty"] == "7"


def test_designer_selected_data_rows_follow_selected_indexes():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.preview_row = {"barcode": "fallback"}
    app.db_rows = [{"barcode": "002"}, {"barcode": "001"}, {"barcode": "003"}]
    app.selected_data_indexes = {2, 0}

    rows = app.selected_data_rows()

    assert [row["barcode"] for row in rows] == ["002", "003"]


def test_designer_ignores_redundant_data_selection_event():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app._refreshing_data_panel = False
    app.data_tree = SimpleNamespace(selection=lambda: ("0",))
    app.db_rows = [{"barcode": "001"}]
    app.selected_data_indexes = {0}
    app.preview_row = app.db_rows[0]
    app.sample_combo_values = ["1. 001"]
    app.refresh_data_panel = lambda: pytest.fail("redundant selection should not refresh the data panel")
    app.redraw = lambda: pytest.fail("redundant selection should not redraw the canvas")

    app.select_data_tree_row()

    assert app.selected_data_indexes == {0}


def test_designer_command_file_names_are_indexed(tmp_path):
    app = LabelDesignerApp.__new__(LabelDesignerApp)

    first = app._write_designer_command_file(_config("tspl", "utf-8"), tmp_path, b"FIRST", index=1)
    second = app._write_designer_command_file(_config("tspl", "utf-8"), tmp_path, b"SECOND", index=2)

    assert first.name == "designer_label_001.tspl"
    assert second.name == "designer_label_002.tspl"
    assert first.read_bytes() == b"FIRST"
    assert second.read_bytes() == b"SECOND"


def test_designer_prints_image_element_as_bitmap(tmp_path):
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (20, 12), "black").save(image_path)
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.base_dir = tmp_path
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [_element("image", "sample", 5, 5, 20, 12)]
    app.elements[0]["image_path"] = image_path.name
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    command = app.render_designer_print_command(_config("tspl", "utf-8"), row, 1)

    assert b"BITMAP " in command


def test_designer_auto_fit_scale_keeps_large_label_inside_canvas():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.canvas = _FakeCanvas(width=760, height=520)

    scale = app._fit_canvas_scale(120, 90)

    assert 1.2 <= scale <= 24
    assert (120 * scale) <= 640
    assert (90 * scale) <= 440.000001


def test_designer_tspl_bitmap_uses_white_background_black_dots():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    blank = Image.new("1", (16, 2), 1)
    command = app._tspl_bitmap_command(0, 0, blank)
    fields = command.split(b",", 5)
    width_bytes = int(fields[2])
    height = int(fields[3])
    blank_payload = fields[5][: width_bytes * height]

    black = Image.new("1", (8, 1), 1)
    black.putpixel((0, 0), 0)
    black_command = app._tspl_bitmap_command(0, 0, black)
    black_payload = black_command.split(b",", 5)[5][:1]

    assert blank_payload == b"\xff\xff\xff\xff"
    assert black_payload == b"\x7f"


def test_designer_tspl_reverse_text_intentionally_prints_black_background():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    element = _element("text", "A", 0, 0, 12, 8, font_size=12)
    element["reverse"] = True
    command = app._tspl_text_bitmap_command(0, 0, 96, 48, "A", element)
    fields = command.split(b",", 5)
    width_bytes = int(fields[2])
    height = int(fields[3])
    payload = fields[5][: width_bytes * height]

    assert payload[0] == 0x00
    assert any(byte != 0x00 for byte in payload)


def test_designer_print_renderer_uses_configured_printer_language():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [
        _element("text", "ITEM: {{item_name}}", 5, 4, 40, 6, font_size=14, align="center"),
        _element("barcode", "{{barcode}}", 5, 12, 40, 14, barcode_type="code128"),
        _element("field", "LOT: {{lot_no}} / QTY: {{qty}}", 5, 29, 40, 6, font_size=12, align="center"),
        _element("box", "", 2, 2, 46, 34),
    ]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "5J3P7YAYWXL5",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "2",
    }

    slcs = app.render_designer_print_command(_config("slcs", "cp949"), row, 2)
    assert slcs.startswith(b"CB\r\n")
    assert slcs.count(b"BMP") >= 2
    assert slcs.endswith(b"P2\r\n")
    assert app.render_designer_print_command(_config("tspl", "utf-8"), row, 2).startswith(b"SIZE 50 mm,40 mm\n")
    assert app.render_designer_print_command(_config("zpl", "utf-8"), row, 2).startswith(b"^XA\n")


def test_designer_print_renderer_applies_media_handling_options():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = []
    row = {"item_code": "A1002", "item_name": "SENSOR", "barcode": "12345678", "lot_no": "LOT", "qty": "1", "print_qty": "1"}

    assert b"CUTy\r\n" in app.render_designer_print_command(_config("slcs", "cp949", media_handling="cutter"), row, 1)
    assert b"SET CUTTER 1\nSET PEEL OFF\nSET TEAR OFF\n" in app.render_designer_print_command(_config("tspl", "utf-8", media_handling="cutter"), row, 1)
    assert b"^MMP\n" in app.render_designer_print_command(_config("zpl", "utf-8", media_handling="peeler"), row, 1)


@pytest.mark.parametrize(
    ("barcode_type", "value"),
    [
        ("code128", "ABC123"),
        ("gs1_128", "(01)08801234567890"),
        ("code39", "ABC-123"),
        ("ean13", "590123412345"),
        ("ean8", "5512345"),
        ("upca", "04210000526"),
        ("itf", "123456"),
        ("codabar", "A12345A"),
        ("pharmacode", "12345"),
    ],
)
def test_1d_barcode_types_render_real_bitmap_images(barcode_type: str, value: str):
    image = _render_1d_barcode_image(barcode_type, value, 260, 80, _element("barcode", value, 1, 1, 30, 10, barcode_type=barcode_type))

    assert image.size == (260, 80)
    assert ImageChops.invert(image.convert("L")).getbbox() is not None


def test_ean13_rejects_wrong_check_digit():
    with pytest.raises(ValueError, match="체크디지트"):
        _render_1d_barcode_image("ean13", "5901234123450", 260, 80, _element("barcode", "5901234123450", 1, 1, 30, 10, barcode_type="ean13"))


@pytest.mark.parametrize(("barcode_type", "value"), [("ean13", "590123412345"), ("upca", "04210000526"), ("ean8", "5512345")])
def test_ean_upc_rendering_has_extended_guard_bars(barcode_type: str, value: str):
    image = _render_1d_barcode_image(barcode_type, value, 260, 90, _element("barcode", value, 1, 1, 30, 10, barcode_type=barcode_type))
    pixels = image.load()
    top = next(y for y in range(image.height) if any(pixels[x, y] == 0 for x in range(image.width)))
    runs = []
    for x in range(image.width):
        if pixels[x, top] != 0:
            continue
        run = 0
        y = top
        while y < image.height and pixels[x, y] == 0:
            run += 1
            y += 1
        if run > 10:
            runs.append(run)

    assert max(runs) - min(runs) >= 4


def test_qr_barcode_renders_real_bitmap_and_preserves_string_value():
    element = _element("barcode", "001234567890", 1, 1, 18, 18, barcode_type="qr")
    element["barcode_options"]["cell_size"] = 4

    image = _render_qr_code_image("001234567890", 180, 180, element)
    other = _render_qr_code_image("101234567890", 180, 180, element)
    black_bbox = ImageChops.invert(image.convert("L")).getbbox()

    assert image.size == (180, 180)
    assert black_bbox is not None
    assert black_bbox[0] > 0
    assert black_bbox[1] > 0
    assert black_bbox[2] < image.width
    assert black_bbox[3] < image.height
    assert ImageChops.difference(image.convert("L"), other.convert("L")).getbbox() is not None


@pytest.mark.parametrize("barcode_type", sorted(BARCODE_2D_BITMAP_TYPES))
def test_2d_barcode_types_render_real_bitmap_images(barcode_type: str):
    width, height = (360, 160) if barcode_type in {"pdf417", "micropdf417"} else (180, 180)
    element = _element("barcode", "A1001-250531", 1, 1, 36 if barcode_type in {"pdf417", "micropdf417"} else 18, 16 if barcode_type in {"pdf417", "micropdf417"} else 18, barcode_type=barcode_type)

    image = _render_2d_barcode_image(barcode_type, _barcode_value_for_type(barcode_type), width, height, element)
    black_bbox = ImageChops.invert(image.convert("L")).getbbox()

    assert image.size == (width, height)
    assert black_bbox is not None
    assert black_bbox[0] >= 0
    assert black_bbox[1] >= 0
    assert black_bbox[2] <= image.width
    assert black_bbox[3] <= image.height


@pytest.mark.parametrize("barcode_type", sorted(DESIGNER_PRINT_SUPPORTED_BARCODE_TYPES))
def test_designer_preview_uses_full_element_box_for_every_exposed_barcode_type(barcode_type: str):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    value = _barcode_value_for_type(barcode_type)
    width_mm, height_mm = _barcode_element_size_mm(barcode_type)
    element = _element("barcode", "{{barcode}}", 8, 6, width_mm, height_mm, barcode_type=barcode_type)
    app.template = {"version": 1, "label": {"width_mm": 60, "height_mm": 40}, "elements": []}
    app.elements = [element]
    app.preview_row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": value,
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    image = app.render_preview_image()
    crop = image.crop((8 * 8, 6 * 8, (8 + width_mm) * 8, (6 + height_mm) * 8))
    black_bbox = ImageChops.invert(crop.convert("L")).getbbox()

    assert crop.size == (width_mm * 8, height_mm * 8)
    assert black_bbox is not None


@pytest.mark.parametrize("barcode_type", sorted(DESIGNER_PRINT_SUPPORTED_BARCODE_TYPES))
@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_designer_prints_every_exposed_barcode_type_as_full_size_bitmap(language: str, barcode_type: str):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    value = _barcode_value_for_type(barcode_type)
    width_mm, height_mm = _barcode_element_size_mm(barcode_type)
    element = _element("barcode", "{{barcode}}", 8, 6, width_mm, height_mm, barcode_type=barcode_type)
    app.template = {"version": 1, "label": {"width_mm": 60, "height_mm": 40}, "elements": []}
    app.elements = [element]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": value,
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }
    expected_marker = {"slcs": b"BMP", "tspl": b"BITMAP ", "zpl": b"^GFA"}[language]
    expected_size = (mm_to_dots(width_mm, 203), mm_to_dots(height_mm, 203))

    payload = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    assert expected_marker in payload
    assert _bitmap_dimensions(payload, language) == expected_size


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("slcs", b"BMP"),
        ("tspl", b"BITMAP "),
        ("zpl", b"^GFA"),
    ],
)
def test_designer_prints_non_code128_1d_as_matching_bitmap(language: str, expected: bytes):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [_element("barcode", "A12345A", 5, 10, 40, 16, barcode_type="codabar")]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "2",
    }

    command = app.render_designer_print_command(_config(language, "utf-8"), row, 2)
    payload = command if isinstance(command, bytes) else command.encode("ascii")

    assert expected in payload


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("slcs", b"BD"),
        ("tspl", b"BOX "),
        ("zpl", b"^GB"),
    ],
)
def test_designer_prints_table_object_for_all_printer_languages(language: str, expected: bytes):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    table = _element("table", "", 4, 5, 30, 18)
    table["table_rows"] = 3
    table["table_cols"] = 4
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [table]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "2",
    }

    command = app.render_designer_print_command(_config(language, "utf-8"), row, 2)
    payload = command if isinstance(command, bytes) else command.encode("ascii")

    assert expected in payload


def test_designer_tspl_table_uses_configured_rows_and_columns():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    table = _element("table", "", 4, 5, 30, 18)
    table["table_rows"] = 4
    table["table_cols"] = 2
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [table]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A12345A",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "2",
    }

    command = app.render_designer_print_command(_config("tspl", "utf-8"), row, 2)

    assert command.count(b"BOX ") == 1
    assert command.count(b"BAR ") == 4


@pytest.mark.parametrize(
    ("language", "expected", "forbidden"),
    [
        ("slcs", b"BMP", b"B2"),
        ("tspl", b"BITMAP ", b"QRCODE "),
        ("zpl", b"^GFA", b"^BQ"),
    ],
)
def test_designer_qr_outputs_same_bitmap_path_for_screen_and_print(language: str, expected: bytes, forbidden: bytes):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    element = _element("barcode", "A1001-250531", 5, 10, 30, 18, barcode_type="qr")
    element["barcode_options"]["cell_size"] = 6
    element["barcode_options"]["qr_ecc"] = "H"
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [element]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "A1001-250531",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    payload = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    assert expected in payload
    assert forbidden not in payload


@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
def test_designer_qr_bitmap_output_matches_element_dot_size(language: str):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    element = _element("barcode", "001234567890", 16, 8, 18, 18, barcode_type="qr")
    element["barcode_options"]["cell_size"] = 2
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [element]
    row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "001234567890",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }
    expected_size = mm_to_dots(18, 203)

    payload = app.render_designer_print_command(_config(language, "utf-8"), row, 1)

    assert _bitmap_dimensions(payload, language) == (expected_size, expected_size)


def test_designer_qr_preview_export_matches_element_pixel_size():
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    element = _element("barcode", "001234567890", 16, 8, 18, 18, barcode_type="qr")
    element["barcode_options"]["cell_size"] = 2
    app.template = {"version": 1, "label": {"width_mm": 50, "height_mm": 40}, "elements": []}
    app.elements = [element]
    app.preview_row = {
        "item_code": "A1002",
        "item_name": "SENSOR BRACKET",
        "barcode": "001234567890",
        "lot_no": "LOT250532",
        "qty": "100",
        "print_qty": "1",
    }

    image = app.render_preview_image()
    crop = image.crop((16 * 8, 8 * 8, (16 + 18) * 8, (8 + 18) * 8))
    black_bbox = ImageChops.invert(crop.convert("L")).getbbox()

    assert crop.size == (18 * 8, 18 * 8)
    assert black_bbox is not None
    assert black_bbox[0] > 0
    assert black_bbox[1] > 0
    assert black_bbox[2] < crop.width
    assert black_bbox[3] < crop.height


def _barcode_value_for_type(barcode_type: str) -> str:
    values = {
        "code128": "ABC123",
        "gs1_128": "(01)08801234567890",
        "code39": "ABC-123",
        "codabar": "A12345A",
        "ean13": "590123412345",
        "ean8": "5512345",
        "upca": "04210000526",
        "itf": "123456",
        "pharmacode": "12345",
        "qr": "A1001-250531",
        "microqr": "A123",
        "datamatrix": "A1001-250531",
        "pdf417": "A1001-250531",
        "micropdf417": "A1001-250531",
        "aztec": "A1001-250531",
        "maxicode": "A1001-250531",
    }
    return values[barcode_type]


def _barcode_element_size_mm(barcode_type: str) -> tuple[int, int]:
    if barcode_type in {"pdf417", "micropdf417"}:
        return 36, 16
    if barcode_type in BARCODE_2D_BITMAP_TYPES:
        return 18, 18
    if barcode_type in BARCODE_1D_BITMAP_TYPES:
        return 36, 16
    raise AssertionError(barcode_type)


def _config(language: str, command_encoding: str, media_handling: str = "tear_off") -> SimpleNamespace:
    return SimpleNamespace(
        printer=SimpleNamespace(
            language=language,
            command_encoding=command_encoding,
            print_method="direct_thermal",
            media_handling=media_handling,
            print_speed=4,
            print_density=10,
        ),
        label=SimpleNamespace(dpi=203, gap_mm=3),
        barcode=SimpleNamespace(
            qr_model=2,
            qr_ecc="M",
            qr_cell_size=4,
            datamatrix_cell_size=4,
            pdf417_columns=5,
            pdf417_rows=30,
            pdf417_security_level=2,
        ),
    )


class _FakeCanvas:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def winfo_width(self) -> int:
        return self._width

    def winfo_height(self) -> int:
        return self._height


class _FakeCard:
    def __init__(self) -> None:
        self.shown = 0
        self.removed = 0

    def grid(self) -> None:
        self.shown += 1

    def grid_remove(self) -> None:
        self.removed += 1


def _bitmap_dimensions(payload: bytes, language: str) -> tuple[int, int]:
    if language == "slcs":
        marker_end = payload.index(b"\r\n", payload.index(b"BMP"))
        bmp_start = marker_end + 2
        bmp_size = int.from_bytes(payload[bmp_start + 2 : bmp_start + 6], "little")
        with Image.open(io.BytesIO(payload[bmp_start : bmp_start + bmp_size])) as image:
            return image.size
    if language == "tspl":
        fields = payload[payload.index(b"BITMAP ") :].split(b",", 5)
        width_bytes = int(fields[2])
        height = int(fields[3])
        return width_bytes * 8, height
    if language == "zpl":
        marker = b"^GFA,"
        start = payload.index(marker) + len(marker)
        total_raw, _total_repeat_raw, width_bytes_raw, _data = payload[start:].split(b",", 3)
        total = int(total_raw)
        width_bytes = int(width_bytes_raw)
        return width_bytes * 8, total // width_bytes
    raise AssertionError(language)
