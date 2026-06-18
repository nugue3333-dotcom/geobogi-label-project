from __future__ import annotations

from openpyxl import load_workbook

from barcode_label_automation.excel_reader import LabelRow
from barcode_label_automation.logger import append_print_log


def test_print_log_includes_error_message_column(tmp_path):
    row = LabelRow(
        item_code="ITEM-001",
        item_name="Sample",
        barcode="",
        lot_no="LOT-A",
        qty=1,
        print_qty=0,
    )

    log_path = append_print_log(
        tmp_path,
        [
            {
                "label": row,
                "language": "slcs",
                "mode": "dry-run",
                "status": "skipped",
                "output_file": "",
                "error_message": "barcode is empty",
            }
        ],
    )

    workbook = load_workbook(log_path)
    sheet = workbook.active

    headers = [cell.value for cell in sheet[1]]
    assert "status" in headers
    assert "error_message" in headers
    assert sheet["H2"].value == "skipped"
    assert sheet["J2"].value == "barcode is empty"
