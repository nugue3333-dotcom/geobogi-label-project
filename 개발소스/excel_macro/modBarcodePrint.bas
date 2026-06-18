Attribute VB_Name = "modBarcodePrint"
Option Explicit

Private Const QUEUE_FILE As String = "print_queue.xlsx"

Private Function Q(ByVal value As String) As String
    Q = """" & Replace(value, """", """""") & """"
End Function

Private Function BaseFolder() As String
    BaseFolder = ThisWorkbook.Path
End Function

Private Function HeaderCol(ByVal ws As Worksheet, ByVal headerName As String) As Long
    Dim c As Range

    Set c = ws.Rows(1).Find(What:=headerName, LookIn:=xlValues, LookAt:=xlWhole)

    If c Is Nothing Then
        HeaderCol = 0
    Else
        HeaderCol = c.Column
    End If
End Function

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
        MsgBox "필수 컬럼이 없습니다." & vbCrLf & vbCrLf & missing, vbCritical
        ValidateHeaders = False
    Else
        ValidateHeaders = True
    End If
End Function

Private Function GetTargetRows(ByVal ws As Worksheet) As Object
    Dim dict As Object
    Dim cell As Range
    Dim rowNo As Long

    Set dict = CreateObject("Scripting.Dictionary")

    On Error Resume Next

    If TypeName(Selection) = "Range" Then
        For Each cell In Selection.Cells
            If cell.Worksheet.Name = ws.Name Then
                rowNo = cell.Row

                If rowNo > 1 Then
                    If Not dict.Exists(CStr(rowNo)) Then
                        dict.Add CStr(rowNo), rowNo
                    End If
                End If
            End If
        Next cell
    End If

    On Error GoTo 0

    If dict.Count = 0 Then
        If ActiveCell.Row > 1 Then
            dict.Add CStr(ActiveCell.Row), ActiveCell.Row
        End If
    End If

    Set GetTargetRows = dict
End Function

Private Function ExportPrintQueue() As Boolean
    On Error GoTo EH

    Dim src As Worksheet
    Dim wb As Workbook
    Dim dst As Worksheet
    Dim rows As Object
    Dim key As Variant
    Dim rowNo As Long
    Dim outRow As Long
    Dim lastCol As Long
    Dim barcodeCol As Long
    Dim printQtyCol As Long
    Dim outPath As String

    Set src = ActiveSheet

    If ValidateHeaders(src) = False Then
        ExportPrintQueue = False
        Exit Function
    End If

    barcodeCol = HeaderCol(src, "barcode")
    printQtyCol = HeaderCol(src, "print_qty")
    lastCol = src.Cells(1, src.Columns.Count).End(xlToLeft).Column

    Set rows = GetTargetRows(src)

    If rows.Count = 0 Then
        MsgBox "출력할 행을 먼저 선택하세요." & vbCrLf & _
               "예: 2번 행 클릭 후 라벨 출력 버튼 클릭", vbExclamation
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

    src.Range(src.Cells(1, 1), src.Cells(1, lastCol)).Copy
    dst.Cells(1, 1).PasteSpecial xlPasteValues

    outRow = 2

    For Each key In rows.Keys
        rowNo = CLng(rows(key))

        If Trim(CStr(src.Cells(rowNo, barcodeCol).Value)) <> "" Then
            src.Range(src.Cells(rowNo, 1), src.Cells(rowNo, lastCol)).Copy
            dst.Cells(outRow, 1).PasteSpecial xlPasteValues

            If Trim(CStr(dst.Cells(outRow, printQtyCol).Value)) = "" Then
                dst.Cells(outRow, printQtyCol).Value = 1
            End If

            outRow = outRow + 1
        End If
    Next key

    Application.CutCopyMode = False

    If outRow = 2 Then
        wb.Close SaveChanges:=False
        Application.DisplayAlerts = True
        MsgBox "선택한 행에 barcode 값이 없습니다.", vbExclamation
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
    MsgBox "출력용 엑셀 생성 실패" & vbCrLf & Err.Description, vbCritical
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
    exePath = folder & "\print_labels.exe"
    cfgPath = folder & "\config.ini"
    logPath = folder & "\last_run.log"

    If Len(Dir(exePath)) = 0 Then
        MsgBox "print_labels.exe 파일이 없습니다." & vbCrLf & exePath, vbCritical
        Exit Sub
    End If

    If Len(Dir(cfgPath)) = 0 Then
        MsgBox "config.ini 파일이 없습니다." & vbCrLf & cfgPath, vbCritical
        Exit Sub
    End If

    If ExportPrintQueue() = False Then
        Exit Sub
    End If

    cmd = "cmd /c cd /d " & Q(folder) & _
          " && " & Q(exePath) & _
          " --config " & Q(cfgPath) & _
          " " & args & _
          " > " & Q(logPath) & " 2>&1"

    rc = CreateObject("WScript.Shell").Run(cmd, 1, True)

    If rc <> 0 Then
        MsgBox jobName & " 실패" & vbCrLf & _
               "last_run.log 파일을 확인하세요." & vbCrLf & logPath, vbCritical
    End If

    Exit Sub

EH:
    MsgBox "매크로 실행 오류" & vbCrLf & Err.Description, vbCritical
End Sub

Public Sub DryRunLabels()
    RunEngine "--dry-run", "출력 전 검증"
End Sub

Public Sub PrintLabels()
    RunEngine "--print --yes", "라벨 출력"
End Sub

Public Sub OpenOutputFolder()
    Dim folder As String

    folder = BaseFolder() & "\out"

    If Len(Dir(folder, vbDirectory)) = 0 Then
        MsgBox "out 폴더가 아직 없습니다." & vbCrLf & _
               "먼저 출력 전 검증을 실행하세요.", vbExclamation
        Exit Sub
    End If

    Shell "explorer.exe " & Q(folder), vbNormalFocus
End Sub

Public Sub OpenLastRunLog()
    Dim logPath As String

    logPath = BaseFolder() & "\last_run.log"

    If Len(Dir(logPath)) = 0 Then
        MsgBox "last_run.log 파일이 아직 없습니다.", vbExclamation
        Exit Sub
    End If

    Shell "notepad.exe " & Q(logPath), vbNormalFocus
End Sub
