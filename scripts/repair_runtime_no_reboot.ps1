[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $root "out\network_runtime_no_reboot.log"
New-Item -ItemType Directory -Force (Split-Path -Parent $log) | Out-Null

"[$(Get-Date -Format s)] no-reboot runtime repair start" | Set-Content -LiteralPath $log -Encoding utf8

try {
    Stop-Service -Name CryptSvc -Force -ErrorAction Stop
    Start-Service -Name CryptSvc -ErrorAction Stop
    "CryptSvc restarted" | Add-Content -LiteralPath $log -Encoding utf8

    if (Get-Service -Name WinHttpAutoProxySvc -ErrorAction SilentlyContinue) {
        Restart-Service -Name WinHttpAutoProxySvc -Force -ErrorAction SilentlyContinue
        "WinHttpAutoProxySvc refreshed" | Add-Content -LiteralPath $log -Encoding utf8
    }

    ipconfig.exe /flushdns | Add-Content -LiteralPath $log -Encoding utf8

    $adapters = Get-CimInstance Win32_NetworkAdapter |
        Where-Object { $_.NetEnabled -and $_.NetConnectionID }
    foreach ($adapter in $adapters) {
        netsh.exe interface set interface name="$($adapter.NetConnectionID)" admin=disabled |
            Add-Content -LiteralPath $log -Encoding utf8
        Start-Sleep -Seconds 2
        netsh.exe interface set interface name="$($adapter.NetConnectionID)" admin=enabled |
            Add-Content -LiteralPath $log -Encoding utf8
        "adapter refreshed: $($adapter.NetConnectionID)" | Add-Content -LiteralPath $log -Encoding utf8
    }

    Start-Sleep -Seconds 4
    $addresses = [System.Net.Dns]::GetHostAddresses("git.chatgpt-team.site")
    "dns ok: $($addresses.IPAddressToString -join ', ')" | Add-Content -LiteralPath $log -Encoding utf8
    "[$(Get-Date -Format s)] COMPLETE" | Add-Content -LiteralPath $log -Encoding utf8
}
catch {
    "[$(Get-Date -Format s)] FAILED: $($_.Exception.Message)" | Add-Content -LiteralPath $log -Encoding utf8
    throw
}
