param(
    [string]$DesignerExe = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DesignerExe)) {
    $designerBaseName = -join ([char[]](0xB77C, 0xBCA8, 0xB514, 0xC790, 0xC774, 0xB108))
    $DesignerExe = Join-Path $PSScriptRoot ($designerBaseName + ".exe")
}

if (-not (Test-Path -LiteralPath $DesignerExe)) {
    throw "Label designer executable was not found: $DesignerExe"
}

$exePath = (Resolve-Path -LiteralPath $DesignerExe).Path
$installDir = Split-Path -Parent $exePath
$iconSource = Join-Path $installDir "assets\brand\chaeumlab_label_file_icon_white.ico"
$localAppData = $env:LOCALAPPDATA
if ([string]::IsNullOrWhiteSpace($localAppData)) {
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
}
$iconDirectory = Join-Path $localAppData "ChaeumLAB\icons"
$fileIconPath = $null
if (Test-Path -LiteralPath $iconSource) {
    $iconHash = (Get-FileHash -LiteralPath $iconSource -Algorithm SHA256).Hash.Substring(0, 12).ToLowerInvariant()
    $fileIconPath = Join-Path $iconDirectory ("chaeumlab_label_file_{0}.ico" -f $iconHash)
    New-Item -ItemType Directory -Path $iconDirectory -Force | Out-Null
    Copy-Item -LiteralPath $iconSource -Destination $fileIconPath -Force
}
if ([string]::IsNullOrWhiteSpace($fileIconPath) -or -not (Test-Path -LiteralPath $fileIconPath)) {
    $fileIconPath = $exePath
}
$progId = "ChaeumLAB.LabelFile"
$classesRoot = "HKCU:\Software\Classes"
$extensionKey = Join-Path $classesRoot ".gblabel"
$progKey = Join-Path $classesRoot $progId
$legacyProgId = "Geobogi" + "Dream.LabelFile"

Remove-Item -Path (Join-Path $classesRoot $legacyProgId) -Recurse -Force -ErrorAction SilentlyContinue
$openWithProgIds = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.gblabel\OpenWithProgids"
if (Test-Path -Path $openWithProgIds) {
    Remove-ItemProperty -Path $openWithProgIds -Name $legacyProgId -Force -ErrorAction SilentlyContinue
}

New-Item -Path $extensionKey -Force | Out-Null
Set-Item -Path $extensionKey -Value $progId

New-Item -Path $progKey -Force | Out-Null
Set-Item -Path $progKey -Value "채움랩 라벨 파일"

$iconKey = Join-Path $progKey "DefaultIcon"
New-Item -Path $iconKey -Force | Out-Null
Set-Item -Path $iconKey -Value "`"$fileIconPath`",0"

$openCommandKey = Join-Path $progKey "shell\open\command"
New-Item -Path $openCommandKey -Force | Out-Null
Set-Item -Path $openCommandKey -Value "`"$exePath`" `"%1`""

$printCommandKey = Join-Path $progKey "shell\print\command"
New-Item -Path $printCommandKey -Force | Out-Null
Set-Item -Path $printCommandKey -Value "`"$exePath`" --print `"%1`""

New-Item -Path $openWithProgIds -Force | Out-Null
New-ItemProperty -Path $openWithProgIds -Name $progId -PropertyType Binary -Value ([byte[]]@()) -Force | Out-Null

$systemRoot = $env:SystemRoot
if ([string]::IsNullOrWhiteSpace($systemRoot)) {
    $systemRoot = [Environment]::GetEnvironmentVariable("SystemRoot", "Machine")
}
if ([string]::IsNullOrWhiteSpace($systemRoot)) {
    $systemRoot = [Environment]::GetEnvironmentVariable("WINDIR", "Machine")
}
if ([string]::IsNullOrWhiteSpace($systemRoot)) {
    $systemRoot = "C:\Windows"
}
$iconRefresh = Join-Path $systemRoot "System32\ie4uinit.exe"
if (Test-Path -LiteralPath $iconRefresh) {
    try {
        Start-Process -FilePath $iconRefresh -ArgumentList "-show" -WindowStyle Hidden -Wait -ErrorAction Stop
    }
    catch {
        # The association is already complete; a locked-down shell can reject only the optional cache refresh.
        Write-Verbose "Explorer icon cache refresh was skipped: $($_.Exception.Message)"
    }
}

Write-Host ".gblabel file association registered."
Write-Host "File icon    : `"$fileIconPath`""
Write-Host "Open command : `"$exePath`" `"%1`""
Write-Host "Print command: `"$exePath`" --print `"%1`""
