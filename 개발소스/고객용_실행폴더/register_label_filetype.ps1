param(
    [string]$DesignerExe = "",
    [string]$RollbackPath = "",
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DesignerExe)) {
    $DesignerExe = Join-Path $PSScriptRoot "라벨디자이너.exe"
}
if (-not (Test-Path -LiteralPath $DesignerExe -PathType Leaf)) {
    throw "라벨디자이너.exe 파일을 찾을 수 없습니다: $DesignerExe"
}
$exePath = (Resolve-Path -LiteralPath $DesignerExe).Path
$arguments = @("--register-file-associations")
if (-not [string]::IsNullOrWhiteSpace($RollbackPath)) {
    $resolvedRollbackPath = (Resolve-Path -LiteralPath $RollbackPath).Path
    $arguments = @("--restore-file-associations", ('"{0}"' -f $resolvedRollbackPath))
}
$process = Start-Process -FilePath $exePath -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "파일 연결 등록 또는 복원에 실패했습니다. 종료 코드: $($process.ExitCode)"
}
if (-not $Quiet) {
    if ($RollbackPath) {
        Write-Host "채움랩이 변경한 파일 연결값을 복원했습니다."
    } else {
        Write-Host ".cllabel / .clproject 및 기존 .gblabel / .gbproject 파일 연결 후보를 등록했습니다."
        Write-Host "기존 사용자 기본 앱 선택은 유지됩니다."
    }
}
