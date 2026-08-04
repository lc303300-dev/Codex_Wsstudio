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
$envPath = Join-Path $imageRoot ".codex-image-private\.env"

function Invoke-CheckedPowerShell {
    param(
        [string]$File,
        [string[]]$Arguments = @()
    )

    Write-Host ""
    Write-Host "Running: $File"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed with exit code ${LASTEXITCODE}: $File"
    }
}

function Ask-YesNo {
    param([string]$Question, [bool]$DefaultYes = $true)

    $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
    $answer = Read-Host "$Question $suffix"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $DefaultYes }
    return $answer.Trim().ToLowerInvariant() -in @("y", "yes")
}

function Test-KeyPresent {
    param([string]$Path, [string]$KeyName)

    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match "^\s*$([regex]::Escape($KeyName))\s*=") {
            return $true
        }
    }
    return $false
}

function Show-KeyChecklist {
    Write-Host ""
    Write-Host "Please prepare the following API keys before deployment:" -ForegroundColor Yellow
    Write-Host "  COMFLY_API_KEY   https://ai.comfly.org/"
    Write-Host "  APIMART_API_KEY  https://apimart.ai/zh"
    Write-Host "  GEMINI_API_KEY   https://aistudio.google.com/"
    Write-Host "Please sign in ahead of time to Dreamina/Jimeng:"
    Write-Host "  https://jimeng.jianying.com/"
    Write-Host ""
    Write-Host "Copy-fill template:"
    Write-Host "  COMFLY_API_KEY="
    Write-Host "  APIMART_API_KEY="
    Write-Host "  GEMINI_API_KEY="
    Write-Host ""
    Write-Host "Everything else, including Codex config paths, is handled automatically."
}

Write-Host "New machine deployment template"
Write-Host "This script will configure keys, then run the repository bootstrap."
Write-Host "Codex home: $CodexHome"
Show-KeyChecklist

foreach ($item in @(
    @{ Pipeline = "comfly-api"; Label = "COMFLY_API_KEY" },
    @{ Pipeline = "gpt-api"; Label = "APIMART_API_KEY" },
    @{ Pipeline = "gemini-api"; Label = "GEMINI_API_KEY" }
)) {
    $present = Test-KeyPresent -Path $envPath -KeyName $item.Label
    $shouldConfigure = if ($present) {
        Ask-YesNo "$($item.Label) already exists. Reconfigure it?" $false
    } else {
        Ask-YesNo "Configure $($item.Label) now?" $true
    }
    if ($shouldConfigure) {
        Invoke-CheckedPowerShell -File (Join-Path $imageRoot "configure-api-key.ps1") -Arguments @("-Pipeline", $item.Pipeline, "-EnvFile", $envPath)
    }
}

$bootstrapArgs = @()
if (-not [string]::IsNullOrWhiteSpace($CodexHome)) {
    $bootstrapArgs += @("-CodexHome", $CodexHome)
}
if ($SkipUpdateCheck) { $bootstrapArgs += "-SkipUpdateCheck" }
if ($SkipCliInstall) { $bootstrapArgs += "-SkipCliInstall" }
if ($SkipLogin) { $bootstrapArgs += "-SkipLogin" }
if ($SkipCreditCheck) { $bootstrapArgs += "-SkipCreditCheck" }

Invoke-CheckedPowerShell -File (Join-Path $root "scripts\deployment\bootstrap-new-machine.ps1") -Arguments $bootstrapArgs

Write-Host ""
Write-Host "Deployment complete."
Write-Host "If this is the first time on the machine, restart Codex before starting work."
Write-Host "Safe key file: $envPath"
