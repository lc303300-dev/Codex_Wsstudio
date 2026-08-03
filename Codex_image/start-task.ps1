[CmdletBinding()]
param([switch]$CheckOnly)

$rootScript = Join-Path (Split-Path $PSScriptRoot -Parent) "start-task.ps1"
if (-not (Test-Path -LiteralPath $rootScript -PathType Leaf)) {
    throw "Shared task-start script not found: $rootScript"
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $rootScript -RepositoryRoot $PSScriptRoot -CheckOnly:$CheckOnly
exit $LASTEXITCODE
