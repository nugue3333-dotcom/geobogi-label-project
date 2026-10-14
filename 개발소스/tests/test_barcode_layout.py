from copy import deepcopy
import math

from PIL import Image, ImageFont
import pytest

from barcode_label_automation.barcode_engine import render_barcode
from barcode_label_automation.barcode_layout import measure_barcode_first, render_barcode_first, symbol_geometry


def load_font(size, name):
    return ImageFont.truetype("C:/Windows/Fonts/consola.ttf", size)


def element(**changes):
    result = {
        "font_size": 10,
        "font_name": "Consolas",
        "barcode_options": {"human_readable": True, "cell_size": 1},
        "barcode_layout": {"version": 2, "size_mode": "size", "symbol_width_mm": 10,
                           "symbol_height_mm": 10, "hri_position": "right",
                           "hri_gap_mm": 1, "hri_font_mode": "auto"},
    }
    result["barcode_layout"].update(changes)
    return result


def matrix(width=18, height=18):
    source = Image.new("1", (width, height), 1)
    for x in range(1, width - 1):
        for y in range(1, height - 1):
            source.putpixel((x, y), (x + y) % 2)
    source.info["module_dots"] = 1
    return source


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize("font_size", [6, 10, 30])
def test_hri_font_and_visibility_never_changes_symbol(dpi, font_size):
    source = matrix()
    options = element()
    options["font_size"] = font_size
    enabled = render_barcode_first(source, options, ["(01)09506000134376"], dpi * 2, dpi, dpi, load_font)
    options["barcode_options"]["human_readable"] = False
    disabled = render_barcode_first(source, options, "", dpi * 2, dpi, dpi, load_font)
    for field in ["symbol_bounds", "module_dots", "actual_symbol_mm"]:
        assert enabled.info[field] == disabled.info[field]
    bounds = enabled.info["symbol_bounds"]
    assert enabled.crop(bounds).tobytes() == disabled.crop(bounds).tobytes()
    assert enabled.info["actual_hri_font_pt"] >= 6
    assert disabled.info["hri_bounds"] is None


@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_target_is_never_exceeded_and_whole_module_is_used(dpi):
    geo = symbol_geometry(matrix(), element(), dpi, dpi, dpi)
    assert geo.module_dots == math.floor(10 * dpi / 25.4 / 18)
    assert geo.actual_symbol_mm[0] <= 10
    assert geo.bounds == (0, 0, 18 * geo.module_dots, 18 * geo.module_dots)


def test_hri_location_does_not_move_symbol_and_below_attaches():
    options = element()
    right = render_barcode_first(matrix(), options, "(10)ABC", 250, 180, 203, load_font)
    options["barcode_layout"]["hri_position"] = "below"
    below = render_barcode_first(matrix(), options, "(10)ABC", 250, 180, 203, load_font)
    assert right.info["symbol_bounds"] == below.info["symbol_bounds"]
    assert right.info["hri_bounds"][0] == right.info["symbol_bounds"][2] + 8
    assert below.info["hri_bounds"][1] == below.info["symbol_bounds"][3] + 8


@pytest.mark.parametrize("shape", [(18, 18), (34, 14), (42, 8)])
def test_rectangular_aspect_ratio_and_quiet_zone_preserved(shape):
    source = matrix(*shape)
    options = element()
    options["barcode_options"]["human_readable"] = False
    image = render_barcode_first(source, options, "", 250, 180, 300, load_font)
    bounds = image.info["symbol_bounds"]
    scale = image.info["module_dots"]
    assert bounds[2:] == (shape[0] * scale, shape[1] * scale)
    code = image.crop(bounds)
    assert all(code.getpixel((x, 0)) != 0 for x in range(code.width))
    assert all(code.getpixel((0, y)) != 0 for y in range(code.height))
    assert code.tobytes() == source.resize(code.size, Image.Resampling.NEAREST).tobytes()


def test_module_mode_respects_explicit_scale_independent_of_target_and_text():
    options = element(size_mode="module", symbol_width_mm=1, symbol_height_mm=1)
    options["barcode_options"]["cell_size"] = 5
    image = render_barcode_first(matrix(), options, "(10)ABC", 250, 160, 203, load_font)
    assert image.info["module_dots"] == 5
    assert image.info["symbol_bounds"] == (0, 0, 90, 90)


def test_default_target_uses_group_side_not_hri():
    options = element(symbol_width_mm=0, symbol_height_mm=0)
    image = render_barcode_first(matrix(), options, "(10)A", 250, 90, 203, load_font)
    assert image.info["module_dots"] == 5


@pytest.mark.parametrize("target", [0.1, 100])
def test_impossible_symbol_rejected_and_inputs_untouched(target):
    source = matrix()
    options = element(symbol_width_mm=target, symbol_height_mm=target)
    before = deepcopy(options)
    source_bytes = source.tobytes()
    with pytest.raises(ValueError):
        render_barcode_first(source, options, "(10)ABC", 100, 100, 203, load_font)
    assert source.tobytes() == source_bytes
    assert options == before


def test_multiple_ai_wrap_at_ai_boundaries_without_cutting():
    groups = ["(01)09506000134376", "(10)LOT123456", "(21)SER0001", "(17)271231"]
    image = render_barcode_first(matrix(), element(), groups, 290, 140, 203, load_font)
    assert len(image.info["hri_lines"]) > 1
    assert "".join(image.info["hri_lines"]) == "".join(groups)
    tx, ty, right, bottom = image.info["hri_bounds"]
    assert 0 <= tx < right <= image.width and 0 <= ty < bottom <= image.height


def test_long_ai_or_no_text_space_rejected_instead_of_shrinking():
    options = element()
    expected = symbol_geometry(matrix(), options, 250, 100, 203)
    for value, width in [("(10)" + "A" * 100, 250), ("(10)A", 72)]:
        with pytest.raises(ValueError, match="표시문자"):
            render_barcode_first(matrix(), options, value, width, 100, 203, load_font)
    assert symbol_geometry(matrix(), options, 250, 100, 203) == expected


def test_fixed_font_does_not_silently_shrink():
    options = element(hri_font_mode="fixed")
    options["font_size"] = 30
    with pytest.raises(ValueError, match="원문"):
        render_barcode_first(matrix(), options, "(01)09506000134376", 250, 100, 203, load_font)


@pytest.mark.parametrize("change", [{"symbol_width_mm": float("nan")}, {"symbol_height_mm": -1},
                                    {"hri_gap_mm": float("inf")}, {"size_mode": "bad"},
                                    {"hri_position": "bad"}])
def test_invalid_layout_rejected(change):
    with pytest.raises(ValueError):
        symbol_geometry(matrix(), element(**change), 300, 200, 203)


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize("kind,value,groups", [
    ("gs1_datamatrix", "(00)106141411234567897", ["(00)106141411234567897"]),
    ("gs1_datamatrix", "(01)09506000134376(10)LOT001(21)SN0001", ["(01)09506000134376", "(10)LOT001", "(21)SN0001"]),
    ("qr", "leading-zero:000123", ["leading-zero:000123"]),
])
def test_real_symbol_decode_and_data_preservation(dpi, kind, value, groups):
    zxingcpp = pytest.importorskip("zxingcpp")
    source = render_barcode(kind, value, {"cell_size": 1, "human_readable": False})
    image = render_barcode_first(source, element(), groups, dpi * 2, dpi, dpi, load_font)
    decoded = zxingcpp.read_barcode(image.crop(image.info["symbol_bounds"]).convert("L"))
    assert decoded is not None
    if kind == "gs1_datamatrix":
        from barcode_label_automation.gs1 import build_gs1, parse_gs1
        assert decoded.bytes == build_gs1(parse_gs1(value)).payload.encode("ascii")
    else:
        assert decoded.text == value


@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_geometry_can_measure_symbol_outside_old_group_for_edit_recovery(dpi):
    options = element(symbol_width_mm=20, symbol_height_mm=20)
    with pytest.raises(ValueError, match="바코드 공간"):
        symbol_geometry(matrix(), options, 40, 40, dpi)
    geometry = symbol_geometry(matrix(), options, 40, 40, dpi, check_bounds=False)
    assert geometry.actual_symbol_mm[0] <= 20
    assert geometry.bounds[2] > 40


@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_preview_keeps_valid_code_when_hri_cannot_fit(dpi):
    options = element()
    expected = symbol_geometry(matrix(), options, dpi, dpi, dpi)
    width = expected.bounds[2]
    preview = render_barcode_first(matrix(), options, "(10)LOT001", width, width, dpi, load_font, preview_only=True)
    assert preview.info["layout_error"]
    assert preview.info["layout_overflow"]
    assert preview.info["symbol_bounds"] == expected.bounds
    assert preview.info["hri_bounds"] is None
    assert preview.crop(expected.bounds).tobytes() == matrix().resize((width, width), Image.Resampling.NEAREST).tobytes()
    with pytest.raises(ValueError, match="表示|표시문자"):
        render_barcode_first(matrix(), options, "(10)LOT001", width, width, dpi, load_font)


def test_preview_expands_to_show_whole_symbol_outside_original_box():
    preview = render_barcode_first(matrix(), element(), "(10)A", 10, 10, 203, load_font, preview_only=True)
    assert preview.size == (72, 72)
    assert preview.info["layout_error"]
    assert preview.getbbox()


@pytest.mark.parametrize("dpi", [203, 300, 600])
@pytest.mark.parametrize("position", ["right", "below"])
def test_measure_reflows_composite_without_changing_symbol(dpi, position):
    options = element(hri_position=position)
    options.update(width=2, height=2)
    groups = ["(01)09506000134376", "(10)LOT001", "(21)SER0001"]
    before = deepcopy(options)
    image = measure_barcode_first(matrix(), options, groups, dpi, load_font, max_width_mm=50)
    expected = symbol_geometry(matrix(), options, 1, 1, dpi, check_bounds=False)
    assert image.info["symbol_bounds"] == expected.bounds
    assert "".join(image.info["hri_lines"]) == "".join(groups)
    assert image.info["actual_hri_font_pt"] >= 6
    assert image.info["actual_group_mm"] == (image.width * 25.4 / dpi, image.height * 25.4 / dpi)
    tx, ty, right, bottom = image.info["hri_bounds"]
    assert right <= image.width and bottom <= image.height
    assert not image.info["layout_overflow"]
    assert options == before
    options["barcode_options"]["human_readable"] = False
    code = measure_barcode_first(matrix(), options, groups, dpi, load_font, max_width_mm=50)
    assert code.size == expected.bounds[2:]
    assert code.info["symbol_bounds"] == image.info["symbol_bounds"]
    assert code.tobytes() == image.crop(expected.bounds).tobytes()


def test_measure_wraps_intact_ai_groups_to_budget_and_computes_height():
    groups = ["(01)09506000134376", "(10)LOT001", "(21)SER0001", "(17)271231"]
    image = measure_barcode_first(matrix(), element(hri_position="below"), groups, 203, load_font, max_width_mm=24)
    assert len(image.info["hri_lines"]) >= 2
    assert "".join(image.info["hri_lines"]) == "".join(groups)
    assert not image.info["layout_overflow"]
    assert image.width * 25.4 / 203 <= 24
    assert image.info["hri_bounds"][3] == image.height


@pytest.mark.parametrize("position", ["right", "below"])
def test_measure_single_overlong_group_keeps_text_and_flags_overflow(position):
    group = "(10)" + "A" * 100
    image = measure_barcode_first(matrix(), element(hri_position=position), [group], 203, load_font, max_width_mm=20)
    assert image.info["layout_error"]
    assert image.info["layout_overflow"]
    assert image.info["hri_lines"] == [group]
    assert image.info["actual_hri_font_pt"] >= 6
    assert image.width * 25.4 / 203 > 20
    assert image.info["symbol_bounds"] == (0, 0, 72, 72)


def test_measure_fixed_font_and_module_lock_are_preserved():
    options = element(size_mode="module", hri_font_mode="fixed")
    options["font_size"] = 24
    options["barcode_options"]["cell_size"] = 4
    image = measure_barcode_first(matrix(), options, "(10)ABC", 203, load_font, max_width_mm=20)
    assert image.info["module_dots"] == 4
    assert image.info["actual_hri_font_pt"] == round(24 * 203 / 72) * 72 / 203
    assert image.info["layout_overflow"]


@pytest.mark.parametrize("dpi", [0, -1, True, 203.0])
def test_measure_rejects_invalid_dpi_without_zero_division(dpi):
    with pytest.raises(ValueError, match="DPI"):
        measure_barcode_first(matrix(), element(), "ABC", dpi, load_font, max_width_mm=20)


@pytest.mark.parametrize("dpi", [203, 300, 600])
def test_measured_and_error_preview_are_independently_decodable(dpi):
    zxingcpp = pytest.importorskip("zxingcpp")
    from barcode_label_automation.gs1 import build_gs1, parse_gs1
    value = "(01)09506000134376(10)LOT001(21)SER0001"
    groups = ["(01)09506000134376", "(10)LOT001", "(21)SER0001"]
    source = render_barcode("gs1_datamatrix", value, {"cell_size": 1, "human_readable": False})
    measured = measure_barcode_first(source, element(), groups, dpi, load_font, max_width_mm=40)
    width = measured.info["symbol_bounds"][2]
    preview = render_barcode_first(source, element(), groups, width, width, dpi, load_font, preview_only=True)
    assert preview.info["layout_error"]
    for image in (measured, preview):
        decoded = zxingcpp.read_barcode(image.crop(image.info["symbol_bounds"]).convert("L"))
        assert decoded is not None
        assert decoded.bytes == build_gs1(parse_gs1(value)).payload.encode("ascii")
