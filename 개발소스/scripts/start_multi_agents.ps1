[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Task,

    [string[]]$Agents = @(),

    [ValidateSet("plan", "execute", "verify")]
    [string]$Mode = "execute",

    [ValidateSet("read-only", "workspace-write", "danger-full-access")]
    [string]$Sandbox = "workspace-write",

    [ValidateSet("never", "on-request", "untrusted")]
    [string]$ApprovalPolicy = "never",

    [switch]$Launch
)

# Codex app internal sub-agents are the default workflow for real edits.
# This script is a legacy helper for prompt package generation and explicit
# CLI automation only.

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

function Read-Utf8Text {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
}

function Quote-ProcessArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    return '"' + ($Value -replace '"', '\"') + '"'
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
                    error = $_.Exception.Message
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
$RunAgentScript = Join-Path $AgentsRoot "run_codex_agent.ps1"

if (-not (Test-Path -LiteralPath $TeamPath)) {
    throw "Missing team config: $TeamPath"
}
if (-not (Test-Path -LiteralPath $ProjectInstructionsPath)) {
    throw "Missing project instructions: $ProjectInstructionsPath"
}
if (-not (Test-Path -LiteralPath $RunAgentScript)) {
    throw "Missing Codex runner: $RunAgentScript"
}

$codex = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codex) {
    throw "codex CLI was not found on PATH. Install or log in to Codex first."
}

$team = Read-Utf8Text -Path $TeamPath | ConvertFrom-Json
$agentMap = @{}
foreach ($property in $team.agents.PSObject.Properties) {
    $agentMap[$property.Name] = $property.Value
}

if ($Agents.Count -eq 0) {
    $Agents = @($team.defaultAgents)
}
else {
    $Agents = @(
        foreach ($agent in $Agents) {
            foreach ($part in ($agent -split ",")) {
                $normalized = $part.Trim()
                if ($normalized) {
                    $normalized
                }
            }
        }
    )
}

foreach ($agentId in $Agents) {
    if (-not $agentMap.ContainsKey($agentId)) {
        $valid = ($agentMap.Keys | Sort-Object) -join ", "
        throw "Unknown agent '$agentId'. Valid agents: $valid"
    }
}

$runsRoot = Join-Path $AgentsRoot "runs"
$runStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$runRoot = Join-Path $runsRoot $runStamp
$promptRoot = Join-Path $runRoot "prompts"
$outputRoot = Join-Path $runRoot "outputs"
$logRoot = Join-Path $runRoot "logs"

foreach ($path in @($promptRoot, $outputRoot, $logRoot)) {
    $null = New-Item -ItemType Directory -Force -Path $path
}

$projectInstructions = Read-Utf8Text -Path $ProjectInstructionsPath
$runAgents = New-Object System.Collections.Generic.List[object]

foreach ($agentId in $Agents) {
    $spec = $agentMap[$agentId]
    $rolePath = Join-Path $AgentsRoot (($spec.promptFile -as [string]) -replace "/", [IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $rolePath)) {
        throw "Missing role prompt for '$agentId': $rolePath"
    }

    $rolePrompt = Read-Utf8Text -Path $rolePath
    $promptPath = Join-Path $promptRoot "$agentId.md"
    $outputPath = Join-Path $outputRoot "$agentId.final.txt"
    $logPath = Join-Path $logRoot "$agentId.log"

    $prompt = @"
# Multi-Agent Assignment

## Agent

- id: $agentId
- name: $($spec.displayName)
- purpose: $($spec.defaultPurpose)
- mode: $Mode
- write scope: $($spec.writeScope)

## User Task

$Task

## Project Root

$ProjectRoot

## Shared Project Instructions

$projectInstructions

## Role Instructions

$rolePrompt

## Required Final Report

1. 완료한 결과
2. 주요 변경 파일
3. 실행한 검증과 결과
4. 실제 장비, 운영 서버, 외부 발송, 고객 배포에서 추가 확인할 항목
5. 알려진 제한사항이나 남은 위험

If this role is read-only, do not edit files.
"@

    Set-Content -LiteralPath $promptPath -Encoding UTF8 -Value $prompt

    $runAgents.Add([ordered]@{
            id = $agentId
            displayName = $spec.displayName
            prompt = $promptPath
            output = $outputPath
            log = $logPath
            processId = $null
            launched = $false
        })
}

$dnsPreflightFailures = @()
$launchBlocked = $false
$blockedReason = $null
if ($Launch) {
    $dnsPreflightFailures = @(Test-CodexCliNetwork)
    if ($dnsPreflightFailures.Count -gt 0) {
        $launchBlocked = $true
        $blockedReason = "dns-preflight-failed"
    }
}
$shouldLaunch = $Launch.IsPresent -and (-not $launchBlocked)

if ($shouldLaunch) {
    $powerShellExe = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if (-not $powerShellExe) {
        $powerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source
    }

    for ($i = 0; $i -lt $runAgents.Count; $i++) {
        $entry = $runAgents[$i]
        $arguments = @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            (Quote-ProcessArgument $RunAgentScript),
            "-ProjectRoot",
            (Quote-ProcessArgument $ProjectRoot),
            "-PromptPath",
            (Quote-ProcessArgument $entry.prompt),
            "-OutputPath",
            (Quote-ProcessArgument $entry.output),
            "-LogPath",
            (Quote-ProcessArgument $entry.log),
            "-Sandbox",
            (Quote-ProcessArgument $Sandbox),
            "-ApprovalPolicy",
            (Quote-ProcessArgument $ApprovalPolicy)
        ) -join " "

        $process = Start-Process -FilePath $powerShellExe -ArgumentList $arguments -PassThru -WindowStyle Hidden
        $entry["processId"] = $process.Id
        $entry["launched"] = $true
        $runAgents[$i] = $entry
    }
}

$summary = [ordered]@{
    createdAt = (Get-Date).ToString("o")
    projectRoot = $ProjectRoot
    task = $Task
    mode = $Mode
    launch = $Launch.IsPresent
    launchBlocked = $launchBlocked
    blockedReason = $blockedReason
    dnsPreflight = [ordered]@{
        passed = (-not $launchBlocked)
        hosts = @($dnsPreflightFailures)
    }
    sandbox = $Sandbox
    approvalPolicy = $ApprovalPolicy
    codexPath = $codex.Source
    runRoot = $runRoot
    agents = @($runAgents.ToArray())
}

$summaryPath = Join-Path $runRoot "run_summary.json"
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host "멀티 에이전트 실행 패키지: $runRoot"
Write-Host "요약 파일: $summaryPath"
Write-Host "Codex CLI: $($codex.Source)"
if ($launchBlocked) {
    Write-Host "Codex CLI DNS preflight failed. No agents were launched."
    foreach ($failure in $dnsPreflightFailures) {
        Write-Host " - $($failure.host): $($failure.error)"
    }
    Write-Host "Fallback: Codex 앱 멀티에이전트로 [작업 설명] 진행해"
    Write-Host "Repair: 우클릭으로 .\05_repair_network_stack_as_admin.cmd 파일을 관리자 권한으로 실행"
    exit 2
}
elseif ($Launch) {
    Write-Host "실행된 에이전트:"
    foreach ($entry in $runAgents) {
        Write-Host " - $($entry.id): PID $($entry.processId), output $($entry.output)"
    }
}
else {
    Write-Host "프롬프트만 생성했습니다. 실제 실행은 같은 명령에 -Launch를 붙이면 됩니다."
}
