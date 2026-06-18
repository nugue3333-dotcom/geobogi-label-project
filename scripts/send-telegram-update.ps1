#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Target = "telegram:7949317631",
    [string]$Message,
    [string]$File,
    [string]$Subject,
    [switch]$ListTargets,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
}
$env:PYTHONIOENCODING = "utf-8"

function Resolve-HermesExe {
    $localAppData = [Environment]::GetEnvironmentVariable("LOCALAPPDATA")
    if ($localAppData) {
        $preferred = Join-Path $localAppData "hermes\hermes-agent\venv\Scripts\hermes.exe"
        if (Test-Path $preferred) {
            return $preferred
        }
    }

    $fromPath = Get-Command hermes.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    throw "Hermes CLI was not found."
}

$hermes = Resolve-HermesExe

if ($ListTargets) {
    & $hermes send --list telegram --json
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($Message) -and [string]::IsNullOrWhiteSpace($File)) {
    throw "Provide -Message or -File, or use -ListTargets."
}
if (-not [string]::IsNullOrWhiteSpace($Message) -and -not [string]::IsNullOrWhiteSpace($File)) {
    throw "Use only one of -Message or -File."
}

$args = @("send", "--to", $Target)
if (-not [string]::IsNullOrWhiteSpace($Subject)) {
    $args += @("--subject", $Subject)
}

if (-not [string]::IsNullOrWhiteSpace($File)) {
    $resolved = Resolve-Path -Path $File
    $args += @("--file", $resolved.Path)
} else {
    $args += $Message
}

if ($DryRun) {
    [PSCustomObject]@{
        Hermes = $hermes
        Arguments = ($args -join " ")
        Target = $Target
        File = $File
        Subject = $Subject
    }
    exit 0
}

& $hermes @args --json
if ($LASTEXITCODE -ne 0) {
    throw "Telegram send failed with exit code $LASTEXITCODE."
}

