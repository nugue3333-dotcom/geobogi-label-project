[CmdletBinding()]
param(
    [string]$OutputRoot,
    [switch]$IncludeSampleWorkbooks,
    [switch]$NoZip
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $ProjectRoot "배포패키지"
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmm"
$PackageName = "거복이의꿈_바코드운영패키지_$Stamp"
$PackageDir = Join-Path $OutputRoot $PackageName

$RequiredFiles = @(
    "라벨출력관리.exe",
    "라벨디자이너.exe",
    "프린터설정.exe",
    "print_labels.exe",
    "config.example.ini",
    "사용안내.txt",
    "라벨출력패키지_고객용_매뉴얼.docx",
    "index.html"
)

foreach ($file in $RequiredFiles) {
    $path = Join-Path $ProjectRoot $file
    if (-not (Test-Path $path)) {
        throw "필수 파일이 없습니다: $file"
    }
}

New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

foreach ($file in $RequiredFiles) {
    Copy-Item -Path (Join-Path $ProjectRoot $file) -Destination $PackageDir -Force
}

Copy-Item -Path (Join-Path $ProjectRoot "config.example.ini") -Destination (Join-Path $PackageDir "config.ini") -Force

$templateSource = Join-Path $ProjectRoot "templates"
if (Test-Path $templateSource) {
    Copy-Item -Path $templateSource -Destination (Join-Path $PackageDir "templates") -Recurse -Force
}

$assetSource = Join-Path $ProjectRoot "assets\higgsfield\hero.png"
if (Test-Path $assetSource) {
    $assetTarget = Join-Path $PackageDir "assets\higgsfield"
    New-Item -ItemType Directory -Force -Path $assetTarget | Out-Null
    Copy-Item -Path $assetSource -Destination (Join-Path $assetTarget "hero.png") -Force
}

if ($IncludeSampleWorkbooks) {
    foreach ($file in @("print_queue.xlsx", "barcode_db.xlsx")) {
        $path = Join-Path $ProjectRoot $file
        if (Test-Path $path) {
            Copy-Item -Path $path -Destination (Join-Path $PackageDir $file) -Force
        }
    }
}

$guidePath = Join-Path $PackageDir "고객_시작안내.txt"
@"
거복이의꿈 바코드 운영 패키지

1. 먼저 프린터설정.exe에서 프린터 연결 방식과 라벨 규격을 확인하세요.
2. 라벨디자이너.exe에서 라벨 양식을 확인하거나 수정하세요.
3. 라벨출력관리.exe에서 출력 목록과 바코드 데이터를 확인하세요.
4. 실제 프린터 출력 전 미리보기 또는 dry-run 기준으로 데이터를 점검하세요.
5. 프린터 모델, 스캐너 모델, 설치지원, 보증/환불/배송 조건은 판매자와 확정한 문서를 따르세요.

주의:
- 개인정보, 결제 정보, 주문 원문을 로그나 공유 파일에 넣지 마세요.
- 바코드 값은 앞자리 0이 사라지지 않도록 문자로 관리하세요.
- config.ini는 고객 환경에 맞게 조정한 뒤 사용하세요.
"@ | Set-Content -Path $guidePath -Encoding UTF8

$zipPath = $null
if (-not $NoZip) {
    $zipPath = "$PackageDir.zip"
    if (Test-Path $zipPath) {
        Remove-Item -Path $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $zipPath -Force
}

[PSCustomObject]@{
    PackageDir = $PackageDir
    ZipPath = $zipPath
    IncludeSampleWorkbooks = [bool]$IncludeSampleWorkbooks
}

