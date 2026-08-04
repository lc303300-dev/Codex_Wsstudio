$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"
$entry = Join-Path $PSScriptRoot "server.py"
$python = Get-Command py.exe -ErrorAction SilentlyContinue
if ($null -ne $python) { & $python.Source -3 -B $entry; exit $LASTEXITCODE }
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if ($null -ne $python -and $python.Source -notlike "*WindowsApps*") { & $python.Source -B $entry; exit $LASTEXITCODE }
$bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path -LiteralPath $bundled)) { throw "Python is unavailable. Install Python 3 or run from Codex." }
& $bundled -B $entry
exit $LASTEXITCODE
