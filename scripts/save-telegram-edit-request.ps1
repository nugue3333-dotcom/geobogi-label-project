#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Message,

    [string]$OutputPath = ".agent\telegram-edit-request.md",

    [string]$Source = "telegram:7949317631"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$targetPath = Join-Path $projectRoot $OutputPath
$targetDir = Split-Path -Parent $targetPath
if (-not [string]::IsNullOrWhiteSpace($targetDir)) {
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
}

$created = Get-Date
$body = @"
# Telegram Edit Request

- Created: $($created.ToString("yyyy-MM-dd HH:mm:ss zzz"))
- Source: $Source
- Project root: $projectRoot

## Request

$Message

## Codex checklist

- Read AGENTS.md first.
- Read docs/PRODUCT_PACKAGES.md and docs/MARKETING_AUTOMATION_RULES.md before changing public copy.
- Do not add unsupported hardware compatibility, pricing, warranty, refund, shipping, or integration claims.
- Prefer dry-run or smoke-test checks before any printer-related validation.
- Update index.html, docs, or program source only after confirming the target file path.
"@

Set-Content -Path $targetPath -Value $body -Encoding UTF8
Get-Item -Path $targetPath | Select-Object FullName,Length,LastWriteTime

