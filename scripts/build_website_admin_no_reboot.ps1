[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$site = Join-Path $root "website-it-public"
$log = Join-Path $root "out\website_admin_build.log"
New-Item -ItemType Directory -Force (Split-Path -Parent $log) | Out-Null

"[$(Get-Date -Format s)] admin website build start" | Set-Content -LiteralPath $log -Encoding utf8
Set-Location -LiteralPath $site

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Command
    )

    "[$(Get-Date -Format s)] $Name" | Add-Content -LiteralPath $log -Encoding utf8
    & cmd.exe /d /s /c "$Command 1>>`"$log`" 2>&1"
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Get-Content -Tail 80 -LiteralPath $log
        throw "$Name failed: $exitCode"
    }
}

if (-not (Test-Path node_modules)) {
    Invoke-NativeStep -Name "npm ci" -Command "npm.cmd ci"
}

Invoke-NativeStep -Name "lint" -Command "npm.cmd run lint"
Invoke-NativeStep -Name "typecheck" -Command "npx.cmd tsc --noEmit"
Invoke-NativeStep -Name "build" -Command "npm.cmd run build"
Invoke-NativeStep -Name "tests" -Command "node.exe --test tests/rendered-html.test.mjs"

"[$(Get-Date -Format s)] COMPLETE" | Add-Content -LiteralPath $log -Encoding utf8
Write-Host "BUILD COMPLETE" -ForegroundColor Green
