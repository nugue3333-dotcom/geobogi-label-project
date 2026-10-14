"""Saved-template, screen-preview and printer bitmap geometry regressions."""
from __future__ import annotations

import copy
from configparser import ConfigParser
import io
import json
import math
import re

from PIL import Image, ImageChops
import pytest

from barcode_label_automation.config import DEFAULTS, load_config
from barcode_label_automation.barcode_catalog import BARCODE_2D_TYPES, SAMPLE_VALUES, sample_options
from barcode_label_automation.barcode_engine import render_barcode
from barcode_label_automation.designer_clipboard import clone_objects, decode_objects, encode_objects
from barcode_label_automation.gs1 import build_gs1, parse_gs1
from barcode_label_automation.label_designer_app import (
    LabelDesignerApp, _element, _normalize_element, _render_2d_barcode_image,
    load_template_file, normalize_template,
)
from barcode_label_automation.templates import mm_to_dots
from barcode_label_automation.template_output import render_command, render_preview


SSCC = "(00)106141411234567897"
MULTI_AI = "(01)09506000134376(10)LOT001(21)SN0001"


def configured_element(kind="gs1_datamatrix", value=SSCC, *, dpi=203):
    obj = _element("barcode", value, 2, 3, 50, 30, barcode_type=kind)
    obj["barcode_options"].update(human_readable=True, cell_size=1)
    obj["barcode_layout"] = {
        "version": 2, "size_mode": "size", "symbol_width_mm": 10,
        "symbol_height_mm": 10, "hri_position": "right", "hri_gap_mm": 1,
        "hri_font_mode": "auto",
    }
    obj["_render_dpi"] = dpi
    return obj


def direct_image(obj, dpi):
    return _render_2d_barcode_image(str(obj["barcode_type"]), str(obj["text"]),
                                  mm_to_dots(obj["width"], dpi),
                                  mm_to_dots(obj["height"], dpi), obj)


def fixture_app(obj, dpi):
    app = LabelDesignerApp.__new__(LabelDesignerApp)
    app.template = {"version": 1, "label": {"width_mm": 60, "height_mm": 40, "dpi": dpi},
                    "elements": [obj]}
    app.elements = [obj]
    app.preview_row = {}
    app._validation_dpi = lambda: dpi
    return app


@pytest.mark.parametrize("kind", ["qr", "datamatrix", "gs1_datamatrix", "pdf417", "aztec"])
def test_new_matrix_objects_default_to_size_first_metadata(kind):
    obj = _element("barcode", "test", 1, 1, 32, 10, barcode_type=kind)
    assert obj["barcode_layout"] == {
        "version": 2, "size_mode": "size", "symbol_width_mm": 32,
        "symbol_height_mm": 10, "hri_position": "right", "hri_gap_mm": 1,
        "hri_font_mode": "auto",
    }


def test_qr_tool_without_explicit_kind_also_gets_size_first_metadata():
    assert _element("qr", "000123", 1, 1, 18, 18)["barcode_layout"]["version"] == 2


def test_linear_objects_remain_outside_the_matrix_layout_contract():
    assert "barcode_layout" not in _element("barcode", "ABC", 1, 1, 30, 10, barcode_type="code128")


@pytest.mark.parametrize("kind", ["qr", "gs1_datamatrix", "datamatrix"])
def test_legacy_file_absent_metadata_is_not_silently_migrated(kind):
    original = {"type": "barcode", "barcode_type": kind, "text": SSCC,
                "x": 1, "y": 1, "width": 32, "height": 10,
                "barcode_options": {"cell_size": 1, "human_readable": False}}
    normalized = _normalize_element(original)
    assert "barcode_layout" not in normalized
    assert "barcode_layout" not in normalize_template({"label": {}, "elements": [original]})["elements"][0]
    assert normalized["width"] == 32 and normalized["height"] == 10


def test_saved_json_and_clipboard_keep_layout_but_drop_render_context(tmp_path):
    original = configured_element(dpi=600)
    normalized = _normalize_element(original)
    assert "_render_dpi" not in normalized
    path = tmp_path / "geometry.cllabel"
    path.write_text(json.dumps({"label": {"width_mm": 60, "height_mm": 40},
                               "elements": [normalized]}), encoding="utf-8")
    restored = load_template_file(path)["elements"][0]
    assert restored["barcode_layout"] == original["barcode_layout"]
    pasted = clone_objects(decode_objects(encode_objects([normalized], tmp_path)), 80, 80, 2)[0]
    pasted = _normalize_element(pasted)
    assert pasted["id"] != normalized["id"]
    assert pasted["barcode_layout"] == normalized["barcode_layout"]
    pasted["barcode_layout"]["symbol_width_mm"] = 20
    assert original["barcode_layout"]["symbol_width_mm"] == 10


@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_render_metadata_and_hri_options_never_change_symbol(dpi):
    obj = configured_element(dpi=dpi)
    initial = direct_image(obj, dpi)
    assert initial.info["actual_symbol_mm"][0] <= 10
    variants = []
    for changes in [{"human_readable": False}, {"font_size": 6}, {"font_size": 30}, {"hri_position": "below"}]:
        other = copy.deepcopy(obj)
        if "human_readable" in changes:
            other["barcode_options"].update(changes)
        elif "font_size" in changes:
            other.update(changes)
        else:
            other["barcode_layout"].update(changes)
        variants.append(direct_image(other, dpi))
    bounds = initial.info["symbol_bounds"]
    for rendered in variants:
        assert rendered.info["symbol_bounds"] == bounds
        assert rendered.info["module_dots"] == initial.info["module_dots"]
        assert rendered.crop(bounds).tobytes() == initial.crop(bounds).tobytes()


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize("screen_scale", [1, 1.5, 2])
def test_preview_is_a_view_of_actual_print_bitmap(dpi, screen_scale):
    obj = configured_element(dpi=dpi)
    app = fixture_app(obj, dpi)
    width, height = round(float(obj["width"]) * 8 * screen_scale), round(float(obj["height"]) * 8 * screen_scale)
    preview = app._render_2d_preview_bitmap(obj, {}, width, height, transparent=False)
    expected = direct_image(obj, dpi).resize((width, height), Image.Resampling.NEAREST)
    assert preview.size == expected.size
    assert ImageChops.difference(preview.convert("L"), expected.convert("L")).getbbox() is None


def config_for(tmp_path, language, dpi):
    parser = ConfigParser(interpolation=None)
    parser.read_dict(DEFAULTS)
    parser.set("printer", "brand", {"slcs": "bixolon", "tspl": "tsc", "zpl": "zebra"}[language])
    parser.set("printer", "language", language)
    parser.set("printer", "mode", "network")
    parser.set("printer", "ip", "127.0.0.1")
    parser.set("label", "width_mm", "60")
    parser.set("label", "height_mm", "40")
    parser.set("label", "dpi", str(dpi))
    path = tmp_path / "config.ini"
    with path.open("w", encoding="utf-8") as stream:
        parser.write(stream)
    return load_config(path)


def bitmap_from_command(payload, language):
    if language == "slcs":
        match = re.search(rb"BMP\d+,\d+\r\n", payload)
        assert match is not None
        return Image.open(io.BytesIO(payload[match.end():])).copy().convert("1")
    if language == "tspl":
        match = re.search(rb"BITMAP \d+,\d+,(\d+),(\d+),0,", payload)
        assert match is not None
        width_bytes, height = map(int, match.groups())
        return Image.frombytes("1", (width_bytes * 8, height), payload[match.end():match.end() + width_bytes * height])
    match = re.search(rb"\^GFA,\d+,\d+,(\d+),([0-9A-F]+)\^FS", payload)
    assert match is not None
    width_bytes = int(match.group(1))
    raw = bytes.fromhex(match.group(2).decode("ascii"))
    return Image.frombytes("1", (width_bytes * 8, len(raw) // width_bytes), bytes(v ^ 255 for v in raw))


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize("language", ["slcs", "tspl", "zpl"])
@pytest.mark.parametrize("kind,value", [("gs1_datamatrix", SSCC), ("gs1_datamatrix", MULTI_AI), ("qr", "001234567890")])
def test_print_payload_contains_same_scale_and_independently_decodes(tmp_path, language, dpi, kind, value):
    zxingcpp = pytest.importorskip("zxingcpp")
    obj = configured_element(kind, value, dpi=dpi)
    app = fixture_app(obj, dpi)
    # The command must carry actual config DPI, rather than a transient hint.
    app.elements[0].pop("_render_dpi")
    command = app.render_designer_print_command(config_for(tmp_path, language, dpi), {}, 1)
    image = bitmap_from_command(command, language)
    expected = direct_image(dict(obj, _render_dpi=dpi), dpi)
    image = image.crop((0, 0, expected.width, expected.height))
    assert ImageChops.difference(image.convert("L"), expected.convert("L")).getbbox() is None
    decoded = zxingcpp.read_barcode(image.crop(expected.info["symbol_bounds"]).convert("L"))
    assert decoded is not None
    expected_bytes = build_gs1(parse_gs1(value)).payload.encode("ascii") if kind.startswith("gs1_") else value.encode("ascii")
    assert decoded.bytes == expected_bytes


def test_print_refuses_insufficient_hri_space_instead_of_shrinking(tmp_path):
    obj = configured_element(value="(01)09506000134376(10)" + "A" * 20)
    obj["width"] = 12
    app = fixture_app(obj, 203)
    with pytest.raises(ValueError, match="표시문자"):
        app.render_designer_print_command(config_for(tmp_path, "tspl", 203), {}, 1)


@pytest.mark.parametrize("kind", sorted(BARCODE_2D_TYPES))
def test_every_matrix_catalogue_type_retains_natural_aspect_and_printable_geometry(kind):
    # A deliberately roomy group tests encoder/layout coverage. Real customers
    # still choose an appropriate target for their data and application.
    obj = _element("barcode", SAMPLE_VALUES[kind], 0, 0, 70, 50, barcode_type=kind)
    obj["barcode_options"].update(sample_options(kind))
    obj["_render_dpi"] = 203
    assert obj["barcode_options"]["human_readable"] is False
    image = direct_image(obj, 203)
    source = render_barcode(kind, SAMPLE_VALUES[kind], dict(sample_options(kind), cell_size=1))
    bounds, module_dots = image.info["symbol_bounds"], image.info["module_dots"]
    expected_scale = min(math.floor(70 * 203 / 25.4 / source.width),
                         math.floor(50 * 203 / 25.4 / source.height))
    assert module_dots == expected_scale
    assert bounds == (0, 0, source.width * module_dots, source.height * module_dots)
    assert bounds[2] <= image.width and bounds[3] <= image.height
    assert ImageChops.invert(image.convert("L")).getbbox() is not None
    assert image.info["actual_symbol_mm"][0] <= 70
    assert image.info["actual_symbol_mm"][1] <= 50


@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_pdf417_rectangular_ratio_and_independent_decode(dpi):
    zxingcpp = pytest.importorskip("zxingcpp")
    obj = _element("barcode", "000123456789", 0, 0, 60, 30, barcode_type="pdf417")
    obj["_render_dpi"] = dpi
    image = direct_image(obj, dpi)
    source = render_barcode("pdf417", "000123456789", {"cell_size": 1})
    assert source.width > source.height
    symbol = image.crop(image.info["symbol_bounds"])
    assert symbol.width * source.height == symbol.height * source.width
    decoded = zxingcpp.read_barcode(symbol.convert("L"))
    assert decoded is not None and decoded.bytes == b"000123456789"


@pytest.mark.parametrize("dpi", [300, 600])
def test_saved_template_preview_uses_active_config_dpi_and_print_geometry(tmp_path, dpi):
    obj = configured_element(dpi=203)
    obj.pop("_render_dpi")
    # Saved documents can contain an older DPI; the active printer config
    # controls both the batch preview and the actual command bitmap.
    template = {"version": 1, "label": {"width_mm": 60, "height_mm": 40, "dpi": 203},
                "elements": [obj]}
    original = copy.deepcopy(template)
    config = config_for(tmp_path, "tspl", dpi)
    command = render_command(template, {}, config, tmp_path, 1)
    print_bitmap = bitmap_from_command(command, "tspl").crop((
        0, 0, mm_to_dots(obj["width"], dpi), mm_to_dots(obj["height"], dpi)))
    preview = render_preview(template, {}, tmp_path)
    preview_crop = preview.crop((16, 24, 416, 264)).convert("L").point(lambda p: 255 if p >= 128 else 0)
    expected = print_bitmap.resize((400, 240), Image.Resampling.NEAREST).convert("L")
    assert ImageChops.difference(preview_crop, expected).getbbox() is None
    stale_bitmap = direct_image(dict(obj, _render_dpi=203), 203).resize((400, 240), Image.Resampling.NEAREST).convert("L")
    assert ImageChops.difference(expected, stale_bitmap).getbbox() is not None
    assert template == original


def test_wide_composite_default_target_uses_object_width_instead_of_smaller_side():
    kind = "gs1_composite"
    obj = _element("barcode", SAMPLE_VALUES[kind], 0, 0, 34, 20, barcode_type=kind)
    obj["barcode_options"].update(sample_options(kind))
    source = render_barcode(kind, SAMPLE_VALUES[kind], dict(sample_options(kind), cell_size=1))
    image = direct_image(obj, 203)
    assert source.width > math.floor(20 * 203 / 25.4)
    assert image.info["symbol_bounds"] == (0, 0, source.width, source.height)
    assert obj["barcode_layout"]["symbol_width_mm"] == 34


@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_zero_targets_reflow_once_then_remain_stable(dpi):
    obj = configured_element(value="(01)09506000134376", dpi=dpi)
    obj.update(width=10,height=10)
    obj["barcode_layout"].update(symbol_width_mm=0,symbol_height_mm=0)
    app = fixture_app(obj,dpi)
    first = app._reflow_barcode_element(obj)
    dimensions=(obj["width"],obj["height"])
    second=app._reflow_barcode_element(obj)
    assert first.info["actual_symbol_mm"]==second.info["actual_symbol_mm"]
    assert dimensions==(obj["width"],obj["height"])
    assert first.tobytes()==second.tobytes()
