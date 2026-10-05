[CmdletBinding()]
param(
    [string]$Version = (Get-Date -Format "yyyy.MM.dd.HHmm"),
    [string]$PackageName = "채움랩_라벨출력_고객용",
    [string]$BuildId = (Get-Date -Format "yyyyMMdd_HHmmss"),
    [string]$TestResult = "not-run",
    [string]$PythonPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootPath = [System.IO.Path]::GetFullPath($Root).TrimEnd("\") + "\"
    $targetPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $targetPath.StartsWith($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "작업 경로가 소스 루트 밖입니다: $targetPath"
    }
}

function Get-FileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Copy-FileWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [int]$Attempts = 5
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Copy-Item -LiteralPath $Source -Destination $Destination -Force -ErrorAction Stop
            return
        }
        catch {
            $lastError = $_
            if ($attempt -lt $Attempts) {
                Start-Sleep -Milliseconds (250 * $attempt)
            }
        }
    }

    throw "파일 복사 실패(잠금 또는 권한): $Source -> $Destination`n$($lastError.Exception.Message)"
}

function Assert-ExactExecutables {
    param(
        [Parameter(Mandatory = $true)][string]$Directory,
        [Parameter(Mandatory = $true)][string[]]$ExpectedNames
    )

    $actual = @(Get-ChildItem -LiteralPath $Directory -Force | Sort-Object Name)
    $actualNames = @($actual | ForEach-Object { $_.Name })
    $difference = @(Compare-Object -ReferenceObject ($ExpectedNames | Sort-Object) -DifferenceObject $actualNames)
    if ($difference.Count -ne 0 -or @($actual | Where-Object { -not $_.PSIsContainer -and $_.Extension -ne ".exe" }).Count -ne 0 -or @($actual | Where-Object { $_.PSIsContainer }).Count -ne 0) {
        throw "dist에는 지정된 한글 EXE 6개만 있어야 합니다. 실제: $($actualNames -join ', ')"
    }
}

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$CustomerRoot = Join-Path $ProjectRoot "고객용_실행폴더"
$FinalRoot = Split-Path -Parent $ProjectRoot
$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot (".release-build\" + $BuildId)
$StageDist = Join-Path $BuildRoot "dist"
$WorkRoot = Join-Path $BuildRoot "work"
$LockPath = Join-Path $ProjectRoot ".build_release_exes.lock"

$Specs = @(
    [ordered]@{ Spec = "customer_preflight.spec"; Exe = "고객환경점검.exe" },
    [ordered]@{ Spec = "label_designer.spec"; Exe = "라벨디자이너.exe" },
    [ordered]@{ Spec = "label_job_runner.spec"; Exe = "라벨작업실행기.exe" },
    [ordered]@{ Spec = "label_manager.spec"; Exe = "라벨출력관리.exe" },
    [ordered]@{ Spec = "print_labels.spec"; Exe = "라벨출력엔진.exe" },
    [ordered]@{ Spec = "printer_settings.spec"; Exe = "프린터설정.exe" }
)
$ExpectedExeNames = @($Specs | ForEach-Object { $_.Exe })
$CustomerGuideNames = @("한눈에_사용안내.pdf", "README_먼저읽기.txt", "사용안내.txt")

if (-not (Test-Path -LiteralPath $CustomerRoot -PathType Container)) {
    throw "고객용 실행폴더가 없습니다: $CustomerRoot"
}
if (-not (Test-Path -LiteralPath $FinalRoot -PathType Container)) {
    throw "상위 최종 폴더가 없습니다: $FinalRoot"
}
foreach ($item in $Specs) {
    $specPath = Join-Path $ProjectRoot $item.Spec
    if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
        throw "PyInstaller spec 파일이 없습니다: $specPath"
    }
}
foreach ($name in $CustomerGuideNames) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $name) -PathType Leaf)) {
        throw "고객 안내 파일이 없습니다: $name"
    }
}

if (-not $PythonPath) {
    $PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python 실행 파일이 없습니다: $PythonPath"
}
$PythonExe = (Resolve-Path -LiteralPath $PythonPath).Path

Assert-ChildPath -Root $ProjectRoot -Path $BuildRoot
Assert-ChildPath -Root $ProjectRoot -Path $DistRoot

$lockStream = $null
try {
    $lockStream = [System.IO.File]::Open(
        $LockPath,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
}
catch {
    throw "다른 릴리스 빌드가 실행 중입니다. 완료 후 다시 실행하세요: $LockPath"
}

try {
    if (Test-Path -LiteralPath $BuildRoot) {
        Assert-ChildPath -Root $ProjectRoot -Path $BuildRoot
        Remove-Item -LiteralPath $BuildRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $StageDist -Force | Out-Null
    New-Item -ItemType Directory -Path $WorkRoot -Force | Out-Null
    Push-Location $ProjectRoot
    try {
        & $PythonExe -m PyInstaller --version | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller를 실행할 수 없습니다."
        }

        foreach ($item in $Specs) {
            $specPath = Join-Path $ProjectRoot $item.Spec
            $specWork = Join-Path $WorkRoot ([System.IO.Path]::GetFileNameWithoutExtension($item.Spec))
            & $PythonExe -m PyInstaller --clean --noconfirm --distpath $StageDist --workpath $specWork $specPath
            if ($LASTEXITCODE -ne 0) {
                throw "PyInstaller 빌드 실패: $($item.Spec)"
            }
        }
    }
    finally {
        Pop-Location
    }

    Assert-ExactExecutables -Directory $StageDist -ExpectedNames $ExpectedExeNames

    if (Test-Path -LiteralPath $DistRoot) {
        Remove-Item -LiteralPath $DistRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $DistRoot -Force | Out-Null
    foreach ($name in $ExpectedExeNames) {
        Copy-FileWithRetry -Source (Join-Path $StageDist $name) -Destination (Join-Path $DistRoot $name)
    }
    Assert-ExactExecutables -Directory $DistRoot -ExpectedNames $ExpectedExeNames

    $SyncRoots = @($ProjectRoot, $CustomerRoot, $FinalRoot)
    foreach ($name in $ExpectedExeNames) {
        $source = Join-Path $DistRoot $name
        $expectedHash = Get-FileSha256 -Path $source
        foreach ($targetRoot in $SyncRoots) {
            $target = Join-Path $targetRoot $name
            Copy-FileWithRetry -Source $source -Destination $target
            $actualHash = Get-FileSha256 -Path $target
            if ($actualHash -ne $expectedHash) {
                throw "EXE 동기화 해시 불일치: $target"
            }
        }
    }

    # Synchronize verified source guides before inventory/hash generation.
    # HTML preview sources stay under docs and are never shipped to customers.
    foreach ($name in $CustomerGuideNames) {
        $source = Join-Path $ProjectRoot $name
        $expectedHash = Get-FileSha256 -Path $source
        foreach ($targetRoot in @($CustomerRoot, $FinalRoot)) {
            $target = Join-Path $targetRoot $name
            Copy-FileWithRetry -Source $source -Destination $target
            if ((Get-FileSha256 -Path $target) -ne $expectedHash) {
                throw "고객 안내 동기화 해시 불일치: $target"
            }
        }
    }

    Push-Location $ProjectRoot
    try {
        & $PythonExe -m barcode_label_automation.release_manifest `
            --base-dir $CustomerRoot `
            --source-root $ProjectRoot `
            --package-name $PackageName `
            --package-version $Version `
            --build-id $BuildId `
            --test-result $TestResult
        if ($LASTEXITCODE -ne 0) {
            throw "고객 폴더 release manifest 검증에 실패했습니다."
        }
    }
    finally {
        Pop-Location
    }

    foreach ($metadataName in @("release_manifest.json", "배포_파일목록.txt", "버전정보.txt")) {
        $metadataSource = Join-Path $CustomerRoot $metadataName
        Copy-FileWithRetry -Source $metadataSource -Destination (Join-Path $ProjectRoot $metadataName)
        Copy-FileWithRetry -Source $metadataSource -Destination (Join-Path $FinalRoot $metadataName)
    }

    Write-Host "릴리스 게이트 통과: $Version ($BuildId)"
    Write-Host "동기화 위치: $($SyncRoots -join ', ')"
}
finally {
    if ($lockStream) {
        $lockStream.Dispose()
    }
    if (Test-Path -LiteralPath $BuildRoot) {
        Assert-ChildPath -Root $ProjectRoot -Path $BuildRoot
        Remove-Item -LiteralPath $BuildRoot -Recurse -Force
    }
    if (Test-Path -LiteralPath $LockPath) {
        Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue
    }
}
