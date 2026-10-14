[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$RelaunchElevated,
    [switch]$SetPublicDns,
    [string]$InterfaceAlias = ""
)

$ErrorActionPreference = "Stop"

function Set-Utf8ProcessEncoding {
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [Console]::InputEncoding = $utf8NoBom
    [Console]::OutputEncoding = $utf8NoBom
    $script:OutputEncoding = $utf8NoBom
    $global:OutputEncoding = $utf8NoBom
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
}

function Repair-WindowsProcessEnvironment {
    if (-not $env:SystemRoot) {
        $env:SystemRoot = "C:\Windows"
    }
    if (-not $env:WINDIR) {
        $env:WINDIR = $env:SystemRoot
    }
    if (-not $env:SystemDrive) {
        $env:SystemDrive = [System.IO.Path]::GetPathRoot($env:SystemRoot).TrimEnd("\")
    }
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-SocketHealth {
    try {
        $client = [Net.Sockets.TcpClient]::new()
        $client.Connect("8.8.8.8", 443)
        $client.Close()
        return "socket-ok"
    }
    catch {
        return ("socket-error: " + $_.Exception.Message)
    }
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host "`n== $Title =="
    try {
        & $Command
    }
    catch {
        Write-Host ("ERROR: " + $_.Exception.Message)
    }
}

function Test-DnsHost {
    param([Parameter(Mandatory = $true)][string]$HostName)

    Write-Host "`n-- DNS: $HostName =="
    try {
        $addresses = [System.Net.Dns]::GetHostAddresses($HostName) | ForEach-Object { $_.IPAddressToString }
        if ($addresses.Count -gt 0) {
            Write-Host ("System.Net.Dns: OK " + ($addresses -join ", "))
        }
        else {
            Write-Host "System.Net.Dns: FAIL no addresses returned"
        }
    }
    catch {
        Write-Host ("System.Net.Dns: FAIL " + $_.Exception.Message)
    }

    nslookup $HostName
    nslookup $HostName 8.8.8.8
}

function Get-WindowsDirectory {
    if ($env:SystemRoot) {
        return $env:SystemRoot
    }
    if ($env:WINDIR) {
        return $env:WINDIR
    }
    return "C:\Windows"
}

function Get-DefaultInterfaceAlias {
    $lines = @(netsh interface show interface)
    foreach ($line in $lines) {
        if ($line -match '^\s*Enabled\s+Connected\s+\S+\s+(.+)$') {
            return $Matches[1].Trim()
        }
    }

    throw "Could not find a connected network interface. Pass -InterfaceAlias explicitly."
}

Set-Utf8ProcessEncoding
Repair-WindowsProcessEnvironment

Write-Host "== Network stack diagnostics =="
Write-Host ("Admin: " + (Test-Admin))
Write-Host ("Socket: " + (Test-SocketHealth))

Invoke-CheckedCommand "IP configuration" { ipconfig /all }

Invoke-CheckedCommand "WinHTTP proxy" { netsh winhttp show proxy }

Invoke-CheckedCommand "Interface DNS servers" { netsh interface ip show dnsservers }

Write-Host "`n== DNS probe =="
Test-DnsHost "www.google.com"
Test-DnsHost "chatgpt.com"
Test-DnsHost "stitch.googleapis.com"

if (-not $Apply) {
    Write-Host "`nDry run only. Re-run with -Apply -RelaunchElevated to reset Winsock/IP with administrator privileges."
    Write-Host "If DNS still fails after reboot, run again with -Apply -RelaunchElevated -SetPublicDns."
    exit 0
}

if (-not (Test-Admin)) {
    if ($RelaunchElevated) {
        $args = @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ('"' + $PSCommandPath + '"'),
            "-Apply"
        )
        if ($SetPublicDns) {
            $args += "-SetPublicDns"
            $args += "-InterfaceAlias"
            $args += ('"' + $InterfaceAlias + '"')
        }
        $windowsDirectory = Get-WindowsDirectory
        $windowsPowerShell = Join-Path $windowsDirectory "System32\WindowsPowerShell\v1.0\powershell.exe"
        $system32Directory = Join-Path $windowsDirectory "System32"
        Start-Process `
            -FilePath $windowsPowerShell `
            -ArgumentList $args `
            -WorkingDirectory $system32Directory `
            -Verb RunAs `
            -Wait
        exit $LASTEXITCODE
    }
    throw "Administrator privileges are required. Run PowerShell as administrator, then execute this script with -Apply."
}

Write-Host "`n== Applying repairs =="
ipconfig /flushdns
netsh winsock reset
netsh int ip reset

if ($SetPublicDns) {
    if (-not $InterfaceAlias) {
        $InterfaceAlias = Get-DefaultInterfaceAlias
    }
    Write-Host "`n== Setting public DNS on $InterfaceAlias =="
    netsh interface ip set dns name="$InterfaceAlias" static 1.1.1.1 primary
    netsh interface ip add dns name="$InterfaceAlias" 8.8.8.8 index=2
}

Write-Host "`nRepair commands completed. Restart Windows before retesting Codex/curl/Invoke-WebRequest."
