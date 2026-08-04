[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }),
    [switch]$SkipUpdateCheck,
    [switch]$SkipCliInstall,
    [switch]$SkipLogin,
    [switch]$SkipCreditCheck
)

$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptRoot)) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$script = Join-Path $scriptRoot "scripts\deployment\new-machine-deploy.ps1"
$arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $script, "-CodexHome", $CodexHome)
if ($SkipUpdateCheck) { $arguments += "-SkipUpdateCheck" }
if ($SkipCliInstall) { $arguments += "-SkipCliInstall" }
if ($SkipLogin) { $arguments += "-SkipLogin" }
if ($SkipCreditCheck) { $arguments += "-SkipCreditCheck" }
& powershell.exe @arguments
exit $LASTEXITCODE
