[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }),
    [switch]$SkipUpdateCheck,
    [switch]$SkipCliInstall,
    [switch]$SkipLogin,
    [switch]$SkipCreditCheck
)

$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$imageRoot = Join-Path $root "packages\Codex_image"
$dtRoot = Join-Path $root "packages\Codex_DT"
$gifRoot = Join-Path $root "packages\Codex_Gif"
$githubRoot = Join-Path $root "packages\Codex_Github"
$seedanceWrapper = Join-Path $imageRoot "CLI\Seedance-CLI\run.ps1"
$previewTool = Join-Path $CodexHome "tools\Convert-CodexImagePreview.ps1"

function Invoke-CheckedPowerShell {
    param([string]$File, [string[]]$Arguments = @())

    Write-Host ""
    Write-Host "Running: $File"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Deployment step failed with exit code ${LASTEXITCODE}: $File"
    }
}

foreach ($command in @("git", "python", "powershell.exe")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command is missing: $command"
    }
}
foreach ($directory in @($imageRoot, $dtRoot, $gifRoot, $githubRoot)) {
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        throw "Required project directory is missing: $directory"
    }
}

Invoke-CheckedPowerShell -File (Join-Path $root "scripts\deployment\install-environment.ps1") -Arguments @("-InstallMissingTools")

if (-not $SkipUpdateCheck) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "start-task.ps1") -RepositoryRoot $root
    $updateExit = $LASTEXITCODE
    if ($updateExit -notin @(0, 2)) {
        throw "The checkout is not safe to deploy until its Git update state is resolved."
    }
}

Invoke-CheckedPowerShell -File (Join-Path $root "scripts\codex\sync-global-codex.ps1") -Arguments @("-RepositoryRoot", $root, "-CodexHome", $CodexHome, "-Yes")

$legacyItems = @(
    (Join-Path $imageRoot "CLI\.env"),
    (Join-Path $imageRoot "CLI\Seedance-CLI\dreamina.exe"),
    (Join-Path $imageRoot "CLI\Gemini-CLI\agy.exe")
)
if ($legacyItems | Where-Object { Test-Path -LiteralPath $_ }) {
    Invoke-CheckedPowerShell -File (Join-Path $imageRoot "migrate-private-runtime.ps1")
}

if (-not $SkipCliInstall) {
    $installArgs = @("-Pipeline", "seedance-cli")
    if ($SkipLogin) { $installArgs += "-SkipLogin" }
    Invoke-CheckedPowerShell -File (Join-Path $imageRoot "install-cli-pipeline.ps1") -Arguments $installArgs
}

$imageDeployArgs = @("-CodexHome", $CodexHome)
if ($SkipLogin) { $imageDeployArgs += "-SkipLoginCheck" }
Invoke-CheckedPowerShell -File (Join-Path $imageRoot "deploy-project.ps1") -Arguments $imageDeployArgs

$dtDeployArgs = @("-PreviewTool", $previewTool, "-SeedanceCli", $seedanceWrapper)
if ($SkipCreditCheck -or $SkipLogin) { $dtDeployArgs += "-SkipCreditCheck" }
Invoke-CheckedPowerShell -File (Join-Path $dtRoot "scripts\deploy_project.ps1") -Arguments $dtDeployArgs
Invoke-CheckedPowerShell -File (Join-Path $githubRoot "register-global-skill.ps1") -Arguments @("-CodexHome", $CodexHome)
Invoke-CheckedPowerShell -File (Join-Path $gifRoot "register-global-skill.ps1") -Arguments @("-CodexHome", $CodexHome)
Invoke-CheckedPowerShell -File (Join-Path $root "scripts\maintenance\verify-deployment.ps1") -Arguments @("-RepositoryRoot", $root, "-CodexHome", $CodexHome)

Write-Host ""
Write-Host "New-machine deployment complete." -ForegroundColor Green
Write-Host "Restart Codex, then run .\start-task.ps1 before beginning work on an older computer."
Write-Host "API keys are intentionally not copied by Git. Configure missing keys with:"
Write-Host "  .\packages\Codex_image\configure-api-key.ps1 -Pipeline comfly-api"
Write-Host "  .\packages\Codex_image\configure-api-key.ps1 -Pipeline gpt-api"
Write-Host "  .\packages\Codex_image\configure-api-key.ps1 -Pipeline gemini-api"
