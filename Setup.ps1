param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:TEMP = Join-Path $PSScriptRoot '.tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
& $Python -m venv .venv5
if ($LASTEXITCODE -ne 0) { throw 'Python venv creation failed. Supply -Python with a Python 3.12+ executable.' }
& (Join-Path $PSScriptRoot '.venv5\Scripts\python.exe') -m pip install --upgrade 'pip==26.2.2'
if ($LASTEXITCODE -ne 0) { throw 'Secure package installer setup failed.' }
& (Join-Path $PSScriptRoot '.venv5\Scripts\python.exe') -m pip install -r (Join-Path $PSScriptRoot 'requirements-opencv5.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& (Join-Path $PSScriptRoot '.venv5\Scripts\python.exe') -m pip install -r (Join-Path $PSScriptRoot 'requirements-segmentation.txt')
if ($LASTEXITCODE -ne 0) { throw 'Segmentation model tools installation failed.' }
& (Join-Path $PSScriptRoot '.venv5\Scripts\python.exe') (Join-Path $PSScriptRoot 'scripts\install_segmentation_model.py')
if ($LASTEXITCODE -ne 0) { throw 'Verified segmentation model installation failed.' }
Write-Host 'Ready. Run: .\Start.ps1'
