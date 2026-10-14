$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $root "out\fresh_shell_test.log"
$addresses = [System.Net.Dns]::GetHostAddresses("git.chatgpt-team.site")
"dns=$($addresses.IPAddressToString -join ',')" | Set-Content -LiteralPath $log -Encoding utf8
& node.exe -e "console.log(require('crypto').randomBytes(4).toString('hex'))" 2>&1 |
    Add-Content -LiteralPath $log -Encoding utf8
