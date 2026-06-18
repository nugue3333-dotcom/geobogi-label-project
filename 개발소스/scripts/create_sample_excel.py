from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook


def main() -> int:
    path = Path(__file__).resolve().parents[1] / "labels.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "labels"
    sheet.append(["item_code", "item_name", "barcode", "lot_no", "qty", "print_qty"])
    sheet.append(["ITEM-001", "Sample Widget", "8801234567890", "LOT-20260601-A", 12, 2])
    sheet.append(["ITEM-002", "Sample Bracket", "8801234567891", "LOT-20260601-B", 5, 1])
    workbook.save(path)
    print(f"Sample Excel written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
