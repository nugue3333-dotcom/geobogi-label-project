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

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Quote-ProcessArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    return '"' + ($Value -replace '"', '\"') + '"'
}

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

$team = Get-Content -Raw -LiteralPath $TeamPath | ConvertFrom-Json
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

$projectInstructions = Get-Content -Raw -LiteralPath $ProjectInstructionsPath
$runAgents = New-Object System.Collections.Generic.List[object]

foreach ($agentId in $Agents) {
    $spec = $agentMap[$agentId]
    $rolePath = Join-Path $AgentsRoot (($spec.promptFile -as [string]) -replace "/", [IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $rolePath)) {
        throw "Missing role prompt for '$agentId': $rolePath"
    }

    $rolePrompt = Get-Content -Raw -LiteralPath $rolePath
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

if ($Launch) {
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
if ($Launch) {
    Write-Host "실행된 에이전트:"
    foreach ($entry in $runAgents) {
        Write-Host " - $($entry.id): PID $($entry.processId), output $($entry.output)"
    }
}
else {
    Write-Host "프롬프트만 생성했습니다. 실제 실행은 같은 명령에 -Launch를 붙이면 됩니다."
}
