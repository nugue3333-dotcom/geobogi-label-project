from __future__ import annotations

import pytest
from openpyxl import Workbook

from barcode_label_automation.excel_reader import read_labels


def test_read_labels_validates_and_maps_rows(tmp_path):
    path = tmp_path / "labels.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["item_code", "item_name", "barcode", "lot_no", "qty", "print_qty"])
    sheet.append(["A-1", "Name", "123456", "LOT1", 3, 2])
    workbook.save(path)

    rows = read_labels(path)

    assert len(rows) == 1
    assert rows[0].item_code == "A-1"
    assert rows[0].qty == 3
    assert rows[0].print_qty == 2


def test_read_labels_allows_print_qty_for_later_skip_validation(tmp_path):
    path = tmp_path / "labels.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["item_code", "item_name", "barcode", "lot_no", "qty", "print_qty"])
    sheet.append(["A-1", "Name", "123456", "LOT1", 3, 0])
    workbook.save(path)

    rows = read_labels(path)

    assert rows[0].print_qty == 0


def test_read_labels_reports_missing_required_columns(tmp_path):
    path = tmp_path / "labels.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["item_code"])
    workbook.save(path)

    with pytest.raises(ValueError, match="Missing required columns"):
        read_labels(path)
