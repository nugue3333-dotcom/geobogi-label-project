$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'GeobogiLabelMobile'
$project = Join-Path $root 'GeobogiLabelMobile.xcodeproj\project.pbxproj'

$requiredFiles = @(
    'AppView.swift',
    'AppStore.swift',
    'DocumentServices.swift',
    'GeobogiLabelMobileApp.swift',
    'LabelCommandRenderer.swift',
    'MobileModels.swift',
    'PrinterLANClient.swift'
)

foreach ($file in $requiredFiles) {
    $path = Join-Path $source $file
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing source: $file" }
    $projectText = Get-Content -LiteralPath $project -Raw
    if ($projectText -notmatch [regex]::Escape("$file in Sources")) { throw "Not in Xcode Sources: $file" }
}

$models = Get-Content -LiteralPath (Join-Path $source 'MobileModels.swift') -Raw
$renderer = Get-Content -LiteralPath (Join-Path $source 'LabelCommandRenderer.swift') -Raw
$store = Get-Content -LiteralPath (Join-Path $source 'AppStore.swift') -Raw
$view = Get-Content -LiteralPath (Join-Path $source 'AppView.swift') -Raw

$checks = @(
    @{ Name = 'Blank template'; Text = $models; Pattern = 'elements: \[LabelElement\] = \[\]' },
    @{ Name = 'PC JSON type'; Text = $models; Pattern = 'case type, text, x, y, width, height' },
    @{ Name = 'PC JSON field'; Text = $models; Pattern = 'case id, kind, value, field, rotation' },
    @{ Name = 'PC JSON label size'; Text = $models; Pattern = 'widthMm = "width_mm"' },
    @{ Name = 'TSC UTF-8'; Text = $renderer; Pattern = 'CODEPAGE UTF-8' },
    @{ Name = 'BIXOLON CP949'; Text = $renderer; Pattern = 'case \.bixolon:[\s\S]*encoding = koreanEncoding' },
    @{ Name = 'BIXOLON peeler blocked'; Text = $renderer; Pattern = 'settings\.mediaHandling != \.peeler' },
    @{ Name = 'SEWOO tear-off only'; Text = $renderer; Pattern = 'settings\.mediaHandling == \.tearOff' },
    @{ Name = 'Retry state'; Text = $store; Pattern = 'func retryLastPrint\(\) async' },
    @{ Name = 'Retry remaining rows'; Text = $store; Pattern = 'retryRows = Array\(rows\[index\.\.\.\]\)' },
    @{ Name = 'Send wording'; Text = $models; Pattern = 'return "명령 전송 완료"' },
    @{ Name = 'Four tabs'; Text = $view; Pattern = 'case template, data, print, settings' },
    @{ Name = 'Quantity 1-100'; Text = $view; Pattern = 'in: 1\.\.\.100' }
)

foreach ($check in $checks) {
    if ($check.Text -notmatch $check.Pattern) { throw "Contract check failed: $($check.Name)" }
    Write-Host "OK  $($check.Name)"
}

Write-Host 'Static verification passed.'
