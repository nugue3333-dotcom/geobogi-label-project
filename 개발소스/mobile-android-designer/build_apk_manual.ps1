[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$AppRoot = $PSScriptRoot
$SourceRoot = Split-Path -Parent $AppRoot

# Android build-tools can fail to open resources below a Korean path. Re-enter
# the same source tree through a temporary ASCII drive so local builds remain
# reproducible without copying the SDK or project.
if ($SourceRoot -match '[^\x00-\x7F]' -and $env:CHAEUMLAB_ASCII_BUILD -ne "1") {
    $drive = @("R:", "S:", "T:", "U:", "V:", "W:", "X:", "Y:", "Z:") |
        Where-Object { -not (Test-Path $_) } |
        Select-Object -First 1
    if (-not $drive) {
        throw "No free drive letter is available for the Android ASCII-path build."
    }
    $driveName = $drive.TrimEnd("\")
    cmd.exe /c "subst $driveName `"$SourceRoot`"" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the temporary Android build drive."
    }
    try {
        $env:CHAEUMLAB_ASCII_BUILD = "1"
        & "$drive\mobile-android-designer\build_apk_manual.ps1"
        if ($LASTEXITCODE -ne 0) {
            throw "Android build failed through the temporary build drive."
        }
    }
    finally {
        Remove-Item Env:CHAEUMLAB_ASCII_BUILD -ErrorAction SilentlyContinue
        cmd.exe /c "subst $driveName /d" | Out-Null
    }
    return
}

$ToolsRoot = Join-Path $SourceRoot ".build-tools"
$JavaHome = Join-Path $ToolsRoot "jdk\jdk-17.0.19+10"
$AndroidSdk = Join-Path $ToolsRoot "android-sdk"
$BuildTools = Join-Path $AndroidSdk "build-tools\35.0.0"
$AndroidJar = Join-Path $AndroidSdk "platforms\android-35\android.jar"

$Aapt2 = Join-Path $BuildTools "aapt2.exe"
$D8 = Join-Path $BuildTools "d8.bat"
$Zipalign = Join-Path $BuildTools "zipalign.exe"
$ApkSigner = Join-Path $BuildTools "apksigner.bat"
$Javac = Join-Path $JavaHome "bin\javac.exe"
$Keytool = Join-Path $JavaHome "bin\keytool.exe"
$Jar = Join-Path $JavaHome "bin\jar.exe"

foreach ($required in @($Aapt2, $D8, $Zipalign, $ApkSigner, $Javac, $Keytool, $Jar, $AndroidJar)) {
    if (-not (Test-Path $required)) {
        throw "Required build tool not found: $required"
    }
}

$BuildDir = Join-Path $AppRoot "build-manual"
$DistDir = Join-Path $AppRoot "dist"
$GenDir = Join-Path $BuildDir "gen"
$ClassesDir = Join-Path $BuildDir "classes"
$DexDir = Join-Path $BuildDir "dex"
$ResZip = Join-Path $BuildDir "resources.zip"
$UnsignedApk = Join-Path $BuildDir "designer-unsigned.apk"
$AlignedApk = Join-Path $BuildDir "designer-aligned.apk"
$FinalApk = Join-Path $DistDir "mobile-label-designer-debug.apk"
$KoreanApk = Join-Path $DistDir "채움LAB_모바일라벨-debug.apk"
$SourcesFile = Join-Path $BuildDir "sources.txt"
$ManifestForBuild = Join-Path $BuildDir "AndroidManifest.xml"
$ClassesJar = Join-Path $BuildDir "classes.jar"
$SigningDir = Join-Path $AppRoot "signing"
$DebugKeystore = Join-Path $SigningDir "chaeumlab-sideload.keystore"

if ((Test-Path $BuildDir) -and ((Resolve-Path $BuildDir).Path.StartsWith((Resolve-Path $AppRoot).Path))) {
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
}
New-Item -ItemType Directory -Force $BuildDir, $DistDir, $GenDir, $ClassesDir, $DexDir, $SigningDir | Out-Null

$env:JAVA_HOME = $JavaHome
$env:ANDROID_HOME = $AndroidSdk
$env:ANDROID_SDK_ROOT = $AndroidSdk
$env:PATH = "$JavaHome\bin;$BuildTools;$AndroidSdk\platform-tools;$env:PATH"

function Assert-ExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

$ManifestText = Get-Content -Raw -LiteralPath (Join-Path $AppRoot "app\src\main\AndroidManifest.xml")
if ($ManifestText -notmatch '\spackage=') {
    $ManifestText = $ManifestText -replace '<manifest xmlns:android="http://schemas.android.com/apk/res/android">', '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="kr.chaeumlab.mobilelabel">'
}
Set-Content -LiteralPath $ManifestForBuild -Value $ManifestText -Encoding UTF8

& $Aapt2 compile --dir (Join-Path $AppRoot "app\src\main\res") -o $ResZip
Assert-ExitCode "aapt2 compile"
& $Aapt2 link `
    -o $UnsignedApk `
    -I $AndroidJar `
    --manifest $ManifestForBuild `
    --java $GenDir `
    --custom-package com.geoboki.labeldesigner `
    --min-sdk-version 23 `
    --target-sdk-version 35 `
    --version-code 4 `
    --version-name 0.3.1 `
    --auto-add-overlay `
    $ResZip
Assert-ExitCode "aapt2 link"

$SourceFiles = @()
$SourceFiles += Get-ChildItem -Path (Join-Path $AppRoot "app\src\main\java") -Recurse -Filter "*.java" | Select-Object -ExpandProperty FullName
$SourceFiles += Get-ChildItem -Path $GenDir -Recurse -Filter "*.java" | Select-Object -ExpandProperty FullName
$SourceFiles | ForEach-Object { '"' + ($_.Replace("\", "/")) + '"' } | Set-Content -LiteralPath $SourcesFile -Encoding UTF8

& $Javac -encoding UTF-8 -source 17 -target 17 -classpath $AndroidJar -d $ClassesDir ("@" + $SourcesFile)
Assert-ExitCode "javac"
& $Jar cf $ClassesJar -C $ClassesDir "."
Assert-ExitCode "jar classes"
cmd.exe /c "`"$D8`" --lib `"$AndroidJar`" --min-api 23 --output `"$DexDir`" `"$ClassesJar`""
Assert-ExitCode "d8"
& $Jar uf $UnsignedApk -C $DexDir "classes.dex"
Assert-ExitCode "jar apk"
& $Zipalign -f 4 $UnsignedApk $AlignedApk
Assert-ExitCode "zipalign"

if (-not (Test-Path $DebugKeystore)) {
    & $Keytool -genkeypair `
        -keystore $DebugKeystore `
        -storepass android `
        -keypass android `
        -alias androiddebugkey `
        -keyalg RSA `
        -keysize 2048 `
        -validity 10000 `
        -dname "CN=ChaeumLAB Mobile Sideload,O=ChaeumLAB,C=KR" | Out-Null
    Assert-ExitCode "keytool"
}

cmd.exe /c "`"$ApkSigner`" sign --ks `"$DebugKeystore`" --ks-pass pass:android --key-pass pass:android --out `"$FinalApk`" `"$AlignedApk`""
Assert-ExitCode "apksigner sign"
cmd.exe /c "`"$ApkSigner`" verify --verbose `"$FinalApk`""
Assert-ExitCode "apksigner verify"

Copy-Item -LiteralPath $FinalApk -Destination $KoreanApk -Force

Get-Item $FinalApk, $KoreanApk
