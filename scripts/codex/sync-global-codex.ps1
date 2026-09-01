[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$RepositoryRoot,
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }),
    [switch]$Yes,
    [switch]$SkipAgents,
    [switch]$SkipConfig
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) { $RepositoryRoot = Join-Path $scriptRoot "..\.." }
$RepositoryRoot = [System.IO.Path]::GetFullPath($RepositoryRoot)
$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$sourceAgents = Join-Path $RepositoryRoot "config\codex\AGENTS.md"
$sourcePortableConfig = Join-Path $RepositoryRoot "config\codex\config.portable.toml"
$setupScript = Join-Path $RepositoryRoot "scripts\codex\setup-codex.ps1"
$targetAgents = Join-Path $CodexHome "AGENTS.md"
$targetConfig = Join-Path $CodexHome "config.toml"

if (-not (Test-Path -LiteralPath $sourceAgents -PathType Leaf)) {
    throw "Repository AGENTS.md not found: $sourceAgents"
}
if (-not (Test-Path -LiteralPath $sourcePortableConfig -PathType Leaf)) {
    throw "Portable Codex config not found: $sourcePortableConfig"
}
if (-not (Test-Path -LiteralPath $setupScript -PathType Leaf)) {
    throw "Config merge script not found: $setupScript"
}

New-Item -ItemType Directory -Path $CodexHome -Force | Out-Null

if (-not $Yes -and -not $WhatIfPreference) {
    Write-Host "This will update the global Codex files under: $CodexHome"
    Write-Host "AGENTS.md will be replaced after a backup. config.toml will be merged safely, not overwritten."
    $answer = (Read-Host "Continue? [y/N]").Trim()
    if ($answer -notmatch '^(?i:y|yes)$') {
        Write-Host "Cancelled. No files were changed."
        return
    }
}

function Backup-IfPresent {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "$Path.backup-$stamp"
    Copy-Item -LiteralPath $Path -Destination $backup -Force
    Write-Host "Backup: $backup"
    return $backup
}

if (-not $SkipAgents) {
    $sourceHash = (Get-FileHash -LiteralPath $sourceAgents -Algorithm SHA256).Hash
    $targetHash = if (Test-Path -LiteralPath $targetAgents -PathType Leaf) { (Get-FileHash -LiteralPath $targetAgents -Algorithm SHA256).Hash } else { $null }
    if ($sourceHash -eq $targetHash) {
        Write-Host "Global AGENTS.md is already current: $targetAgents"
    }
    elseif ($PSCmdlet.ShouldProcess($targetAgents, "replace global AGENTS.md from repository")) {
        Backup-IfPresent $targetAgents | Out-Null
        $temporary = "$targetAgents.tmp-$PID"
        Copy-Item -LiteralPath $sourceAgents -Destination $temporary -Force
        Move-Item -LiteralPath $temporary -Destination $targetAgents -Force
        Write-Host "Updated global AGENTS.md: $targetAgents"
    }
}

if (-not $SkipConfig) {
    if ($PSCmdlet.ShouldProcess($targetConfig, "merge portable settings into global Codex config")) {
        $configBackup = Backup-IfPresent $targetConfig
        $setupArgs = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $setupScript,
            "-CodexHome", $CodexHome,
            "-SkipBackup"
        )
        & powershell.exe @setupArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Global config merge failed with exit code ${LASTEXITCODE}."
        }
        if (Test-Path -LiteralPath $targetConfig -PathType Leaf) {
            Write-Host "Updated global config.toml: $targetConfig"
        }
        else {
            throw "Global config.toml was not created: $targetConfig"
        }
    }
}

$imageRegistration = Join-Path $RepositoryRoot "packages\Codex_image\register-default-media-tools.ps1"
if (Test-Path -LiteralPath $imageRegistration -PathType Leaf) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $imageRegistration -CodexHome $CodexHome
    if ($LASTEXITCODE -ne 0) {
        throw "Codex_image default media tool registration failed with exit code ${LASTEXITCODE}."
    }
}

$previewSource = Join-Path $RepositoryRoot "packages\Codex_image\tools\Convert-CodexImagePreview.ps1"
$previewTargetRoot = Join-Path $CodexHome "tools"
$previewTarget = Join-Path $previewTargetRoot "Convert-CodexImagePreview.ps1"
if (Test-Path -LiteralPath $previewSource -PathType Leaf) {
    New-Item -ItemType Directory -Path $previewTargetRoot -Force | Out-Null
    Copy-Item -LiteralPath $previewSource -Destination $previewTarget -Force
    Write-Host "Updated preview converter: $previewTarget"
}

$chatPathResolverSource = Join-Path $RepositoryRoot "scripts\codex\Resolve-CodexChatPath.ps1"
$chatPathResolverTarget = Join-Path $previewTargetRoot "Resolve-CodexChatPath.ps1"
if (Test-Path -LiteralPath $chatPathResolverSource -PathType Leaf) {
    New-Item -ItemType Directory -Path $previewTargetRoot -Force | Out-Null
    Copy-Item -LiteralPath $chatPathResolverSource -Destination $chatPathResolverTarget -Force
    Write-Host "Updated chat path resolver: $chatPathResolverTarget"
}

$githubRegistration = Join-Path $RepositoryRoot "packages\Codex_Github\register-global-skill.ps1"
if (Test-Path -LiteralPath $githubRegistration -PathType Leaf) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $githubRegistration -CodexHome $CodexHome
    if ($LASTEXITCODE -ne 0) {
        throw "Codex_Github global skill registration failed with exit code ${LASTEXITCODE}."
    }
}

$gifRegistration = Join-Path $RepositoryRoot "packages\Codex_Gif\register-global-skill.ps1"
if (Test-Path -LiteralPath $gifRegistration -PathType Leaf) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $gifRegistration -CodexHome $CodexHome
    if ($LASTEXITCODE -ne 0) {
        throw "Codex_Gif global skill registration failed with exit code ${LASTEXITCODE}."
    }
}

$dtRegistration = Join-Path $RepositoryRoot "packages\Codex_DT\register-global-skill.ps1"
if (Test-Path -LiteralPath $dtRegistration -PathType Leaf) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $dtRegistration -CodexHome $CodexHome
    if ($LASTEXITCODE -ne 0) {
        throw "Codex_DT global skill registration failed with exit code ${LASTEXITCODE}."
    }
}

$batchImageRegistration = Join-Path $RepositoryRoot "packages\Codex_Batch_Image\register-global-skill.ps1"
if (Test-Path -LiteralPath $batchImageRegistration -PathType Leaf) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $batchImageRegistration -CodexHome $CodexHome
    if ($LASTEXITCODE -ne 0) { throw "Codex_Batch_Image global skill registration failed with exit code ${LASTEXITCODE}." }
}

$flowRegistration = Join-Path $RepositoryRoot "packages\Codex_Flow\register-global-skills.ps1"
if (Test-Path -LiteralPath $flowRegistration -PathType Leaf) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $flowRegistration -CodexHome $CodexHome
    if ($LASTEXITCODE -ne 0) { throw "Codex_Flow global Skill registration failed with exit code ${LASTEXITCODE}." }
}

Write-Host ""
Write-Host "Global Codex synchronization complete. Restart Codex or start a new task to reload changes." -ForegroundColor Green
