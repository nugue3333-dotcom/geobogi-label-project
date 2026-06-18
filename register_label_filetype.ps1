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
$progId = "GeobogiDream.LabelFile"
$classesRoot = "HKCU:\Software\Classes"
$extensionKey = Join-Path $classesRoot ".gblabel"
$progKey = Join-Path $classesRoot $progId

New-Item -Path $extensionKey -Force | Out-Null
Set-Item -Path $extensionKey -Value $progId

New-Item -Path $progKey -Force | Out-Null
Set-Item -Path $progKey -Value "Geobogi Dream Label File"

$iconKey = Join-Path $progKey "DefaultIcon"
New-Item -Path $iconKey -Force | Out-Null
Set-Item -Path $iconKey -Value "`"$exePath`",0"

$openCommandKey = Join-Path $progKey "shell\open\command"
New-Item -Path $openCommandKey -Force | Out-Null
Set-Item -Path $openCommandKey -Value "`"$exePath`" `"%1`""

$printCommandKey = Join-Path $progKey "shell\print\command"
New-Item -Path $printCommandKey -Force | Out-Null
Set-Item -Path $printCommandKey -Value "`"$exePath`" --print `"%1`""

Write-Host ".gblabel file association registered."
Write-Host "Open command : `"$exePath`" `"%1`""
Write-Host "Print command: `"$exePath`" --print `"%1`""
