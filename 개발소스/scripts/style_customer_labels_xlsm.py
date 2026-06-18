from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pythoncom
import win32com.client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_DIR_NAME = "\uace0\uac1d\uc6a9_\uc2e4\ud589\ud3f4\ub354"
WORKBOOK_PATH = PROJECT_ROOT / CUSTOMER_DIR_NAME / "labels.xlsm"
FONT_NAME = "Malgun Gothic"
PRINT_BUTTON_TEXT = "\ub77c\ubca8 \ucd9c\ub825"
PRINT_QTY_ERROR = "print_qty\ub294 1\ubd80\ud130 100\uae4c\uc9c0 \uc785\ub825\ud558\uc138\uc694."


def rgb(red: int, green: int, blue: int) -> int:
    return red + (green * 256) + (blue * 65536)


def main() -> int:
    if WORKBOOK_PATH.exists():
        backup = WORKBOOK_PATH.with_name(
            f"labels.before-design.{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsm"
        )
        shutil.copy2(WORKBOOK_PATH, backup)
        print(f"Backup created: {backup}")

    pythoncom.CoInitialize()
    excel = None
    workbook = None
    owns_excel = False
    try:
        workbook = _find_open_workbook(WORKBOOK_PATH)
        if workbook is None:
            excel = win32com.client.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            workbook = excel.Workbooks.Open(str(WORKBOOK_PATH.resolve()))
            owns_excel = True
        else:
            excel = workbook.Application

        sheet = workbook.Worksheets("Labels")
        sheet.Activate()
        _style_sheet(sheet)
        workbook.Save()

        if owns_excel:
            workbook.Close(False)
            excel.Quit()
        print(f"Styled workbook: {WORKBOOK_PATH}")
        return 0
    finally:
        pythoncom.CoUninitialize()


def _style_sheet(sheet) -> None:
    app = sheet.Application

    sheet.Cells.Font.Name = FONT_NAME
    sheet.Cells.Font.Size = 10
    sheet.Cells.Interior.Color = rgb(245, 247, 250)
    sheet.Tab.Color = rgb(225, 29, 72)

    _clear_right_workspace(sheet)
    _style_table(sheet)
    _replace_print_button(sheet)

    try:
        sheet.Range("A2").Select()
        app.ActiveWindow.DisplayGridlines = False
        app.ActiveWindow.Zoom = 100
        app.ActiveWindow.FreezePanes = False
        app.ActiveWindow.SplitRow = 1
        app.ActiveWindow.SplitColumn = 0
        app.ActiveWindow.FreezePanes = True
    except Exception:
        pass


def _style_table(sheet) -> None:
    sheet.Rows("1:1").RowHeight = 32
    sheet.Rows("2:200").RowHeight = 25

    widths = (15, 26, 21, 18, 10, 12)
    for column, width in enumerate(widths, start=1):
        sheet.Columns(column).ColumnWidth = width

    header = sheet.Range("A1:F1")
    header.Interior.Color = rgb(17, 24, 39)
    header.Font.Color = rgb(255, 255, 255)
    header.Font.Bold = True
    header.Font.Size = 10
    header.HorizontalAlignment = -4108
    header.VerticalAlignment = -4108

    body = sheet.Range("A2:F200")
    body.Interior.Color = rgb(255, 255, 255)
    body.VerticalAlignment = -4108
    body.Borders.LineStyle = 1
    body.Borders.Weight = 2

    for row in range(2, 201):
        if row % 2 == 0:
            sheet.Range(f"A{row}:F{row}").Interior.Color = rgb(249, 250, 251)

    table = sheet.Range("A1:F200")
    table.Borders.LineStyle = 1
    table.Borders.Color = rgb(226, 232, 240)
    sheet.Range("A1:F1").Borders(4).Color = rgb(225, 29, 72)
    sheet.Range("A1:F1").Borders(4).Weight = 3

    sheet.Columns("E:F").HorizontalAlignment = -4152
    sheet.Columns("A:D").HorizontalAlignment = -4131
    sheet.Columns("A:D").NumberFormat = "@"
    sheet.Columns("E:F").NumberFormat = "0"

    try:
        if sheet.AutoFilterMode:
            sheet.AutoFilterMode = False
        sheet.Range("A1:F200").AutoFilter()
    except Exception:
        pass

    try:
        validation = sheet.Range("F2:F500").Validation
        validation.Delete()
        validation.Add(Type=1, AlertStyle=1, Operator=1, Formula1="1", Formula2="100")
        validation.IgnoreBlank = True
        validation.InCellDropdown = True
        validation.ErrorTitle = "print_qty"
        validation.ErrorMessage = PRINT_QTY_ERROR
    except Exception:
        pass


def _clear_right_workspace(sheet) -> None:
    sheet.Columns("G:G").ColumnWidth = 3
    sheet.Columns("H:M").ColumnWidth = 12
    sheet.Columns("N:Q").ColumnWidth = 3
    sheet.Rows("1:3").RowHeight = 34
    sheet.Rows("4:20").RowHeight = 24

    workspace = sheet.Range("H1:M20")
    workspace.UnMerge()
    workspace.Clear()
    workspace.Interior.Color = rgb(245, 247, 250)


def _replace_print_button(sheet) -> None:
    for index in range(sheet.Shapes.Count, 0, -1):
        shape = sheet.Shapes.Item(index)
        if str(shape.Name).startswith("btn"):
            shape.Delete()

    target = sheet.Range("H1:M3")
    button = sheet.Shapes.AddShape(
        5,
        target.Left + 6,
        target.Top + 6,
        target.Width - 12,
        target.Height - 12,
    )
    button.Name = "btnPrintLabels"
    button.OnAction = "PrintLabels"
    button.AlternativeText = "Print labels"
    button.Fill.ForeColor.RGB = rgb(225, 29, 72)
    button.Line.ForeColor.RGB = rgb(190, 18, 60)
    button.Line.Weight = 1.5
    button.TextFrame2.TextRange.Text = PRINT_BUTTON_TEXT
    button.TextFrame2.TextRange.Font.Name = FONT_NAME
    button.TextFrame2.TextRange.Font.Bold = True
    button.TextFrame2.TextRange.Font.Size = 20
    button.TextFrame2.TextRange.Font.Fill.ForeColor.RGB = rgb(255, 255, 255)
    button.TextFrame2.TextRange.ParagraphFormat.Alignment = 2
    button.TextFrame2.VerticalAnchor = 3
    try:
        button.Shadow.Visible = True
        button.Shadow.ForeColor.RGB = rgb(148, 163, 184)
        button.Shadow.Transparency = 0.65
        button.Shadow.OffsetX = 0
        button.Shadow.OffsetY = 3
    except Exception:
        pass
    button.Placement = 1


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
