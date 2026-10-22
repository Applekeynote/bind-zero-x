param([int]$Port = 8765, [switch]$Mobile, [string]$MobileIP = '', [int]$MobilePort = 8766)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$projectPython = Join-Path $projectRoot '.venv5\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    $projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Run Setup.ps1 with Python 3.12+ first. See README.md.'
}
$env:TEMP = Join-Path $projectRoot '.tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
Write-Host "BIND ZERO-X: http://127.0.0.1:$Port  (Ctrl+C to stop)"
$serverArguments = @((Join-Path $projectRoot 'app\console_server.py'), '--port', $Port)
if ($Mobile) { $serverArguments += @('--mobile', '--mobile-port', $MobilePort) }
if ($Mobile -and -not $MobileIP) {
    $networkWithGateway = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1
    if ($networkWithGateway) { $MobileIP = $networkWithGateway.IPv4Address.IPAddress | Select-Object -First 1 }
}
if ($MobileIP) { $serverArguments += @('--mobile-ip', $MobileIP) }
& $projectPython @serverArguments
