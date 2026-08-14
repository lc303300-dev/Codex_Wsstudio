param(
    [string]$PreviewTool,
    [string]$SeedanceCli,
    [switch]$SkipCreditCheck,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$configPath = Join-Path $root "config/pipeline.json"
$localConfigPath = Join-Path $root "config/pipeline.local.json"

function Resolve-ConfiguredPath {
    param(
        [string]$Explicit,
        [string[]]$EnvironmentNames,
        [string]$LocalValue,
        [string]$BaseValue,
        [string]$Fallback
    )

    foreach ($candidate in @($Explicit)) {
        if (-not [string]::IsNullOrWhiteSpace($candidate)) { return $candidate }
    }
    foreach ($name in $EnvironmentNames) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
    }
    foreach ($candidate in @($LocalValue, $BaseValue, $Fallback)) {
        if (-not [string]::IsNullOrWhiteSpace($candidate)) { return $candidate }
    }
    return $null
}

function Test-CommandAvailable {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Resolve-FirstExistingPath {
    param([string[]]$Candidates)

    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $resolved = $candidate
        try {
            $resolved = (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
        } catch {
        }
        if (Test-Path -LiteralPath $resolved) {
            return $resolved
        }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Missing pipeline config: $configPath"
}

$baseConfig = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw | ConvertFrom-Json
$localConfig = $null
if (Test-Path -LiteralPath $localConfigPath) {
    $localConfig = Get-Content -LiteralPath $localConfigPath -Encoding UTF8 -Raw | ConvertFrom-Json
}

$codexHome = [Environment]::GetEnvironmentVariable("CODEX_HOME")
if ([string]::IsNullOrWhiteSpace($codexHome)) {
    $codexHome = Join-Path $env:USERPROFILE ".codex"
}
$previewFallback = Join-Path $codexHome "tools/Convert-CodexImagePreview.ps1"
$codexImageRoot = Resolve-Path -LiteralPath (Join-Path $root "..\Codex_image")

$localPreview = if ($null -ne $localConfig -and $null -ne $localConfig.paths) { [string]$localConfig.paths.preview_tool } else { $null }
$localSeedance = if ($null -ne $localConfig -and $null -ne $localConfig.paths) { [string]$localConfig.paths.seedance_cli } else { $null }

$resolvedPreviewTool = Resolve-ConfiguredPath `
    -Explicit $PreviewTool `
    -EnvironmentNames @("CODEX_PREVIEW_TOOL") `
    -LocalValue $localPreview `
    -BaseValue ([string]$baseConfig.paths.preview_tool) `
    -Fallback $previewFallback

if (-not (Test-Path -LiteralPath $resolvedPreviewTool)) {
    $resolvedPreviewTool = Resolve-FirstExistingPath -Candidates @(
        $PreviewTool,
        $localPreview,
        ([string]$baseConfig.paths.preview_tool),
        $previewFallback,
        (Join-Path $codexImageRoot "tools\Convert-CodexImagePreview.ps1")
    )
}

$resolvedSeedanceCli = Resolve-ConfiguredPath `
    -Explicit $SeedanceCli `
    -EnvironmentNames @("SEEDANCE_CLI", "SEEDANCE_CLI_PATH", "DREAMINA_CLI") `
    -LocalValue $localSeedance `
    -BaseValue ([string]$baseConfig.paths.seedance_cli) `
    -Fallback $null

if (-not (Test-Path -LiteralPath $resolvedSeedanceCli)) {
    $resolvedSeedanceCli = Resolve-FirstExistingPath -Candidates @(
        $SeedanceCli,
        $localSeedance,
        ([string]$baseConfig.paths.seedance_cli),
        (Join-Path $codexImageRoot "CLI\Seedance-CLI\run.ps1"),
        (Join-Path $codexImageRoot ".codex-image-private\bin\seedance-cli\run.ps1")
    )
}

$requiredDirectories = @(
    "inputs",
    "previews",
    "prompts",
    "review",
    "manifests",
    "outputs",
    "outputs/logs",
    "outputs/videos",
    ".codex-image-private",
    ".codex-image-private/batches"
)
foreach ($dir in $requiredDirectories) {
    New-Item -ItemType Directory -Force -Path (Join-Path $root $dir) | Out-Null
}

foreach ($file in @("inputs/.gitkeep", "previews/.gitkeep", "prompts/.gitkeep", "review/.gitkeep", "outputs/logs/.gitkeep", "outputs/videos/.gitkeep")) {
    $path = Join-Path $root $file
    if (-not (Test-Path -LiteralPath $path)) {
        Set-Content -LiteralPath $path -Value "" -Encoding UTF8
    }
}

$checks = New-Object System.Collections.Generic.List[object]
function Add-Check {
    param([string]$Name, [bool]$Ok, [string]$Detail)
    $script:checks.Add([pscustomobject]@{ Name = $Name; Ok = $Ok; Detail = $Detail }) | Out-Null
}

Add-Check "PowerShell" $true $PSVersionTable.PSVersion.ToString()
Add-Check "Python" (Test-CommandAvailable "python") ($(if (Test-CommandAvailable "python") { (& python --version 2>&1) -join " " } else { "python not found in PATH" }))
Add-Check "Preview tool" (Test-Path -LiteralPath $resolvedPreviewTool) $resolvedPreviewTool
Add-Check "Seedance CLI" (-not [string]::IsNullOrWhiteSpace($resolvedSeedanceCli) -and (Test-Path -LiteralPath $resolvedSeedanceCli)) $resolvedSeedanceCli
Add-Check "seedance-forge corpus" (Test-Path -LiteralPath (Join-Path $root "third_party/seedance-forge/references/indexes/combined.index.jsonl")) "third_party/seedance-forge/references/indexes/combined.index.jsonl"
Add-Check "Video director skill" (Test-Path -LiteralPath (Join-Path $root ".claude/skills/video-director-prompt/SKILL.md")) ".claude/skills/video-director-prompt/SKILL.md"
Add-Check "Seedance validator" (Test-Path -LiteralPath (Join-Path $root "third_party/seedance-2.0-prompt-skill/build-seedance2-prompts/scripts/validate_prompt.py")) "third_party/seedance-2.0-prompt-skill/build-seedance2-prompts/scripts/validate_prompt.py"

if ((Test-CommandAvailable "python") -and -not $Force) {
    $statusOutput = & python (Join-Path $root "scripts/pipeline_status.py") 2>&1
    Add-Check "Pipeline status" ($LASTEXITCODE -eq 0) (($statusOutput -join "`n").Trim())
}

$local = [ordered]@{
    language = $baseConfig.language
    surface = $baseConfig.surface
    mode = $baseConfig.mode
    duration = $baseConfig.duration
    model_version = $baseConfig.model_version
    video_resolution = $baseConfig.video_resolution
    poll_seconds = $baseConfig.poll_seconds
    preview_max_long_edge = $baseConfig.preview_max_long_edge
    private_runtime = $baseConfig.private_runtime
    paths = [ordered]@{
        preview_tool = $resolvedPreviewTool
        seedance_cli = $resolvedSeedanceCli
        forge_search = [string]$baseConfig.paths.forge_search
        forge_index = [string]$baseConfig.paths.forge_index
        mqrox_validator = [string]$baseConfig.paths.mqrox_validator
    }
}
($local | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $localConfigPath -Encoding UTF8
Add-Check "Local config" (Test-Path -LiteralPath $localConfigPath) $localConfigPath

if (-not $SkipCreditCheck -and -not [string]::IsNullOrWhiteSpace($resolvedSeedanceCli) -and (Test-Path -LiteralPath $resolvedSeedanceCli)) {
    Write-Host "Checking Dreamina user credit..."
    $creditOutput = powershell -NoProfile -ExecutionPolicy Bypass -File $resolvedSeedanceCli user_credit 2>&1
    Add-Check "Dreamina user_credit" ($LASTEXITCODE -eq 0) (($creditOutput -join "`n").Trim())
}
elseif ($SkipCreditCheck) {
    Add-Check "Dreamina user_credit" $true "Skipped by -SkipCreditCheck."
}

Write-Host ""
Write-Host "Codex_DT deployment checks"
$failed = @()
foreach ($check in $checks) {
    $mark = if ($check.Ok) { "OK" } else { "FAIL" }
    Write-Host ("[{0}] {1}: {2}" -f $mark, $check.Name, $check.Detail)
    if (-not $check.Ok) { $failed += $check }
}

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "Deployment is incomplete. Fix the FAIL item(s), then rerun:"
    Write-Host "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy_project.ps1"
    exit 1
}

Write-Host ""
Write-Host "Deployment complete. This workspace is ready for Codex_DT image-to-video pipeline work."
Write-Host "Local config: $localConfigPath"
