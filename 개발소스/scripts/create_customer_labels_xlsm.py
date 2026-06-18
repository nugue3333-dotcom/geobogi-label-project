from __future__ import annotations

import shutil
import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

try:
    import pythoncom
    import win32com.client
    from pywintypes import com_error
except ImportError as exc:  # pragma: no cover - depends on Windows COM runtime
    raise SystemExit("pywin32 is required. Install with: .\\.venv\\Scripts\\python.exe -m pip install pywin32") from exc

from barcode_db_sheet import ensure_barcode_db_sheet
from style_customer_labels_xlsm import _style_sheet


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_DIR_NAME = "\uace0\uac1d\uc6a9_\uc2e4\ud589\ud3f4\ub354"
DEFAULT_CUSTOMER_DIR = PROJECT_ROOT / CUSTOMER_DIR_NAME
MACRO_MODULE = PROJECT_ROOT / "excel_macro" / "modBarcodePrint_ascii.bas"
SHEET_EVENT_MODULE = PROJECT_ROOT / "excel_macro" / "LabelsWorksheetChange_ascii.bas"
WORKBOOK_EVENT_MODULE = PROJECT_ROOT / "excel_macro" / "ThisWorkbookOpen_ascii.bas"
HEADERS = ("item_code", "item_name", "barcode", "lot_no", "qty", "print_qty")
SAMPLE_ROWS = (
    ("A1001", "SENSOR BRACKET", "A1001-250531", "LOT250531", 100, 1),
    ("A1002", "SENSOR BRACKET", "A1001-250532", "LOT250532", 100, 2),
    ("A1003", "SENSOR BRACKET", "A1001-250533", "LOT250533", 100, 3),
    ("A1004", "SENSOR BRACKET", "A1001-250534", "LOT250534", 100, 4),
)


def main() -> int:
    parser = ArgumentParser(description="Create the customer-facing labels.xlsm workbook.")
    parser.add_argument("--output", type=Path, default=DEFAULT_CUSTOMER_DIR / "labels.xlsm")
    args = parser.parse_args()

    workbook_path = args.output
    customer_dir = workbook_path.parent
    customer_dir.mkdir(parents=True, exist_ok=True)

    missing = [path for path in (MACRO_MODULE, SHEET_EVENT_MODULE, WORKBOOK_EVENT_MODULE) if not path.exists()]
    if missing:
        for path in missing:
            print(f"Required VBA file not found: {path}", file=sys.stderr)
        return 1

    if workbook_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = customer_dir / f"labels.backup.{timestamp}.xlsm"
        try:
            shutil.copy2(workbook_path, backup_path)
            workbook_path.unlink()
            print(f"Backup created: {backup_path}")
        except OSError as exc:
            print(f"Could not replace existing labels.xlsm: {exc}", file=sys.stderr)
            print("Close labels.xlsm in Excel and run this script again.", file=sys.stderr)
            return 1

    pythoncom.CoInitialize()
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    workbook = None
    try:
        workbook = excel.Workbooks.Add()
        sheet = workbook.Worksheets(1)
        sheet.Name = "Labels"
        _write_sample_sheet(sheet)
        _style_sheet(sheet)
        ensure_barcode_db_sheet(workbook)
        _replace_standard_module(workbook)
        _write_sheet_event(workbook, sheet)
        _write_workbook_event(workbook)
        workbook.SaveAs(str(workbook_path.resolve()), FileFormat=52)
        print(f"labels.xlsm created: {workbook_path}")
        return 0
    except com_error as exc:
        print(f"Failed to create labels.xlsm: {exc}", file=sys.stderr)
        print(
            "If VBA import is blocked, enable Excel Trust Center > Macro Settings > "
            "Trust access to the VBA project object model.",
            file=sys.stderr,
        )
        return 1
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=False)
        excel.Quit()
        pythoncom.CoUninitialize()


def _write_sample_sheet(sheet: object) -> None:
    for column, value in enumerate(HEADERS, start=1):
        sheet.Cells(1, column).Value = value

    for row_index, values in enumerate(SAMPLE_ROWS, start=2):
        for column, value in enumerate(values, start=1):
            sheet.Cells(row_index, column).Value = value


def _replace_standard_module(workbook: object) -> None:
    code = _read_vba_module(MACRO_MODULE)
    components = workbook.VBProject.VBComponents
    component = _find_component(components, "modBarcodePrint")

    if component is None:
        component = components.Add(1)
        component.Name = "modBarcodePrint"

    module = component.CodeModule
    if module.CountOfLines > 0:
        module.DeleteLines(1, module.CountOfLines)
    module.AddFromString(code)


def _write_sheet_event(workbook: object, sheet: object) -> None:
    code = SHEET_EVENT_MODULE.read_text(encoding="utf-8-sig")
    module = workbook.VBProject.VBComponents(sheet.CodeName).CodeModule
    if module.CountOfLines > 0:
        module.DeleteLines(1, module.CountOfLines)
    module.AddFromString(code)


def _write_workbook_event(workbook: object) -> None:
    code = WORKBOOK_EVENT_MODULE.read_text(encoding="utf-8-sig")
    module = workbook.VBProject.VBComponents("ThisWorkbook").CodeModule
    if module.CountOfLines > 0:
        module.DeleteLines(1, module.CountOfLines)
    module.AddFromString(code)


def _find_component(components: object, name: str) -> object | None:
    for index in range(1, components.Count + 1):
        component = components.Item(index)
        if component.Name == name:
            return component
    return None


def _read_vba_module(path: Path) -> str:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    filtered = [line for line in lines if not line.startswith("Attribute VB_Name =")]
    return "\r\n".join(filtered) + "\r\n"


if __name__ == "__main__":
    raise SystemExit(main())
