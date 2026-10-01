[CmdletBinding()]
param(
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$fontFileName = "MONEYGRAPHY-ROUNDED.TTF"
$fontDisplayName = "머니그라피TTF Rounded (TrueType)"
$sourcePath = Join-Path (Split-Path -Parent $PSScriptRoot) "assets\fonts\$fontFileName"
$localAppData = $env:LOCALAPPDATA
if (-not $localAppData) {
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
}
if (-not $localAppData) {
    throw "Windows 사용자 로컬 데이터 폴더를 확인할 수 없습니다."
}
$fontDirectory = Join-Path $localAppData "Microsoft\Windows\Fonts"
$destinationPath = Join-Path $fontDirectory "Moneygraphy-Rounded.ttf"
$registryPath = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts"

if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
    throw "채움랩 기본 글꼴 파일을 찾을 수 없습니다: $sourcePath"
}

New-Item -ItemType Directory -Path $fontDirectory -Force | Out-Null
$copyRequired = -not (Test-Path -LiteralPath $destinationPath -PathType Leaf)
if (-not $copyRequired) {
    $copyRequired = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash -ne `
        (Get-FileHash -LiteralPath $destinationPath -Algorithm SHA256).Hash
}
if ($copyRequired) {
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
}
if ((Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash -ne `
    (Get-FileHash -LiteralPath $destinationPath -Algorithm SHA256).Hash) {
    throw "채움랩 기본 글꼴 파일 검증에 실패했습니다."
}

New-Item -Path $registryPath -Force | Out-Null
New-ItemProperty -Path $registryPath -Name $fontDisplayName -Value $destinationPath -PropertyType String -Force | Out-Null

if (-not ("ChaeumLab.FontInstaller" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
namespace ChaeumLab {
    public static class FontInstaller {
        [DllImport("gdi32.dll", CharSet = CharSet.Unicode)]
        public static extern int AddFontResourceEx(string fileName, uint flags, IntPtr reserved);

        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern IntPtr SendMessageTimeout(
            IntPtr windowHandle,
            uint message,
            UIntPtr wParam,
            IntPtr lParam,
            uint flags,
            uint timeout,
            out UIntPtr result
        );
    }
}
"@
}

$fontAdded = [ChaeumLab.FontInstaller]::AddFontResourceEx($destinationPath, 0, [IntPtr]::Zero)
if ($fontAdded -le 0) {
    throw "Windows에 채움랩 기본 글꼴을 등록하지 못했습니다."
}
$broadcastResult = [UIntPtr]::Zero
[void][ChaeumLab.FontInstaller]::SendMessageTimeout(
    [IntPtr]0xffff,
    0x001D,
    [UIntPtr]::Zero,
    [IntPtr]::Zero,
    0x0002,
    1000,
    [ref]$broadcastResult
)

if ($Quiet) {
    Write-Output "FONT_INSTALL_OK $destinationPath"
}
else {
    Write-Host "채움랩 기본 글꼴을 설치했습니다: $destinationPath"
}
