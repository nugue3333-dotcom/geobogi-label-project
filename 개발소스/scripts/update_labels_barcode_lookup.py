from __future__ import annotations

import shutil
import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

import pythoncom
import win32com.client
from pywintypes import com_error

from barcode_db_sheet import ensure_barcode_db_sheet
from style_customer_labels_xlsm import _style_sheet


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_DIR_NAME = "\uace0\uac1d\uc6a9_\uc2e4\ud589\ud3f4\ub354"
DEFAULT_WORKBOOKS = (
    PROJECT_ROOT / "labels.xlsm",
    PROJECT_ROOT / CUSTOMER_DIR_NAME / "labels.xlsm",
)
MACRO_MODULE = PROJECT_ROOT / "excel_macro" / "modBarcodePrint_ascii.bas"
SHEET_EVENT_MODULE = PROJECT_ROOT / "excel_macro" / "LabelsWorksheetChange_ascii.bas"
WORKBOOK_EVENT_MODULE = PROJECT_ROOT / "excel_macro" / "ThisWorkbookOpen_ascii.bas"


def main() -> int:
    parser = ArgumentParser(description="Add barcode DB lookup macro to labels.xlsm.")
    parser.add_argument("workbooks", nargs="*", type=Path, default=list(DEFAULT_WORKBOOKS))
    args = parser.parse_args()

    missing = [path for path in (MACRO_MODULE, SHEET_EVENT_MODULE, WORKBOOK_EVENT_MODULE) if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing required macro file: {path}", file=sys.stderr)
        return 1

    pythoncom.CoInitialize()
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    try:
        for workbook_path in args.workbooks:
            if not workbook_path.exists():
                print(f"Skip missing workbook: {workbook_path}")
                continue
            _update_workbook(excel, workbook_path)
        return 0
    except (com_error, RuntimeError) as exc:
        print(f"Excel update error: {exc}", file=sys.stderr)
        print(
            "If VBA update is blocked, enable Excel Trust Center > Macro Settings > "
            "Trust access to the VBA project object model.",
            file=sys.stderr,
        )
        return 1
    finally:
        excel.Quit()
        pythoncom.CoUninitialize()


def _update_workbook(excel: object, workbook_path: Path) -> None:
    backup = workbook_path.with_name(
        f"{workbook_path.stem}.before-barcode-lookup."
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}{workbook_path.suffix}"
    )
    shutil.copy2(workbook_path, backup)
    print(f"Backup created: {backup}")

    workbook = excel.Workbooks.Open(str(workbook_path.resolve()), 0, False)
    try:
        if workbook.ReadOnly:
            raise RuntimeError(f"Workbook opened read-only: {workbook_path}")
        sheet = workbook.Worksheets("Labels")
        _style_sheet(sheet)
        ensure_barcode_db_sheet(workbook, workbook_path)
        _replace_standard_module(workbook)
        _write_sheet_event(workbook, sheet)
        _write_workbook_event(workbook)
        workbook.Save()
        print(f"Updated workbook: {workbook_path}")
    finally:
        workbook.Close(SaveChanges=False)


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
