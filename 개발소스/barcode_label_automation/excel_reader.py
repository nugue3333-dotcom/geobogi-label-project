from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


REQUIRED_COLUMNS = ("item_code", "item_name", "barcode", "lot_no", "qty", "print_qty")


@dataclass(frozen=True)
class LabelRow:
    item_code: str
    item_name: str
    barcode: str
    lot_no: str
    qty: int
    print_qty: int


def read_labels(path: str | Path) -> list[LabelRow]:
    workbook_path = Path(path)
    if not workbook_path.exists():
        raise FileNotFoundError(f"Excel file not found: {workbook_path}")

    workbook = load_workbook(workbook_path, data_only=True)
    sheet = workbook.active
    headers = _read_headers(sheet)
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    labels: list[LabelRow] = []
    for row_number in range(2, sheet.max_row + 1):
        values = {column: sheet.cell(row=row_number, column=index).value for column, index in headers.items()}
        if all(value is None or str(value).strip() == "" for value in values.values()):
            continue
        labels.append(
            LabelRow(
                item_code=_as_text(values["item_code"]),
                item_name=_as_text(values["item_name"]),
                barcode=_as_text(values["barcode"]),
                lot_no=_as_text(values["lot_no"]),
                qty=_as_positive_int(values["qty"], "qty", row_number),
                print_qty=_as_required_int(values["print_qty"], "print_qty", row_number),
            )
        )
    return labels


def _read_headers(sheet: Any) -> dict[str, int]:
    headers: dict[str, int] = {}
    for column_index, cell in enumerate(sheet[1], start=1):
        if cell.value is None:
            continue
        header = str(cell.value).strip()
        if header:
            headers[header] = column_index
    return headers


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _as_positive_int(value: object, column: str, row_number: int) -> int:
    number = _as_required_int(value, column, row_number)
    if number < 1:
        raise ValueError(f"Row {row_number}: {column} must be greater than 0")
    return number


def _as_required_int(value: object, column: str, row_number: int) -> int:
    if value is None or str(value).strip() == "":
        raise ValueError(f"Row {row_number}: {column} is required")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Row {row_number}: {column} must be an integer") from exc
    return number
