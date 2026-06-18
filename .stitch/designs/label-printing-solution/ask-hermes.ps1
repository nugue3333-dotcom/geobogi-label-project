param(
  [Parameter(Mandatory=$true)]
  [string]$Prompt
)

$ErrorActionPreference = "Stop"

chcp 65001 | Out-Null
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$agentDir = Join-Path $PSScriptRoot ".agent"
New-Item -ItemType Directory -Force -Path $agentDir | Out-Null

$outFile = Join-Path $agentDir "hermes-last.md"

$hermesCmd = $null

$cmd = Get-Command "hermes" -ErrorAction SilentlyContinue
if ($cmd) {
  $hermesCmd = $cmd.Source
}

if (-not $hermesCmd) {
  $searchRoots = @(
    "$env:LOCALAPPDATA\hermes",
    "$env:APPDATA\npm",
    "$env:LOCALAPPDATA\Programs"
  ) | Where-Object { Test-Path $_ }

  $found = foreach ($root in $searchRoots) {
    Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -in @("hermes.exe", "hermes.cmd", "hermes.bat") } |
      Select-Object -ExpandProperty FullName
  }

  $hermesCmd = $found | Select-Object -First 1
}

if (-not $hermesCmd) {
  throw "Hermes CLI를 찾지 못했습니다. 새 PowerShell에서 hermes --version 먼저 확인하세요."
}

$result = & $hermesCmd -z $Prompt 2>&1

$result | Out-File -FilePath $outFile -Encoding utf8

Write-Output $result