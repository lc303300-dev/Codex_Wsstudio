[CmdletBinding()]
param([switch]$CheckOnly)

$projectRoot = Split-Path $PSScriptRoot -Parent
$rootScript = Join-Path (Split-Path $projectRoot -Parent) "start-task.ps1"
if (-not (Test-Path -LiteralPath $rootScript -PathType Leaf)) {
    throw "Shared task-start script not found: $rootScript"
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $rootScript -RepositoryRoot $projectRoot -CheckOnly:$CheckOnly
exit $LASTEXITCODE
