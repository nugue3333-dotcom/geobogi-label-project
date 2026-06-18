from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook, load_workbook


LABEL_HEADERS = ("item_code", "item_name", "barcode", "lot_no", "qty", "print_qty")
DB_HEADERS = ("barcode", "item_code", "item_name", "lot_no", "qty", "print_qty")


@dataclass(frozen=True)
class BarcodeLookupResult:
    barcode: str
    item_code: str
    item_name: str
    lot_no: str
    qty: str
    print_qty: str


def load_label_rows(path: str | Path) -> list[dict[str, str]]:
    return load_table(path, LABEL_HEADERS, sheet_name="Labels")


def save_label_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    save_table(path, LABEL_HEADERS, rows, sheet_name="Labels")


def load_db_rows(path: str | Path) -> list[dict[str, str]]:
    rows = load_table(path, DB_HEADERS, sheet_name="BarcodeDB", sample_rows=_sample_db_rows())
    return rows


def save_db_rows(path: str | Path, rows: list[dict[str, str]]) -> None:
    save_table(path, DB_HEADERS, rows, sheet_name="BarcodeDB")


def lookup_barcode(db_rows: list[dict[str, str]], barcode: str) -> BarcodeLookupResult | None:
    target = str(barcode).strip()
    if not target:
        return None
    for row in db_rows:
        if str(row.get("barcode", "")).strip() == target:
            return BarcodeLookupResult(
                barcode=target,
                item_code=str(row.get("item_code", "")).strip(),
                item_name=str(row.get("item_name", "")).strip(),
                lot_no=str(row.get("lot_no", "")).strip(),
                qty=str(row.get("qty", "")).strip(),
                print_qty=str(row.get("print_qty", "")).strip() or "1",
            )
    return None


def load_table(
    path: str | Path,
    headers: tuple[str, ...],
    sheet_name: str,
    sample_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    workbook_path = Path(path)
    if not workbook_path.exists():
        save_table(workbook_path, headers, sample_rows or [], sheet_name=sheet_name)

    workbook = load_workbook(workbook_path, data_only=True)
    try:
        sheet = workbook[sheet_name] if sheet_name in workbook.sheetnames else workbook.active
        header_map = _header_map(sheet, headers)
        rows: list[dict[str, str]] = []
        for row_number in range(2, sheet.max_row + 1):
            row = {header: _cell_text(sheet.cell(row_number, header_map[header]).value) for header in headers}
            if any(value.strip() for value in row.values()):
                rows.append(row)
        return rows
    finally:
        workbook.close()


def save_table(path: str | Path, headers: tuple[str, ...], rows: list[dict[str, str]], sheet_name: str) -> None:
    workbook_path = Path(path)
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(list(headers))

    for row in rows:
        if not any(str(row.get(header, "")).strip() for header in headers):
            continue
        sheet.append([str(row.get(header, "")).strip() for header in headers])

    for column_index, header in enumerate(headers, start=1):
        width = 28 if header in {"item_name", "barcode"} else 16
        sheet.column_dimensions[sheet.cell(1, column_index).column_letter].width = width
        font = copy(sheet.cell(1, column_index).font)
        font.bold = True
        sheet.cell(1, column_index).font = font
    for column_index in range(1, min(4, len(headers)) + 1):
        for row_index in range(1, sheet.max_row + 1):
            sheet.cell(row_index, column_index).number_format = "@"
    workbook.save(workbook_path)


def _header_map(sheet: object, expected_headers: tuple[str, ...]) -> dict[str, int]:
    found: dict[str, int] = {}
    for column_index, cell in enumerate(sheet[1], start=1):
        value = _cell_text(cell.value)
        if value:
            found[value] = column_index
    missing = [header for header in expected_headers if header not in found]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    return {header: found[header] for header in expected_headers}


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _sample_db_rows() -> list[dict[str, str]]:
    values = [
        ("88023502", "A1001", "SENSOR BRACKET", "LOT250531", "100", "1"),
        ("5J3P7YAYWXL5", "A1002", "SENSOR BRACKET", "LOT250532", "100", "2"),
        ("A1001-250533", "A1003", "SENSOR BRACKET", "LOT250533", "100", "3"),
        ("A1001-250534", "A1004", "SENSOR BRACKET", "LOT250534", "100", "4"),
        ("KOR-TEST-001", "K1001", "\ud55c\uae00\ud488\ubaa9\ud14c\uc2a4\ud2b8", "LOT-HANGUL", "10", "1"),
    ]
    return [dict(zip(DB_HEADERS, row, strict=True)) for row in values]
