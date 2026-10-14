[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$ResetEthernet
)

$ErrorActionPreference = "Stop"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-Check {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    try {
        & $Action
        [pscustomobject]@{ name = $Name; result = "ok"; detail = "" }
    }
    catch {
        [pscustomobject]@{ name = $Name; result = "failed"; detail = $_.Exception.Message }
    }
}

if (-not (Test-Administrator)) {
    throw "관리자 권한이 필요합니다. PowerShell을 관리자 권한으로 열어 다시 실행하세요."
}

$root = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $root "out"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$reportPath = Join-Path $outDir "network_socket_runtime_repair.txt"

"[$(Get-Date -Format s)] Windows socket runtime repair" | Set-Content -LiteralPath $reportPath -Encoding utf8
"Apply=$Apply ResetEthernet=$ResetEthernet" | Add-Content -LiteralPath $reportPath -Encoding utf8

$before = @(
    Invoke-Check -Name "dotnet_dns_before" -Action { [System.Net.Dns]::GetHostAddresses("pypi.org") | Out-Null }
    Invoke-Check -Name "socket_before" -Action {
        $client = [System.Net.Sockets.TcpClient]::new()
        $client.Connect("1.1.1.1", 443)
        $client.Dispose()
    }
)
$before | Format-Table -AutoSize | Out-String | Add-Content -LiteralPath $reportPath -Encoding utf8

if (-not $Apply) {
    Get-Content -LiteralPath $reportPath
    exit 0
}

"[$(Get-Date -Format s)] Starting component repair" | Add-Content -LiteralPath $reportPath -Encoding utf8
& dism.exe /Online /Cleanup-Image /RestoreHealth 2>&1 | Tee-Object -FilePath $reportPath -Append
$dismExit = $LASTEXITCODE
& sfc.exe /scannow 2>&1 | Tee-Object -FilePath $reportPath -Append
$sfcExit = $LASTEXITCODE

ipconfig.exe /flushdns 2>&1 | Tee-Object -FilePath $reportPath -Append
Restart-Service -Name CryptSvc -Force
Restart-Service -Name WinHttpAutoProxySvc -Force

if ($ResetEthernet) {
    $connected = Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.NetEnabled -and $_.NetConnectionID }
    foreach ($adapter in $connected) {
        netsh.exe interface set interface name="$($adapter.NetConnectionID)" admin=disabled 2>&1 | Tee-Object -FilePath $reportPath -Append
        Start-Sleep -Seconds 2
        netsh.exe interface set interface name="$($adapter.NetConnectionID)" admin=enabled 2>&1 | Tee-Object -FilePath $reportPath -Append
    }
}

Start-Sleep -Seconds 3
$after = @(
    Invoke-Check -Name "dotnet_dns_after" -Action { [System.Net.Dns]::GetHostAddresses("pypi.org") | Out-Null }
    Invoke-Check -Name "socket_after" -Action {
        $client = [System.Net.Sockets.TcpClient]::new()
        $client.Connect("1.1.1.1", 443)
        $client.Dispose()
    }
)
$after | Format-Table -AutoSize | Out-String | Add-Content -LiteralPath $reportPath -Encoding utf8
"DISM exit=$dismExit SFC exit=$sfcExit" | Add-Content -LiteralPath $reportPath -Encoding utf8
Get-Content -LiteralPath $reportPath

if ($after.result -contains "failed") {
    exit 1
}
