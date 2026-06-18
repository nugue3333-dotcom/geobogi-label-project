#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Question,

    [string]$OutputPath = ".agent\hermes-last.md",

    [string[]]$ContextFile = @(),

    [int]$MaxTurns = 3,

    [switch]$Raw
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
    # Older hosts may not allow changing console encoding; Hermes still runs.
}
$env:PYTHONIOENCODING = "utf-8"

function Resolve-HermesExe {
    $localAppData = [Environment]::GetEnvironmentVariable("LOCALAPPDATA")
    if ($localAppData) {
        $preferred = Join-Path $localAppData "hermes\hermes-agent\venv\Scripts\hermes.exe"
        if (Test-Path -LiteralPath $preferred) {
            return $preferred
        }
    }

    $fromPath = Get-Command hermes.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    throw "Hermes CLI was not found. Check the Hermes install path or PATH."
}

function Resolve-HermesPython {
    param([string]$HermesExe)

    $scriptsDir = Split-Path -Parent $HermesExe
    if ($scriptsDir) {
        $candidate = Join-Path $scriptsDir "python.exe"
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $fromPath = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    throw "Python was not found. Hermes helper needs Python to pass long prompts safely."
}

function Read-ContextBlock {
    param(
        [string]$Path,
        [int]$MaxChars = 1800
    )

    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $resolved) {
        return $null
    }

    try {
        $content = Get-Content -LiteralPath $resolved.Path -Raw -Encoding UTF8
    } catch {
        $content = Get-Content -LiteralPath $resolved.Path -Raw
    }

    if ($content.Length -gt $MaxChars) {
        $content = $content.Substring(0, $MaxChars) + "`r`n...[truncated]"
    }

    return @"
### $Path

````text
$content
````
"@
}

$questionText = $Question.Trim()
if ([string]::IsNullOrWhiteSpace($questionText)) {
    throw "Question is empty."
}

$hermesExe = Resolve-HermesExe
$pythonExe = Resolve-HermesPython -HermesExe $hermesExe

if ($ContextFile.Count -eq 0) {
    $currentDir = Get-Item -LiteralPath .
    if (
        (Test-Path -LiteralPath (Join-Path $currentDir.FullName "AGENTS.md")) -and
        (Test-Path -LiteralPath (Join-Path $currentDir.FullName "docs\PRODUCT_PACKAGES.md"))
    ) {
        $projectDir = $currentDir
    } else {
        $projectDir = Get-ChildItem -LiteralPath . -Directory |
            Where-Object {
                (Test-Path -LiteralPath (Join-Path $_.FullName "AGENTS.md")) -and
                (Test-Path -LiteralPath (Join-Path $_.FullName "docs\PRODUCT_PACKAGES.md"))
            } |
            Select-Object -First 1
    }

    if ($projectDir) {
        $ContextFile = @(
            (Join-Path $projectDir.FullName "AGENTS.md"),
            (Join-Path $projectDir.FullName "docs\PRODUCT_PACKAGES.md"),
            (Join-Path $projectDir.FullName "docs\MARKETING_AUTOMATION_RULES.md")
        )
    }
}

$contextBlocks = @()
foreach ($file in $ContextFile) {
    $block = Read-ContextBlock -Path $file
    if ($block) {
        $contextBlocks += $block
    }
}

$contextText = if ($contextBlocks.Count -gt 0) {
    $contextBlocks -join "`r`n`r`n"
} else {
    "(No project context files were found.)"
}

if ($Raw) {
    $prompt = $questionText
} else {
    $prompt = @"
You are Hermes, a review and planning helper for this local project.

Rules:
- Do not edit files, run deployments, or perform destructive actions. Only answer.
- Answer in Korean.
- Be concise and practical.
- Mark hardware compatibility, pricing, warranty, refunds, installation support, and integration claims as "needs confirmation" when evidence is missing.
- Prefer dry-run validation over real printer output for label, barcode, and printer work.
- Organize the answer so Codex can use it for the next implementation step.

Current working directory:
$PWD

Question:
$questionText

Project context:
$contextText
"@
}

$outDir = Split-Path -Parent $OutputPath
if ([string]::IsNullOrWhiteSpace($outDir)) {
    $outDir = "."
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$promptPath = Join-Path $outDir "hermes-prompt.md"
$runnerPath = Join-Path $outDir "hermes-runner.py"
Set-Content -LiteralPath $promptPath -Value $prompt -Encoding UTF8

$runnerCode = @'
import pathlib
import subprocess
import sys

hermes_exe = sys.argv[1]
prompt_path = pathlib.Path(sys.argv[2])
max_turns = sys.argv[3]

prompt = prompt_path.read_text(encoding="utf-8-sig")
args = [
    hermes_exe,
    "chat",
    "-q",
    prompt,
    "-Q",
    "--max-turns",
    str(max_turns),
    "--source",
    "codex-helper",
]

completed = subprocess.run(
    args,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
)
sys.stdout.write(completed.stdout)
sys.exit(completed.returncode)
'@
Set-Content -LiteralPath $runnerPath -Value $runnerCode -Encoding ASCII

$startedAt = Get-Date
$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $outputLines = & $pythonExe $runnerPath $hermesExe $promptPath $MaxTurns 2>&1
} finally {
    $ErrorActionPreference = $oldErrorActionPreference
    Remove-Item -LiteralPath $runnerPath -ErrorAction SilentlyContinue
}
$exitCode = $LASTEXITCODE
$finishedAt = Get-Date
$responseText = (($outputLines | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine).Trim()

$contextList = if ($ContextFile.Count -gt 0) {
    ($ContextFile | ForEach-Object { "- $_" }) -join "`r`n"
} else {
    "- none"
}

$markdown = @"
# Hermes Last Response

- Created: $($finishedAt.ToString("yyyy-MM-dd HH:mm:ss zzz"))
- Working directory: $((Get-Location).Path)
- Hermes CLI: $hermesExe
- Hermes Python: $pythonExe
- Exit code: $exitCode
- Max turns: $MaxTurns
- Prompt file: $promptPath

## Question

$questionText

## Context Files

$contextList

## Response

$responseText
"@

Set-Content -LiteralPath $OutputPath -Value $markdown -Encoding UTF8

Write-Host "Saved Hermes response to $OutputPath"
Write-Host "Started:  $($startedAt.ToString("HH:mm:ss"))"
Write-Host "Finished: $($finishedAt.ToString("HH:mm:ss"))"

if ($exitCode -ne 0) {
    throw "Hermes CLI failed with exit code $exitCode. See $OutputPath for captured output."
}
