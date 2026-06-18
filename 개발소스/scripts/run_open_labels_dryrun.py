from __future__ import annotations

from pathlib import Path

import pythoncom
import win32com.client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK_PATH = PROJECT_ROOT / "고객용_실행폴더" / "labels.xlsm"


def main() -> int:
    pythoncom.CoInitialize()
    try:
        workbook = _find_open_workbook(WORKBOOK_PATH)
        owns_excel = False
        if workbook is None:
            excel = win32com.client.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            workbook = excel.Workbooks.Open(str(WORKBOOK_PATH))
            owns_excel = True
        else:
            excel = workbook.Application

        try:
            workbook.Worksheets("Labels").Activate()
            workbook.Application.Run("DryRunLabels")
            workbook.Save()
        finally:
            if owns_excel:
                workbook.Close(False)
                excel.Quit()
        print("DryRunLabels executed")
        return 0
    finally:
        pythoncom.CoUninitialize()


def _find_open_workbook(path: Path):
    target = str(path.resolve()).lower()
    rot = pythoncom.GetRunningObjectTable()
    ctx = pythoncom.CreateBindCtx(0)
    for moniker in rot.EnumRunning():
        try:
            name = moniker.GetDisplayName(ctx, None)
        except Exception:
            continue
        if name.lower() == target:
            obj = rot.GetObject(moniker)
            return win32com.client.Dispatch(obj.QueryInterface(pythoncom.IID_IDispatch))
    return None


if __name__ == "__main__":
    raise SystemExit(main())
