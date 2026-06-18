Option Explicit

Private Sub Worksheet_Change(ByVal Target As Range)
    On Error GoTo EH

    Dim barcodeCol As Long
    Dim changed As Range
    Dim cell As Range

    barcodeCol = modBarcodePrint.HeaderCol(Me, "barcode")
    If barcodeCol = 0 Then
        Exit Sub
    End If

    Set changed = Intersect(Target, Me.Columns(barcodeCol))
    If changed Is Nothing Then
        Exit Sub
    End If

    Application.EnableEvents = False

    For Each cell In changed.Cells
        If cell.Row >= 2 Then
            modBarcodePrint.LookupBarcodeForCell cell
        End If
    Next cell

CleanUp:
    Application.EnableEvents = True
    Exit Sub

EH:
    Application.EnableEvents = True
    MsgBox "Barcode scan event error." & vbCrLf & Err.Description, vbCritical
End Sub
