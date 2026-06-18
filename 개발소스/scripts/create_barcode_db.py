from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_DIR_NAME = "\uace0\uac1d\uc6a9_\uc2e4\ud589\ud3f4\ub354"
OUTPUTS = (
    PROJECT_ROOT / "barcode_db.xlsx",
)
HEADERS = ("barcode", "item_code", "item_name", "lot_no", "qty", "print_qty")
SAMPLE_ROWS = (
    ("A1001-250531", "A1001", "SENSOR BRACKET", "LOT250531", 100, 1),
    ("A1001-250532", "A1002", "SENSOR BRACKET", "LOT250532", 100, 2),
    ("A1001-250533", "A1003", "SENSOR BRACKET", "LOT250533", 100, 3),
    ("A1001-250534", "A1004", "SENSOR BRACKET", "LOT250534", 100, 4),
)


def main() -> int:
    for output in OUTPUTS:
        output.parent.mkdir(parents=True, exist_ok=True)
        create_db(output)
        print(f"created: {output}")
    return 0


def create_db(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BarcodeDB"

    for col, header in enumerate(HEADERS, start=1):
        sheet.cell(row=1, column=col, value=header)

    for row_index, row in enumerate(SAMPLE_ROWS, start=2):
        for col, value in enumerate(row, start=1):
            sheet.cell(row=row_index, column=col, value=value)

    _style(sheet)
    workbook.save(path)


def _style(sheet) -> None:
    header_fill = PatternFill("solid", fgColor="111827")
    body_fill = PatternFill("solid", fgColor="FFFFFF")
    alt_fill = PatternFill("solid", fgColor="F9FAFB")
    thin = Side(style="thin", color="E2E8F0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    widths = (22, 15, 28, 18, 10, 12)
    for col, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(col)].width = width

    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = Font(name="Malgun Gothic", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    for row in sheet.iter_rows(min_row=2, max_row=200, min_col=1, max_col=len(HEADERS)):
        fill = alt_fill if row[0].row % 2 == 0 else body_fill
        for cell in row:
            cell.fill = fill
            cell.font = Font(name="Malgun Gothic", size=10, color="111827")
            cell.alignment = Alignment(vertical="center")
            cell.border = border

    for col in ("A", "B", "C", "D"):
        for cell in sheet[col]:
            cell.number_format = "@"
    for col in ("E", "F"):
        for cell in sheet[col]:
            cell.number_format = "0"

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:F200"


if __name__ == "__main__":
    raise SystemExit(main())
