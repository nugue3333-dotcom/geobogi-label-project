Attribute VB_Name = "modBarcodePrint"
Option Explicit

Private Const QUEUE_FILE As String = "print_queue.xlsx"
Private Const DB_SHEET As String = "BarcodeDB"
Private Const DATA_SHEET As String = "Labels"
Private Const FIRST_COL As Long = 1
Private Const LAST_COL As Long = 6

Private Function Q(ByVal value As String) As String
    Q = """" & Replace(value, """", """""") & """"
End Function

Private Function BaseFolder() As String
    BaseFolder = ThisWorkbook.Path
End Function

Private Function DbMissingBarcodeMessage() As String
    DbMissingBarcodeMessage = "DB" & ChrW(50640) & " " & _
                              ChrW(50630) & ChrW(45716) & " " & _
                              ChrW(48148) & ChrW(53076) & ChrW(46300) & " " & _
                              ChrW(51077) & ChrW(45768) & ChrW(45796) & "."
End Function

Public Function HeaderCol(ByVal ws As Worksheet, ByVal headerName As String) As Long
    Dim c As Range

    Set c = ws.Rows(1).Find(What:=headerName, LookIn:=xlValues, LookAt:=xlWhole)

    If c Is Nothing Then
        HeaderCol = 0
    Else
        HeaderCol = c.Column
    End If
End Function

Private Function GetBarcodeDbSheet() As Worksheet
    On Error Resume Next
    Set GetBarcodeDbSheet = ThisWorkbook.Worksheets(DB_SHEET)
    On Error GoTo 0
End Function

Private Sub SetValueIfColumnsExist(ByVal targetSheet As Worksheet, ByVal targetRow As Long, ByVal targetHeader As String, ByVal dbSheet As Worksheet, ByVal dbRow As Long, ByVal dbHeader As String)
    Dim targetCol As Long
    Dim dbCol As Long

    targetCol = HeaderCol(targetSheet, targetHeader)
    dbCol = HeaderCol(dbSheet, dbHeader)

    If targetCol > 0 And dbCol > 0 Then
        targetSheet.Cells(targetRow, targetCol).Value = dbSheet.Cells(dbRow, dbCol).Value
    End If
End Sub

Public Sub LookupBarcodeForCell(ByVal barcodeCell As Range)
    On Error GoTo EH

    Dim barcodeValue As String
    Dim dbWs As Worksheet
    Dim dbBarcodeCol As Long
    Dim found As Range
    Dim targetWs As Worksheet
    Dim targetRow As Long
    Dim printQtyCol As Long

    barcodeValue = Trim(CStr(barcodeCell.Value))
    If barcodeValue = "" Then
        Exit Sub
    End If

    Set targetWs = barcodeCell.Worksheet
    targetRow = barcodeCell.Row

    Set dbWs = GetBarcodeDbSheet()
    If dbWs Is Nothing Then
        Application.StatusBar = "BarcodeDB sheet not found."
        MsgBox "BarcodeDB sheet not found in labels.xlsm.", vbExclamation
        Exit Sub
    End If

    dbBarcodeCol = HeaderCol(dbWs, "barcode")

    If dbBarcodeCol = 0 Then
        MsgBox "barcode column not found in BarcodeDB sheet.", vbCritical
        GoTo CleanUp
    End If

    Set found = dbWs.Columns(dbBarcodeCol).Find(What:=barcodeValue, LookIn:=xlValues, LookAt:=xlWhole)

    If found Is Nothing Then
        Application.StatusBar = "Barcode not found in DB: " & barcodeValue
        MsgBox DbMissingBarcodeMessage() & vbCrLf & vbCrLf & _
               "Barcode: " & barcodeValue & vbCrLf & _
               "Sheet: " & DB_SHEET, vbExclamation + vbOKOnly, "Barcode DB"
        GoTo CleanUp
    End If

    SetValueIfColumnsExist targetWs, targetRow, "item_code", dbWs, found.Row, "item_code"
    SetValueIfColumnsExist targetWs, targetRow, "item_name", dbWs, found.Row, "item_name"
    SetValueIfColumnsExist targetWs, targetRow, "lot_no", dbWs, found.Row, "lot_no"
    SetValueIfColumnsExist targetWs, targetRow, "qty", dbWs, found.Row, "qty"
    SetValueIfColumnsExist targetWs, targetRow, "print_qty", dbWs, found.Row, "print_qty"

    printQtyCol = HeaderCol(targetWs, "print_qty")
    If printQtyCol > 0 Then
        If Trim(CStr(targetWs.Cells(targetRow, printQtyCol).Value)) = "" Then
            targetWs.Cells(targetRow, printQtyCol).Value = 1
        End If
    End If

    Application.StatusBar = "Barcode loaded from DB: " & barcodeValue

CleanUp:
    Exit Sub

EH:
    Application.StatusBar = False
    MsgBox "Barcode lookup error." & vbCrLf & Err.Description, vbCritical
End Sub

Public Sub LookupBarcodeInRow(ByVal rowNo As Long)
    Dim ws As Worksheet
    Dim barcodeCol As Long

    Set ws = ThisWorkbook.Worksheets(DATA_SHEET)
    barcodeCol = HeaderCol(ws, "barcode")

    If rowNo < 2 Or barcodeCol = 0 Then
        Exit Sub
    End If

    LookupBarcodeForCell ws.Cells(rowNo, barcodeCol)
End Sub

Private Function ValidateHeaders(ByVal ws As Worksheet) As Boolean
    Dim required As Variant
    Dim i As Long
    Dim missing As String

    required = Array("item_code", "item_name", "barcode", "lot_no", "qty", "print_qty")

    For i = LBound(required) To UBound(required)
        If HeaderCol(ws, CStr(required(i))) = 0 Then
            missing = missing & "- " & CStr(required(i)) & vbCrLf
        End If
    Next i

    If Len(missing) > 0 Then
        MsgBox "Missing required columns." & vbCrLf & vbCrLf & missing, vbCritical
        ValidateHeaders = False
    Else
        ValidateHeaders = True
    End If
End Function

Private Function LastDataRow(ByVal ws As Worksheet) As Long
    Dim colNo As Long
    Dim rowNo As Long
    Dim maxRow As Long

    maxRow = 1

    For colNo = FIRST_COL To LAST_COL
        rowNo = ws.Cells(ws.Rows.Count, colNo).End(xlUp).Row
        If rowNo > maxRow Then
            maxRow = rowNo
        End If
    Next colNo

    LastDataRow = maxRow
End Function

Private Function ExportPrintQueue() As Boolean
    On Error GoTo EH

    Dim src As Worksheet
    Dim wb As Workbook
    Dim dst As Worksheet
    Dim rowNo As Long
    Dim outRow As Long
    Dim lastRow As Long
    Dim barcodeCol As Long
    Dim printQtyCol As Long
    Dim outPath As String
    Dim colNo As Long

    Set src = ThisWorkbook.Worksheets(DATA_SHEET)
    Application.Calculate
    src.Calculate

    If ValidateHeaders(src) = False Then
        ExportPrintQueue = False
        Exit Function
    End If

    barcodeCol = HeaderCol(src, "barcode")
    printQtyCol = HeaderCol(src, "print_qty")

    lastRow = LastDataRow(src)

    If lastRow < 2 Then
        MsgBox "No data rows found.", vbExclamation
        ExportPrintQueue = False
        Exit Function
    End If

    outPath = BaseFolder() & "\" & QUEUE_FILE

    Application.DisplayAlerts = False

    If Len(Dir(outPath)) > 0 Then
        Kill outPath
    End If

    Set wb = Workbooks.Add(xlWBATWorksheet)
    Set dst = wb.Worksheets(1)
    dst.Name = "Labels"

    For colNo = FIRST_COL To LAST_COL
        dst.Cells(1, colNo).Value = src.Cells(1, colNo).Value
    Next colNo

    outRow = 2

    For rowNo = 2 To lastRow
        If Trim(CStr(src.Cells(rowNo, barcodeCol).Value)) <> "" Then
            For colNo = FIRST_COL To LAST_COL
                dst.Cells(outRow, colNo).Value = src.Cells(rowNo, colNo).Value
            Next colNo

            If Trim(CStr(dst.Cells(outRow, printQtyCol).Value)) = "" Then
                dst.Cells(outRow, printQtyCol).Value = 1
            End If

            outRow = outRow + 1
        End If
    Next rowNo

    If outRow = 2 Then
        wb.Close SaveChanges:=False
        Application.DisplayAlerts = True
        MsgBox "Selected rows do not have barcode values.", vbExclamation
        ExportPrintQueue = False
        Exit Function
    End If

    wb.SaveAs Filename:=outPath, FileFormat:=xlOpenXMLWorkbook
    wb.Close SaveChanges:=False

    Application.DisplayAlerts = True

    ExportPrintQueue = True
    Exit Function

EH:
    Application.DisplayAlerts = True
    MsgBox "Failed to create print_queue.xlsx." & vbCrLf & Err.Description, vbCritical
    ExportPrintQueue = False
End Function

Private Sub RunEngine(ByVal args As String, ByVal jobName As String)
    On Error GoTo EH

    Dim folder As String
    Dim exePath As String
    Dim cfgPath As String
    Dim logPath As String
    Dim cmd As String
    Dim rc As Long

    folder = BaseFolder()
    exePath = folder & "\라벨출력엔진.exe"
    cfgPath = folder & "\config.ini"
    logPath = folder & "\last_run.log"

    If Len(Dir(exePath)) = 0 Then
        MsgBox "라벨출력엔진.exe 파일이 없습니다." & vbCrLf & exePath, vbCritical
        Exit Sub
    End If

    If Len(Dir(cfgPath)) = 0 Then
        MsgBox "config.ini not found." & vbCrLf & cfgPath, vbCritical
        Exit Sub
    End If

    If ExportPrintQueue() = False Then
        Exit Sub
    End If

    ThisWorkbook.Save

    cmd = "cmd /c cd /d " & Q(folder) & _
          " && " & Q(exePath) & _
          " --config " & Q(cfgPath) & _
          " " & args & _
          " > " & Q(logPath) & " 2>&1"

    rc = CreateObject("WScript.Shell").Run(cmd, 1, True)

    If rc <> 0 Then
        MsgBox jobName & " failed." & vbCrLf & _
               "Check last_run.log." & vbCrLf & logPath, vbCritical
    End If

    Exit Sub

EH:
    MsgBox "Macro execution error." & vbCrLf & Err.Description, vbCritical
End Sub

Public Sub DryRunLabels()
    RunEngine "--dry-run", "Dry-run"
End Sub

Public Sub PrintLabels()
    If MsgBox("The current print data will be sent to the actual printer." & vbCrLf & vbCrLf & _
              "Check label stock, printer power, connection status, and label size before continuing.", _
              vbQuestion + vbYesNo, "Confirm actual printer output") <> vbYes Then
        Exit Sub
    End If
    RunEngine "--print --yes", "Print"
End Sub

Public Sub OpenOutputFolder()
    Dim folder As String

    folder = BaseFolder() & "\out"

    If Len(Dir(folder, vbDirectory)) = 0 Then
        MsgBox "out folder does not exist. Run dry-run first.", vbExclamation
        Exit Sub
    End If

    Shell "explorer.exe " & Q(folder), vbNormalFocus
End Sub

Public Sub OpenLastRunLog()
    Dim logPath As String

    logPath = BaseFolder() & "\last_run.log"

    If Len(Dir(logPath)) = 0 Then
        MsgBox "last_run.log does not exist yet.", vbExclamation
        Exit Sub
    End If

    Shell "notepad.exe " & Q(logPath), vbNormalFocus
End Sub
