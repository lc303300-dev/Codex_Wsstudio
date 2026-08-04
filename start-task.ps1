[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [switch]$CheckOnly
)

$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptRoot)) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) { $RepositoryRoot = $scriptRoot }
$script = Join-Path $scriptRoot "scripts\maintenance\start-task.ps1"
$arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $script, "-RepositoryRoot", $RepositoryRoot)
if ($CheckOnly) { $arguments += "-CheckOnly" }
& powershell.exe @arguments
exit $LASTEXITCODE
