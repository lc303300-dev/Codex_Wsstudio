[CmdletBinding()]
param([switch]$CheckOnly)

$scriptPath = $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($scriptPath)) {
    throw "Unable to determine the path of Codex_image\start-task.ps1."
}
$scriptDirectory = Split-Path -Parent ([System.IO.Path]::GetFullPath($scriptPath))
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDirectory "..")).Path
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
