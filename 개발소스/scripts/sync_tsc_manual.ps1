[CmdletBinding()]
param(
    [string]$Url = "",
    [string]$LocalSource = "F:\0.이근우과장\새 폴더\TSC메뉴얼\TSPL_TSPL2_Programming.pdf",
    [string]$Destination = "",
    [string]$ExpectedSha256 = "45898D837D807F0134377C85B52D04D9458F291E68A512218848730A2B7DEF65"
)

$ErrorActionPreference = "Stop"

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Assert-ExpectedHash {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([string]::IsNullOrWhiteSpace($ExpectedSha256)) {
        return
    }

    $actual = Get-Sha256 -Path $Path
    if ($actual -ne $ExpectedSha256.ToUpperInvariant()) {
        throw "TSC manual hash mismatch. Expected $ExpectedSha256 but got $actual for $Path"
    }
}

if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = Join-Path $PSScriptRoot "..\references\tsc\TSPL_TSPL2_Programming.pdf"
}

$destinationFullPath = [System.IO.Path]::GetFullPath($Destination)
$destinationDir = Split-Path -Parent $destinationFullPath
New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null

$downloaded = $false
$tempFile = Join-Path ([System.IO.Path]::GetTempPath()) ("tsc-tspl2-manual-" + [System.Guid]::NewGuid().ToString("N") + ".pdf")

if (-not [string]::IsNullOrWhiteSpace($Url)) {
    try {
        $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
        if ($curl) {
            & $curl.Source -fL --retry 2 --connect-timeout 15 --max-time 120 -o $tempFile $Url 2>$null
            if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $tempFile)) {
                Assert-ExpectedHash -Path $tempFile
                Copy-Item -LiteralPath $tempFile -Destination $destinationFullPath -Force
                $downloaded = $true
            }
        }

        if (-not $downloaded) {
            Invoke-WebRequest -Uri $Url -OutFile $tempFile -UseBasicParsing -MaximumRedirection 5 -TimeoutSec 120
            Assert-ExpectedHash -Path $tempFile
            Copy-Item -LiteralPath $tempFile -Destination $destinationFullPath -Force
            $downloaded = $true
        }
    }
    catch {
        Write-Warning ("Official URL download failed: " + $_.Exception.Message)
        Write-Warning ("Falling back to LocalSource or existing Destination.")
    }
    finally {
        if (Test-Path -LiteralPath $tempFile) {
            Remove-Item -LiteralPath $tempFile -Force
        }
    }
}

if (-not $downloaded) {
    if (Test-Path -LiteralPath $LocalSource) {
        Assert-ExpectedHash -Path $LocalSource
        Copy-Item -LiteralPath $LocalSource -Destination $destinationFullPath -Force
    }
    elseif (Test-Path -LiteralPath $destinationFullPath) {
        Assert-ExpectedHash -Path $destinationFullPath
    }
    else {
        throw "TSC manual was not downloaded, LocalSource does not exist, and Destination is missing: $LocalSource"
    }
}

Assert-ExpectedHash -Path $destinationFullPath
Write-Host "TSC manual ready: $destinationFullPath"
Write-Host ("SHA256: " + (Get-Sha256 -Path $destinationFullPath))
