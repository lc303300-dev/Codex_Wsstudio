$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"
$python = Get-Command py.exe -ErrorAction SilentlyContinue
if ($null -ne $python) { & $python.Source (Join-Path $PSScriptRoot "comfly_api.py") @args; exit $LASTEXITCODE }
$python = Get-Command python.exe -ErrorAction SilentlyContinue
if ($null -ne $python -and $python.Source -notlike "*WindowsApps*") { & $python.Source (Join-Path $PSScriptRoot "comfly_api.py") @args; exit $LASTEXITCODE }
$bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path -LiteralPath $bundled)) { throw "Python is unavailable. Install Python 3 or run from Codex." }
& $bundled (Join-Path $PSScriptRoot "comfly_api.py") @args
exit $LASTEXITCODE
