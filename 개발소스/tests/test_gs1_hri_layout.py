from __future__ import annotations

from PIL import ImageDraw
import pytest
import zxingcpp

from barcode_label_automation.gs1 import build_gs1, parse_gs1
from barcode_label_automation.label_designer_app import (
    _element, _gs1_hri_lines, _gs1_hri_packed_lines,
    _render_2d_barcode_image, _render_1d_barcode_image,
)

VALUE = "(01)09506000134376(17)271231(10)LOT/A.B-1(21)SERIAL00000000000001"


def test_hri_groups_preserve_all_data_beyond_48_characters():
    groups = _gs1_hri_lines(VALUE)
    assert "".join(groups) == VALUE
    assert len(VALUE) > 48
    lines = _gs1_hri_packed_lines(groups, 25, len)
    assert "".join(lines) == VALUE
    assert all(line.startswith("(") for line in lines)


@pytest.mark.parametrize("size", [(480, 160), (700, 240), (900, 360)])
def test_gs1_datamatrix_right_hri_remains_scannable(size):
    element = _element("qr", VALUE, 0, 0, 50, 20, barcode_type="gs1_datamatrix")
    element["barcode_options"]["human_readable"] = True
    image = _render_2d_barcode_image("gs1_datamatrix", VALUE, *size, element)
    assert image.info["hri_layout"] == "right"
    assert "".join(image.info["hri_lines"]) == VALUE
    decoded = zxingcpp.read_barcode(image.convert("L"))
    assert decoded and decoded.symbology_identifier == "]d2"
    assert decoded.bytes.decode("ascii") == build_gs1(parse_gs1(VALUE)).payload
    assert image.info["module_dots"] == int(image.info["module_dots"])


def test_gs1_128_lower_hri_keeps_parentheses_and_does_not_truncate(monkeypatch):
    painted = []
    original = ImageDraw.ImageDraw.text
    def record(self, xy, text, *args, **kwargs):
        painted.append(text)
        return original(self, xy, text, *args, **kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record)
    value = "(01)09506000134376(17)271231(10)LOT/A.B-1(21)SER0001"
    assert len(value) > 48
    element = _element("barcode", value, 0, 0, 100, 20, barcode_type="gs1_128")
    image = _render_1d_barcode_image("gs1_128", value, 1500, 230, element)
    assert value in painted
    decoded = zxingcpp.read_barcode(image.convert("L"))
    assert decoded and decoded.symbology_identifier == "]C1"
    assert decoded.bytes.decode("ascii") == build_gs1(parse_gs1(value)).payload


def test_hri_off_uses_full_box_without_side_text(monkeypatch):
    painted = []
    monkeypatch.setattr(ImageDraw.ImageDraw, "text", lambda self, xy, text, *args, **kwargs: painted.append(text))
    element = _element("qr", VALUE, 0, 0, 30, 30, barcode_type="gs1_datamatrix")
    element["barcode_options"]["human_readable"] = False
    image = _render_2d_barcode_image("gs1_datamatrix", VALUE, 240, 240, element)
    assert not painted
    assert zxingcpp.read_barcode(image.convert("L")).bytes.decode("ascii") == build_gs1(parse_gs1(VALUE)).payload


def test_small_box_and_invalid_characters_are_rejected_without_data_loss():
    element = _element("qr", VALUE, 0, 0, 10, 10, barcode_type="gs1_datamatrix")
    element["barcode_options"]["human_readable"] = True
    with pytest.raises(ValueError, match="공간"):
        _render_2d_barcode_image("gs1_datamatrix", VALUE, 35, 20, element)
    with pytest.raises(ValueError):
        _gs1_hri_lines("(01)09506000134376(10)LOT한글")
