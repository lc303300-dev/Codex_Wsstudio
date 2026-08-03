[CmdletBinding()]
param([switch]$CheckOnly)

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$rootScript = Join-Path $repositoryRoot "start-task.ps1"
if (-not (Test-Path -LiteralPath $rootScript -PathType Leaf)) {
    throw "Shared task-start script not found: $rootScript"
}
$arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $rootScript, "-RepositoryRoot", $repositoryRoot)
if ($CheckOnly) {
    $arguments += "-CheckOnly"
}
& powershell.exe @arguments
exit $LASTEXITCODE
