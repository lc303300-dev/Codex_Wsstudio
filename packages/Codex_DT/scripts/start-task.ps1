[CmdletBinding()]
param([switch]$CheckOnly)

$scriptPath = $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($scriptPath)) {
    throw "Unable to determine the path of Codex_DT\scripts\start-task.ps1."
}
$scriptDirectory = Split-Path -Parent ([System.IO.Path]::GetFullPath($scriptPath))
$projectRoot = Split-Path $scriptDirectory -Parent
$rootScript = Join-Path (Split-Path (Split-Path $projectRoot -Parent) -Parent) "start-task.ps1"
if (-not (Test-Path -LiteralPath $rootScript -PathType Leaf)) {
    throw "Shared task-start script not found: $rootScript"
}
$arguments = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $rootScript,
    "-RepositoryRoot", $projectRoot
)
if ($CheckOnly) {
    $arguments += "-CheckOnly"
}
& powershell.exe @arguments
exit $LASTEXITCODE
