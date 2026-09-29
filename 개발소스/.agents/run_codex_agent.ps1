[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [Parameter(Mandatory = $true)]
    [string]$PromptPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [Parameter(Mandatory = $true)]
    [string]$LogPath,

    [string]$Sandbox = "workspace-write",

    [string]$ApprovalPolicy = "never"
)

Set-StrictMode -Version Latest
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
    $profileRoot = if ($env:USERPROFILE) {
        $env:USERPROFILE
    }
    else {
        [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    }
    if (-not $profileRoot) {
        throw "Windows user profile path could not be resolved."
    }
    if (-not $env:USERPROFILE) {
        $env:USERPROFILE = $profileRoot
    }
    if (-not $env:SystemRoot) {
        $env:SystemRoot = "C:\Windows"
    }
    if (-not $env:WINDIR) {
        $env:WINDIR = $env:SystemRoot
    }
    if (-not $env:SystemDrive) {
        $env:SystemDrive = [System.IO.Path]::GetPathRoot($env:SystemRoot).TrimEnd("\")
    }
    if (-not $env:APPDATA) {
        $env:APPDATA = [Environment]::GetFolderPath([Environment+SpecialFolder]::ApplicationData)
    }
    if (-not $env:LOCALAPPDATA) {
        $env:LOCALAPPDATA = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    }
}

function Read-Utf8Text {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
}

function Write-AgentLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss K"
    Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value "[$timestamp] $Message"
}

function Test-CodexCliNetwork {
    $requiredHosts = @("chatgpt.com", "stitch.googleapis.com")
    $failures = New-Object System.Collections.Generic.List[string]

    foreach ($hostName in $requiredHosts) {
        try {
            $addresses = [System.Net.Dns]::GetHostAddresses($hostName)
            if ($addresses.Count -eq 0) {
                $failures.Add("${hostName}: no DNS addresses returned")
            }
        }
        catch {
            $failures.Add("${hostName}: $($_.Exception.Message)")
        }
    }

    return @($failures.ToArray())
}

try {
    Set-Utf8ProcessEncoding
    Repair-WindowsProcessEnvironment

    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputPath)
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath)
    Set-Content -LiteralPath $LogPath -Encoding UTF8 -Value ""

    $userCodex = Join-Path $env:APPDATA "npm\codex.cmd"
    $codexPath = if (Test-Path -LiteralPath $userCodex) {
        $userCodex
    }
    else {
        (Get-Command codex -ErrorAction Stop).Source
    }
    Write-AgentLog "Starting Codex agent"
    Write-AgentLog "CodexPath=$codexPath"
    Write-AgentLog "ProjectRoot=$ProjectRoot"
    Write-AgentLog "PromptPath=$PromptPath"
    Write-AgentLog "OutputPath=$OutputPath"
    Write-AgentLog "Sandbox=$Sandbox ApprovalPolicy=$ApprovalPolicy"

    $prompt = Read-Utf8Text -Path $PromptPath
    $networkFailures = @(Test-CodexCliNetwork)
    if ($networkFailures.Count -gt 0) {
        $failureText = $networkFailures -join [Environment]::NewLine
        $message = @"
Codex CLI network preflight failed.

The terminal-based Codex CLI cannot resolve the required service hosts, so this agent was not launched. Use Codex app internal multi-agent mode for real edits, or repair the Windows network stack before retrying the legacy CLI runner.

Failed hosts:
$failureText

Repair command:
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\repair_windows_network_stack.ps1

Administrator repair command:
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\repair_windows_network_stack.ps1 -Apply -RelaunchElevated

Recommended fallback:
Codex 앱 멀티에이전트로 [작업 설명] 진행해
"@
        Set-Content -LiteralPath $OutputPath -Encoding UTF8 -Value $message
        Write-AgentLog "Codex CLI network preflight failed"
        foreach ($failure in $networkFailures) {
            Write-AgentLog $failure
        }
        exit 2
    }

    Push-Location -LiteralPath $ProjectRoot
    try {
        $prompt |
            & $codexPath exec `
                -C $ProjectRoot `
                --sandbox $Sandbox `
                -c "approval_policy=`"$ApprovalPolicy`"" `
                -o $OutputPath `
                - 2>&1 |
            Tee-Object -FilePath $LogPath -Append

        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    }
    finally {
        Pop-Location
    }

    Write-AgentLog "Finished Codex agent with exit code $exitCode"
    exit $exitCode
}
catch {
    Write-AgentLog "Failed: $($_.Exception.Message)"
    exit 1
}
