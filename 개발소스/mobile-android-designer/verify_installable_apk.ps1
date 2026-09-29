[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApkPath
)

$ErrorActionPreference = "Stop"
$SourceRoot = Split-Path -Parent $PSScriptRoot
$ResolvedApk = (Resolve-Path -LiteralPath $ApkPath).Path
$Drive = "Q:"

if (Test-Path $Drive) {
    throw "Temporary verification drive $Drive is already in use."
}

cmd.exe /c "subst $Drive `"$SourceRoot`"" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Could not create the ASCII-path verification drive."
}

try {
    $AsciiApk = "$Drive\mobile-android-designer\dist\install-verification.apk"
    Copy-Item -LiteralPath $ResolvedApk -Destination $AsciiApk -Force

    $JavaHome = "$Drive\.build-tools\jdk\jdk-17.0.19+10"
    $BuildTools = "$Drive\.build-tools\android-sdk\build-tools\35.0.0"
    $env:JAVA_HOME = $JavaHome
    $env:PATH = "$JavaHome\bin;$env:PATH"

    cmd.exe /c "`"$BuildTools\apksigner.bat`" verify --verbose --print-certs `"$AsciiApk`""
    if ($LASTEXITCODE -ne 0) {
        throw "APK signature verification failed."
    }

    & "$BuildTools\zipalign.exe" -c 4 $AsciiApk
    if ($LASTEXITCODE -ne 0) {
        throw "APK alignment verification failed."
    }

    $Badging = (& "$BuildTools\aapt.exe" dump badging $AsciiApk) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "APK manifest verification failed."
    }
    if ($Badging -notmatch "package: name='kr\.chaeumlab\.mobilelabel' versionCode='4' versionName='0\.3\.1'") {
        throw "Unexpected package ID or version."
    }
    if ($Badging -notmatch "sdkVersion:'23'") {
        throw "Unexpected minimum Android SDK."
    }
    if ($Badging -notmatch "launchable-activity: name='com\.geoboki\.labeldesigner\.MainActivity'") {
        throw "Launcher activity is missing."
    }

    Write-Output "APK_INSTALL_CONTRACT_OK"
    Write-Output "package=kr.chaeumlab.mobilelabel version=0.3.1 minSdk=23"
}
finally {
    Remove-Item -LiteralPath "$Drive\mobile-android-designer\dist\install-verification.apk" -Force -ErrorAction SilentlyContinue
    cmd.exe /c "subst $Drive /d" | Out-Null
}
