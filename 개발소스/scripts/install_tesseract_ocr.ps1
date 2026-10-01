param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
    Write-Host "[ocr] $Message"
}

function Test-TesseractExe([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $probeDir = Join-Path (Split-Path -Parent $Path) '_probe'
    New-Item -ItemType Directory -Force -Path $probeDir | Out-Null
    $out = Join-Path $probeDir 'version.out.txt'
    $err = Join-Path $probeDir 'version.err.txt'
    try {
        $process = Start-Process -FilePath $Path -ArgumentList '--version' -Wait -PassThru -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err
        return $process.ExitCode -eq 0
    } catch {
        return $false
    }
}

function Find-TesseractExe([string]$InstallDir) {
    $candidates = @(
        (Join-Path $InstallDir 'tesseract.exe'),
        (Join-Path $InstallDir 'Tesseract-OCR\tesseract.exe'),
        'C:\Program Files\Tesseract-OCR\tesseract.exe',
        'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
    )
    $pathCommand = Get-Command 'tesseract.exe' -ErrorAction SilentlyContinue
    if ($pathCommand) {
        $candidates += $pathCommand.Source
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $resolved = (Get-Item -LiteralPath $candidate).FullName
            if (Test-TesseractExe $resolved) {
                return $resolved
            }
        }
    }
    return $null
}

function Copy-TesseractRuntime([string]$SourceExe, [string]$InstallDir) {
    $sourceDir = Split-Path -Parent $SourceExe
    $resolvedSource = [System.IO.Path]::GetFullPath($sourceDir)
    $resolvedTarget = [System.IO.Path]::GetFullPath($InstallDir)
    if ($resolvedSource.Equals($resolvedTarget, [System.StringComparison]::OrdinalIgnoreCase)) {
        return
    }
    Write-Step "Copying Tesseract runtime from $sourceDir"
    Copy-Item -LiteralPath (Join-Path $sourceDir '*') -Destination $InstallDir -Recurse -Force
}

function Optimize-TesseractRuntime([string]$InstallDir) {
    Write-Step 'Removing OCR training tools that are not needed at customer runtime'
    $trainingExeNames = @(
        'ambiguous_words.exe',
        'classifier_tester.exe',
        'cntraining.exe',
        'combine_lang_model.exe',
        'combine_tessdata.exe',
        'dawg2wordlist.exe',
        'lstmeval.exe',
        'lstmtraining.exe',
        'merge_unicharsets.exe',
        'mftraining.exe',
        'set_unicharset_properties.exe',
        'shapeclustering.exe',
        'tesseract-uninstall.exe',
        'text2image.exe',
        'unicharset_extractor.exe',
        'wordlist2dawg.exe'
    )
    foreach ($name in $trainingExeNames) {
        $path = Join-Path $InstallDir $name
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force
        }
    }
    Get-ChildItem -LiteralPath $InstallDir -Filter '*.html' -File -ErrorAction SilentlyContinue | Remove-Item -Force
    $tessdataDir = Join-Path $InstallDir 'tessdata'
    foreach ($path in @(
        (Join-Path $tessdataDir 'osd.traineddata'),
        (Join-Path $tessdataDir 'jaxb-api-2.3.1.jar'),
        (Join-Path $tessdataDir 'piccolo2d-core-3.0.1.jar'),
        (Join-Path $tessdataDir 'piccolo2d-extras-3.0.1.jar'),
        (Join-Path $tessdataDir 'ScrollView.jar')
    )) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force
        }
    }
}

function Download-TrainedData([string]$TessdataDir, [string]$Language) {
    $target = Join-Path $TessdataDir "$Language.traineddata"
    if (Test-Path -LiteralPath $target) {
        return
    }
    $url = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/$Language.traineddata"
    Write-Step "Downloading $Language.traineddata"
    Invoke-WebRequest -Uri $url -OutFile $target -UseBasicParsing
}

function Install-WithWinget([string]$InstallDir) {
    $winget = Get-Command 'winget.exe' -ErrorAction SilentlyContinue
    if (-not $winget) {
        return $false
    }
    Write-Step 'Installing Tesseract OCR with winget'
    & $winget.Source install --id UB-Mannheim.TesseractOCR --exact --silent --accept-source-agreements --accept-package-agreements --location $InstallDir
    return $LASTEXITCODE -eq 0
}

function Install-WithDirectInstaller([string]$InstallDir) {
    $downloadDir = Join-Path $InstallDir '_download'
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $installerUrls = @(
        'https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.5.0.20241111.exe',
        'https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.4.0.20240606.exe',
        'https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe'
    )
    foreach ($url in $installerUrls) {
        $installer = Join-Path $downloadDir (Split-Path -Leaf $url)
        try {
            if (-not (Test-Path -LiteralPath $installer)) {
                Write-Step "Downloading Tesseract installer: $url"
                Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
            }
            Write-Step "Running Tesseract installer: $installer"
            $process = Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=$InstallDir") -Wait -PassThru -WindowStyle Hidden
            if ($process.ExitCode -eq 0 -and (Find-TesseractExe $InstallDir)) {
                return $true
            }
        } catch {
            Write-Step "Installer attempt failed: $($_.Exception.Message)"
        }
    }
    return $false
}

$installDir = Join-Path $ProjectRoot 'tools\ocr'
$tessdataDir = Join-Path $installDir 'tessdata'
New-Item -ItemType Directory -Force -Path $installDir, $tessdataDir | Out-Null

$tesseractExe = Find-TesseractExe $installDir
if (-not $tesseractExe) {
    $null = Install-WithWinget $installDir
    $tesseractExe = Find-TesseractExe $installDir
}
if (-not $tesseractExe) {
    $null = Install-WithDirectInstaller $installDir
    $tesseractExe = Find-TesseractExe $installDir
}

if (-not $tesseractExe) {
    throw 'Tesseract OCR installation failed. Expected tesseract.exe in tools\ocr or Program Files.'
}

Copy-TesseractRuntime $tesseractExe $installDir
$bundledExe = Join-Path $installDir 'tesseract.exe'
if (-not (Test-TesseractExe $bundledExe)) {
    $currentExe = Find-TesseractExe $installDir
    if ($currentExe) {
        Copy-TesseractRuntime $currentExe $installDir
    }
}

Download-TrainedData $tessdataDir 'eng'
Download-TrainedData $tessdataDir 'kor'
Optimize-TesseractRuntime $installDir

Write-Step 'Validating Tesseract OCR'
& $bundledExe --version | Select-Object -First 1
& $bundledExe --list-langs --tessdata-dir $tessdataDir

$marker = Join-Path $installDir 'README.txt'
@"
채움랩 label OCR runtime

This folder is used by 라벨디자이너.exe for image-to-editable-template OCR.
Required files:
- tesseract.exe
- tessdata\eng.traineddata
- tessdata\kor.traineddata

The application searches this folder before the system PATH.
"@ | Set-Content -LiteralPath $marker -Encoding UTF8

Write-Step "Done: $installDir"
