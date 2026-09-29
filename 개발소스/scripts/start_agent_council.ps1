[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Task,

    [string[]]$Agents = @(),

    [ValidateRange(1, 4)]
    [int]$Rounds = 4,

    [ValidateSet("read-only", "workspace-write", "danger-full-access")]
    [string]$Sandbox = "workspace-write",

    [ValidateSet("never", "on-request", "untrusted")]
    [string]$ApprovalPolicy = "never",

    [switch]$Launch,

    [switch]$AllowLegacyNestedLaunch
)

# Codex app internal sub-agents are the default workflow for real edits.
# This script is a legacy helper for prompt/council package generation and
# explicit CLI automation only.

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

function Normalize-AgentList {
    param([string[]]$InputAgents)

    return @(
        foreach ($agent in $InputAgents) {
            foreach ($part in ($agent -split ",")) {
                $normalized = $part.Trim()
                if ($normalized) {
                    $normalized
                }
            }
        }
    )
}

function Add-TranscriptBlock {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Text
    )

    Add-Content -LiteralPath $Path -Encoding UTF8 -Value ""
    Add-Content -LiteralPath $Path -Encoding UTF8 -Value $Text
}

function Test-CodexCliNetwork {
    $requiredHosts = @("chatgpt.com", "stitch.googleapis.com")
    $failures = New-Object System.Collections.Generic.List[object]

    foreach ($hostName in $requiredHosts) {
        try {
            $addresses = [System.Net.Dns]::GetHostAddresses($hostName)
            if ($addresses.Count -eq 0) {
                $failures.Add([ordered]@{
                        host = $hostName
                        error = "no DNS addresses returned"
                    })
            }
        }
        catch {
            $failures.Add([ordered]@{
                    host = $hostName
                    # Keep platform-specific socket errors out of user-facing
                    # council output; the stable reason is sufficient here.
                    error = "name resolution unavailable in nested CLI process"
                })
        }
    }

    return @($failures.ToArray())
}

Set-Utf8ProcessEncoding
Repair-WindowsProcessEnvironment

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$AgentsRoot = Join-Path $ProjectRoot ".agents"
$TeamPath = Join-Path $AgentsRoot "team.json"
$ProjectInstructionsPath = Join-Path $ProjectRoot "AGENTS.md"
$CouncilProtocolPath = Join-Path $AgentsRoot "prompts\council-protocol.md"
$RunAgentScript = Join-Path $AgentsRoot "run_codex_agent.ps1"

foreach ($requiredPath in @($TeamPath, $ProjectInstructionsPath, $CouncilProtocolPath, $RunAgentScript)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Missing required file: $requiredPath"
    }
}

$userCodex = Join-Path $env:APPDATA "npm\codex.cmd"
$codex = if (Test-Path -LiteralPath $userCodex) {
    Get-Item -LiteralPath $userCodex
}
else {
    Get-Command codex -ErrorAction SilentlyContinue
}
if (-not $codex) {
    throw "codex CLI was not found on PATH. Install or log in to Codex first."
}
$codexPath = if ($codex.PSObject.Properties["Source"]) {
    $codex.Source
}
else {
    $codex.FullName
}

$team = Read-Utf8Text -Path $TeamPath | ConvertFrom-Json
$agentMap = @{}
foreach ($property in $team.agents.PSObject.Properties) {
    $agentMap[$property.Name] = $property.Value
}

if ($Agents.Count -eq 0) {
    $Agents = @($team.collaboration.defaultCouncilAgents)
}
$Agents = Normalize-AgentList -InputAgents $Agents

foreach ($agentId in $Agents) {
    if (-not $agentMap.ContainsKey($agentId)) {
        $valid = ($agentMap.Keys | Sort-Object) -join ", "
        throw "Unknown agent '$agentId'. Valid agents: $valid"
    }
}

$allRounds = @($team.collaboration.rounds)
$selectedRounds = @($allRounds | Select-Object -First $Rounds)

$runsRoot = Join-Path $AgentsRoot "councils"
$runStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$runRoot = Join-Path $runsRoot $runStamp
$promptRoot = Join-Path $runRoot "prompts"
$outputRoot = Join-Path $runRoot "outputs"
$logRoot = Join-Path $runRoot "logs"

foreach ($path in @($promptRoot, $outputRoot, $logRoot)) {
    $null = New-Item -ItemType Directory -Force -Path $path
}

$projectInstructions = Read-Utf8Text -Path $ProjectInstructionsPath
$councilProtocol = Read-Utf8Text -Path $CouncilProtocolPath
$transcriptPath = Join-Path $runRoot "transcript.md"

$agentListText = ($Agents | ForEach-Object {
        $spec = $agentMap[$_]
        "- ${_}: $($spec.displayName) / $($spec.defaultPurpose) / write scope: $($spec.writeScope)"
    }) -join [Environment]::NewLine

$roundListText = ($selectedRounds | ForEach-Object {
        "- $($_.id): $($_.title) / write policy: $($_.writePolicy)"
    }) -join [Environment]::NewLine

$initialTranscript = @"
# Agent Council Transcript

Created: $((Get-Date).ToString("o"))
Project: $ProjectRoot
Task: $Task
Launch: $($Launch.IsPresent)
Sandbox: $Sandbox
ApprovalPolicy: $ApprovalPolicy

## Agents

$agentListText

## Rounds

$roundListText

## Current Shared State

No agent has spoken yet.
"@

Set-Content -LiteralPath $transcriptPath -Encoding UTF8 -Value $initialTranscript

$runItems = New-Object System.Collections.Generic.List[object]
$powerShellExe = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $powerShellExe) {
    $powerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source
}

$dnsPreflightFailures = @()
$launchBlocked = $false
$blockedReason = $null
if ($Launch -and (-not $AllowLegacyNestedLaunch)) {
    $launchBlocked = $true
    $blockedReason = "legacy-nested-launch-disabled"
}
elseif ($Launch) {
    $dnsPreflightFailures = @(Test-CodexCliNetwork)
    if ($dnsPreflightFailures.Count -gt 0) {
        $launchBlocked = $true
        $blockedReason = "dns-preflight-failed"
    }
}
$shouldLaunch = $Launch.IsPresent -and (-not $launchBlocked)

for ($roundIndex = 0; $roundIndex -lt $selectedRounds.Count; $roundIndex++) {
    $round = $selectedRounds[$roundIndex]
    $roundNumber = $roundIndex + 1

    foreach ($agentId in $Agents) {
        $spec = $agentMap[$agentId]
        $rolePath = Join-Path $AgentsRoot (($spec.promptFile -as [string]) -replace "/", [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $rolePath)) {
            throw "Missing role prompt for '$agentId': $rolePath"
        }

        $rolePrompt = Read-Utf8Text -Path $rolePath
        $currentTranscript = Read-Utf8Text -Path $transcriptPath
        $roundAgentId = "{0:00}-{1}-{2}" -f $roundNumber, $round.id, $agentId
        $promptPath = Join-Path $promptRoot "$roundAgentId.md"
        $outputPath = Join-Path $outputRoot "$roundAgentId.final.txt"
        $logPath = Join-Path $logRoot "$roundAgentId.log"

        $prompt = @"
# Agent Council Turn

## Round

- round: $roundNumber
- phase: $($round.id)
- title: $($round.title)
- write policy: $($round.writePolicy)

## Agent

- id: $agentId
- name: $($spec.displayName)
- purpose: $($spec.defaultPurpose)
- write scope: $($spec.writeScope)

## User Task

$Task

## Project Root

$ProjectRoot

## Shared Project Instructions

$projectInstructions

## Council Protocol

$councilProtocol

## Role Instructions

$rolePrompt

## Conversation So Far

$currentTranscript

## Your Turn

Respond to the conversation so far. Follow this round's write policy.

For diagnosis and solution-debate rounds, do not edit files.
For implementation, edit only when your role and write scope allow it. If you are not the right writer, explain what should be changed and why.
For verification, run safe checks only and do not perform physical printer output, live message sending, real-account actions, or production server changes.

End with:
1. 핵심 판단
2. 다른 에이전트 의견에 대한 동의/반대
3. 제안 또는 변경 사항
4. 검증 결과 또는 필요한 검증
5. 남은 위험
"@

        Set-Content -LiteralPath $promptPath -Encoding UTF8 -Value $prompt

        $exitCode = $null
        if ($shouldLaunch) {
            & $powerShellExe `
                -NoProfile `
                -ExecutionPolicy Bypass `
                -File $RunAgentScript `
                -ProjectRoot $ProjectRoot `
                -PromptPath $promptPath `
                -OutputPath $outputPath `
                -LogPath $logPath `
                -Sandbox $Sandbox `
                -ApprovalPolicy $ApprovalPolicy

            $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
            $agentMessage = if (Test-Path -LiteralPath $outputPath) {
                Read-Utf8Text -Path $outputPath
            }
            else {
                "No final output file was created. Check log: $logPath"
            }
        }
        elseif ($launchBlocked) {
            if ($blockedReason -eq "legacy-nested-launch-disabled") {
                $agentMessage = @"
Nested Codex CLI launch is disabled by default. No agents were launched.

Supported workflow:
Codex 앱 멀티에이전트로 [작업 설명] 진행해

For explicitly approved legacy diagnostics only, both -Launch and
-AllowLegacyNestedLaunch are required.
"@
            }
            else {
                $failureText = ($dnsPreflightFailures | ForEach-Object { "- $($_.host): $($_.error)" }) -join [Environment]::NewLine
                $agentMessage = @"
Nested Codex CLI network preflight failed. No agents were launched.

Failed hosts:
$failureText

The nested terminal process cannot reach the required service hosts. This does
not indicate a repository failure, and changing the PC DNS settings is not the
default recovery path.

Supported workflow:
Codex 앱 멀티에이전트로 [작업 설명] 진행해
"@
            }
        }
        else {
            $agentMessage = "Prompt created only. Launch was not requested. Prompt: $promptPath"
        }

        $transcriptBlock = @"
## Round $roundNumber - $($round.title) - $agentId

Status: $(if ($shouldLaunch) { "executed with exit code $exitCode" } elseif ($launchBlocked) { "launch blocked: $blockedReason" } else { "prompt-only" })
Prompt: $promptPath
Output: $outputPath
Log: $logPath

$agentMessage
"@

        Add-TranscriptBlock -Path $transcriptPath -Text $transcriptBlock

        $runItems.Add([ordered]@{
                round = $roundNumber
                phase = $round.id
                agent = $agentId
                prompt = $promptPath
                output = $outputPath
                log = $logPath
                exitCode = $exitCode
                launched = $shouldLaunch
            })
    }
}

$failedTurns = @(
    $runItems.ToArray() | Where-Object {
        [bool]$_['launched'] -and $null -ne $_['exitCode'] -and [int]$_['exitCode'] -ne 0
    }
)

$summary = [ordered]@{
    createdAt = (Get-Date).ToString("o")
    projectRoot = $ProjectRoot
    task = $Task
    mode = "council"
    launch = $Launch.IsPresent
    launchBlocked = $launchBlocked
    blockedReason = $blockedReason
    dnsPreflight = [ordered]@{
        passed = (-not $launchBlocked)
        hosts = @($dnsPreflightFailures)
    }
    sandbox = $Sandbox
    approvalPolicy = $ApprovalPolicy
    codexPath = $codexPath
    runRoot = $runRoot
    transcript = $transcriptPath
    agents = @($Agents)
    rounds = @($selectedRounds | ForEach-Object { $_.id })
    turns = @($runItems.ToArray())
    failedTurnCount = $failedTurns.Count
}

$summaryPath = Join-Path $runRoot "council_summary.json"
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host "멀티 AI 에이전트 회의 패키지: $runRoot"
Write-Host "회의록: $transcriptPath"
Write-Host "요약 파일: $summaryPath"
Write-Host "Codex CLI: $codexPath"
if ($Launch) {
    if ($launchBlocked) {
        if ($blockedReason -eq "legacy-nested-launch-disabled") {
            Write-Host "Nested Codex CLI launch is disabled by default. No agents were launched."
        }
        else {
            Write-Host "Nested Codex CLI network preflight failed. No agents were launched."
            foreach ($failure in $dnsPreflightFailures) {
                Write-Host " - $($failure.host): $($failure.error)"
            }
        }
        Write-Host "Supported workflow: Codex 앱 멀티에이전트로 [작업 설명] 진행해"
        exit 2
    }
    if ($failedTurns.Count -gt 0) {
        Write-Host "순차 회의 실행 중 실패한 에이전트가 있습니다: $($failedTurns.Count)건"
        Write-Host "첫 실패 로그: $($failedTurns[0].log)"
        exit 1
    }
    Write-Host "순차 회의 실행이 완료되었습니다."
}
else {
    Write-Host "프롬프트와 회의록만 생성했습니다. 실제 수정 작업은 Codex 앱에서 'Codex 앱 멀티에이전트로 [작업] 진행해'라고 요청하는 방식을 권장합니다."
}
