from dataclasses import replace

import pytest
import zxingcpp

from barcode_label_automation.excel_reader import LabelRow
from barcode_label_automation.templates import default_barcode_config, render_auto_page


ROW = LabelRow(
    "00001", "SENSOR BRACKET", "001234567890", "LOT250531", 100, 1,
    source_fields=(("상품명", "SENSOR BRACKET"), ("상품코드", "00001"), ("LOT", "LOT250531"), ("수량", "100")),
)


@pytest.mark.parametrize("kind", ["code128", "qr", "datamatrix"])
def test_compact_auto_layout_keeps_all_four_fields_and_decodable_barcode(kind):
    config = replace(default_barcode_config(), barcode_type=kind)
    page = render_auto_page(ROW, 40, 20, 203, barcode_config=config, language="tspl")
    layout = page.info["automatic_layout"]

    assert len(layout["fields"]) == 4
    assert all(value in "\n".join(layout["fields"]) for value in ("SENSOR BRACKET", "00001", "LOT250531", "100"))
    assert layout["font_pt"] >= 5
    x, y, width, height = layout["symbol_bounds"]
    assert 0 <= x < x + width <= page.width
    assert 0 <= y < y + height <= page.height
    assert any(code.text == ROW.barcode for code in zxingcpp.read_barcodes(page))


def test_compact_auto_layout_rejects_content_that_cannot_fit_at_five_points():
    row = replace(ROW, source_fields=tuple((str(index), "value") for index in range(40)))
    with pytest.raises(ValueError, match="5pt"):
        render_auto_page(row, 40, 20, 203, language="tspl")
