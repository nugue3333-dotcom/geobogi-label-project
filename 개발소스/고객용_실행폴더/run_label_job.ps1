param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("DryRun", "Print", "OpenOutputFolder", "OpenLastRunLog")]
    [string]$Mode,

    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalAppDataDir = [Environment]::GetFolderPath("LocalApplicationData")
if ([string]::IsNullOrWhiteSpace($LocalAppDataDir)) {
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $LocalAppDataDir = Join-Path $env:USERPROFILE "AppData\Local"
    }
    elseif (-not [string]::IsNullOrWhiteSpace($env:PUBLIC)) {
        $LocalAppDataDir = Join-Path $env:PUBLIC "Documents"
    }
    elseif (-not [string]::IsNullOrWhiteSpace($env:SystemDrive)) {
        $LocalAppDataDir = Join-Path $env:SystemDrive "Users\Public\Documents"
    }
    else {
        $LocalAppDataDir = "C:\Users\Public\Documents"
    }
}
$UserDataDir = Join-Path (Join-Path $LocalAppDataDir "ChaeumLAB") "LabelPrint"
$LegacyUserDataDir = Join-Path $LocalAppDataDir "GeobogiLabel"

function Test-RestrictedInstallDir {
    param([string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
    $programRoots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramW6432) |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($root in $programRoots) {
        $rootPath = [System.IO.Path]::GetFullPath($root).TrimEnd("\")
        if ($resolved.StartsWith($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    try {
        $probe = Join-Path $Path (".write_probe_" + [Guid]::NewGuid().ToString("N") + ".tmp")
        Set-Content -LiteralPath $probe -Value "ok" -Encoding UTF8
        Remove-Item -LiteralPath $probe -Force
        return $false
    }
    catch {
        return $true
    }
}

function Initialize-UserDataDir {
    if ((-not (Test-Path -LiteralPath $UserDataDir)) -and (Test-Path -LiteralPath $LegacyUserDataDir)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $UserDataDir) | Out-Null
        Copy-Item -LiteralPath $LegacyUserDataDir -Destination $UserDataDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $UserDataDir | Out-Null
    foreach ($fileName in @("config.ini", "config.example.ini", "barcode_db.xlsx", "print_queue.xlsx", "labels.xlsm", "sample_direct_open.gblabel")) {
        $source = Join-Path $InstallDir $fileName
        $target = Join-Path $UserDataDir $fileName
        if ((Test-Path -LiteralPath $source) -and -not (Test-Path -LiteralPath $target)) {
            Copy-Item -LiteralPath $source -Destination $target -Force
        }
    }
    foreach ($dirName in @("templates", "db", "assets", "tools")) {
        $source = Join-Path $InstallDir $dirName
        $target = Join-Path $UserDataDir $dirName
        if ((Test-Path -LiteralPath $source) -and -not (Test-Path -LiteralPath $target)) {
            Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
        }
    }
}

if (Test-RestrictedInstallDir $InstallDir) {
    Initialize-UserDataDir
    $BaseDir = $UserDataDir
}
else {
    $BaseDir = $InstallDir
}

$QueuePath = Join-Path $BaseDir "print_queue.xlsx"
$ConfigPath = Join-Path $BaseDir "config.ini"
$ExePath = Join-Path $InstallDir "라벨출력엔진.exe"
$LogPath = Join-Path $BaseDir "last_run.log"
$OutputDir = Join-Path $BaseDir "out"
$script:OpenedLabelsWorkbook = $false

function Show-Message {
    param(
        [string]$Text,
        [string]$Title = "채움랩 라벨 출력",
        [string]$Icon = "Information"
    )

    if ($Quiet) {
        Write-Output $Text
        return
    }

    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        $Title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::$Icon
    ) | Out-Null
}

function Ask-YesNo {
    param([string]$Text)

    Add-Type -AssemblyName System.Windows.Forms
    $result = [System.Windows.Forms.MessageBox]::Show(
        $Text,
        "채움랩 라벨 출력",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    return $result -eq [System.Windows.Forms.DialogResult]::Yes
}

function Release-ComObject {
    param([object]$Object)

    if ($null -ne $Object) {
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($Object) | Out-Null
    }
}

function Set-CellValue {
    param(
        [object]$Cell,
        [object]$Value
    )

    if ($null -eq $Value) {
        $Cell.Value2 = ""
        return
    }

    if ($Value -is [double] -or $Value -is [int] -or $Value -is [long] -or $Value -is [decimal]) {
        $Cell.Value2 = [double]$Value
        return
    }

    $Cell.Value2 = [string]$Value
}

function Get-ExcelApplication {
    try {
        return [System.Runtime.InteropServices.Marshal]::GetActiveObject("Excel.Application")
    }
    catch {
        $excel = New-Object -ComObject Excel.Application
        $excel.Visible = $true
        return $excel
    }
}

function Get-LabelsWorkbook {
    param([object]$Excel)

    $targets = @(
        (Join-Path $BaseDir "labels.xlsm"),
        (Join-Path $BaseDir "labels.xlsx")
    )

    foreach ($workbook in @($Excel.Workbooks)) {
        foreach ($target in $targets) {
            if ([string]::Equals($workbook.FullName, $target, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $workbook
            }
        }
    }

    foreach ($target in $targets) {
        if (Test-Path -LiteralPath $target) {
            $script:OpenedLabelsWorkbook = $true
            return $Excel.Workbooks.Open($target)
        }
    }

    throw "labels.xlsx 또는 labels.xlsm 파일을 찾을 수 없습니다."
}

function Get-HeaderMap {
    param([object]$Worksheet)

    $headers = @{}
    $lastColumn = $Worksheet.Cells.Item(1, $Worksheet.Columns.Count).End(-4159).Column
    for ($column = 1; $column -le $lastColumn; $column += 1) {
        $header = [string]$Worksheet.Cells.Item(1, $column).Value2
        if (-not [string]::IsNullOrWhiteSpace($header)) {
            $headers[$header.Trim()] = $column
        }
    }
    return $headers
}

function Get-TargetRows {
    param(
        [object]$Excel,
        [object]$Workbook,
        [object]$Worksheet
    )

    $rows = New-Object "System.Collections.Generic.SortedSet[int]"

    try {
        $selection = $Excel.Selection
        if ($null -ne $selection -and $selection.Worksheet.Parent.FullName -eq $Workbook.FullName) {
            foreach ($area in @($selection.Areas)) {
                foreach ($row in @($area.Rows)) {
                    if ($row.Row -gt 1) {
                        [void]$rows.Add([int]$row.Row)
                    }
                }
            }
        }
    }
    catch {
    }

    if ($rows.Count -eq 0) {
        try {
            $activeCell = $Excel.ActiveCell
            if ($null -ne $activeCell -and $activeCell.Worksheet.Parent.FullName -eq $Workbook.FullName -and $activeCell.Row -gt 1) {
                [void]$rows.Add([int]$activeCell.Row)
            }
        }
        catch {
        }
    }

    if ($rows.Count -eq 0) {
        $lastRow = $Worksheet.Cells.Item($Worksheet.Rows.Count, 1).End(-4162).Row
        if ($lastRow -ge 2) {
            [void]$rows.Add(2)
        }
    }

    return $rows
}

function Export-PrintQueue {
    $excel = Get-ExcelApplication
    $queueWorkbook = $null
    $labelsWorkbook = $null

    try {
        $labelsWorkbook = Get-LabelsWorkbook -Excel $excel
        $labelsSheet = $labelsWorkbook.ActiveSheet
        if ($null -eq $labelsSheet) {
            $labelsSheet = $labelsWorkbook.Worksheets.Item(1)
        }

        $headers = Get-HeaderMap -Worksheet $labelsSheet
        $required = @("item_code", "item_name", "barcode", "lot_no", "qty", "print_qty")
        $missing = @($required | Where-Object { -not $headers.ContainsKey($_) })
        if ($missing.Count -gt 0) {
            throw "필수 컬럼이 없습니다.`r`n`r`n- $($missing -join "`r`n- ")"
        }

        $rows = New-Object "System.Collections.Generic.SortedSet[int]"
        $lastRow = 1
        foreach ($headerName in $required) {
            $column = $headers[$headerName]
            $candidate = $labelsSheet.Cells.Item($labelsSheet.Rows.Count, $column).End(-4162).Row
            if ($candidate -gt $lastRow) {
                $lastRow = $candidate
            }
        }

        for ($rowNumber = 2; $rowNumber -le $lastRow; $rowNumber += 1) {
            [void]$rows.Add([int]$rowNumber)
        }

        if ($rows.Count -eq 0) {
            throw "출력할 데이터 행을 찾지 못했습니다."
        }

        if (Test-Path -LiteralPath $QueuePath) {
            Remove-Item -LiteralPath $QueuePath -Force
        }

        $queueWorkbook = $excel.Workbooks.Add()
        $queueSheet = $queueWorkbook.Worksheets.Item(1)
        $queueSheet.Name = "Labels"

        for ($column = 1; $column -le $required.Count; $column += 1) {
            Set-CellValue -Cell ($queueSheet.Cells.Item(1, $column)) -Value ($required[$column - 1])
        }

        $outRow = 2
        foreach ($rowNumber in $rows) {
            $barcode = [string]$labelsSheet.Cells.Item($rowNumber, $headers["barcode"]).Value2
            if ([string]::IsNullOrWhiteSpace($barcode)) {
                continue
            }

            for ($column = 1; $column -le $required.Count; $column += 1) {
                $sourceColumn = $headers[$required[$column - 1]]
                Set-CellValue -Cell ($queueSheet.Cells.Item($outRow, $column)) -Value ($labelsSheet.Cells.Item($rowNumber, $sourceColumn).Value2)
            }

            $printQtyValue = [string]$queueSheet.Cells.Item($outRow, 6).Value2
            if ([string]::IsNullOrWhiteSpace($printQtyValue)) {
                Set-CellValue -Cell ($queueSheet.Cells.Item($outRow, 6)) -Value 1
            }

            $outRow += 1
        }

        if ($outRow -eq 2) {
            throw "선택한 행에 barcode 값이 없습니다."
        }

        $queueWorkbook.SaveAs($QueuePath, 51)
        $queueWorkbook.Close($false)
        $queueWorkbook = $null
    }
    finally {
        if ($null -ne $queueWorkbook) {
            $queueWorkbook.Close($false)
        }
        if ($script:OpenedLabelsWorkbook -and $null -ne $labelsWorkbook) {
            $labelsWorkbook.Close($false)
            $script:OpenedLabelsWorkbook = $false
        }
    }
}

function Invoke-Engine {
    param([string]$Argument)

    if (-not (Test-Path -LiteralPath $ExePath)) {
        throw "라벨출력엔진.exe 파일이 없습니다.`r`n$ExePath"
    }
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        throw "config.ini 파일이 없습니다.`r`n$ConfigPath"
    }

    Export-PrintQueue

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $ExePath
    $startInfo.WorkingDirectory = $BaseDir
    $startInfo.Arguments = "--config `"$ConfigPath`" $Argument"
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = [System.Diagnostics.Process]::Start($startInfo)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    Set-Content -LiteralPath $LogPath -Value ($stdout + $stderr) -Encoding UTF8

    if ($process.ExitCode -ne 0) {
        throw "실행 실패입니다. last_run.log 파일을 확인하세요.`r`n$LogPath"
    }
}

try {
    switch ($Mode) {
        "DryRun" {
            Invoke-Engine -Argument "--dry-run"
            Show-Message "출력 전 검증 완료`r`n`r`n$QueuePath`r`n$OutputDir`r`n$LogPath"
        }
        "Print" {
            if ($Quiet) {
                throw "Quiet 모드에서는 실제 출력 전송을 실행할 수 없습니다. 화면 확인 후 다시 실행하세요."
            }
            if (-not (Ask-YesNo "현재 인쇄 데이터가 실제 프린터로 전송됩니다.`r`n`r`n라벨 용지, 프린터 전원, 연결 상태, 라벨 크기를 확인한 뒤 진행하세요.")) {
                Show-Message "실제 출력 전송을 취소했습니다."
                exit 0
            }
            Invoke-Engine -Argument "--print --yes"
            Show-Message "프린터 전송 완료`r`n`r`n프린터 실제 출력 여부는 장비 상태와 라벨 배출을 확인하세요." "프린터 전송 완료"
        }
        "OpenOutputFolder" {
            if (-not (Test-Path -LiteralPath $OutputDir)) {
                New-Item -ItemType Directory -Path $OutputDir | Out-Null
            }
            Start-Process explorer.exe -ArgumentList "`"$OutputDir`""
        }
        "OpenLastRunLog" {
            if (-not (Test-Path -LiteralPath $LogPath)) {
                Show-Message "last_run.log 파일이 아직 없습니다." "채움랩 라벨 출력" "Warning"
                exit 0
            }
            Start-Process notepad.exe -ArgumentList "`"$LogPath`""
        }
    }
}
catch {
    Show-Message $_.Exception.Message "채움랩 라벨 출력 오류" "Error"
    exit 1
}
