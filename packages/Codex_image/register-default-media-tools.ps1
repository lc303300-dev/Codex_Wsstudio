[CmdletBinding()]
param(
    [string]$CodexHome,
    [string]$PersonalPluginsRoot,
    [switch]$ProviderSkills,
    [switch]$KeepLegacyProviderSkills
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
if (-not $CodexHome) {
    $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
}
if (-not $PersonalPluginsRoot) {
    $PersonalPluginsRoot = Join-Path $HOME "plugins"
}
$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$PersonalPluginsRoot = [System.IO.Path]::GetFullPath($PersonalPluginsRoot)
$SkillsRoot = Join-Path $CodexHome "skills"
$PluginsRoot = Join-Path $CodexHome "plugins"
$MarkerName = ".codex-image-registration.json"
$ToolNames = @("default-image-generation", "default-video-generation")
$ProviderNames = @("gemini-api", "gemini-cli", "seedance-cli", "gpt-api", "comfly-api")

function Test-CodexImageSourceRoot {
    param([string]$SourceRoot)

    if ([string]::IsNullOrWhiteSpace($SourceRoot)) { return $false }
    try {
        $candidate = [System.IO.Path]::GetFullPath($SourceRoot)
    } catch {
        return $false
    }
    return (Test-Path -LiteralPath (Join-Path $candidate "CLI\Media-Router") -PathType Container)
}

function Install-ManagedDirectory {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Kind,
        [string]$Name,
        [string[]]$ExcludeNames = @()
    )
    $parent = Split-Path $Destination -Parent
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    if (Test-Path -LiteralPath $Destination) {
        $marker = Join-Path $Destination $MarkerName
        if (-not (Test-Path -LiteralPath $marker)) { throw "Refusing to replace unmanaged $Kind '$Name': $Destination" }
        $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($record.source_root -ne $ProjectRoot) {
            if (Test-CodexImageSourceRoot -SourceRoot ([string]$record.source_root)) {
                throw "Refusing to replace $Kind '$Name' from another source root."
            }
            Write-Warning "Replacing stale managed $Kind '$Name' from unavailable source root: $($record.source_root)"
        }
    }
    $temporary = Join-Path $parent (".codex-media-install-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $temporary | Out-Null
    try {
        Get-ChildItem -LiteralPath $Source -Force |
            Where-Object { $_.Name -notin $ExcludeNames } |
            Copy-Item -Destination $temporary -Recurse -Force
        [ordered]@{ name=$Name; kind=$Kind; source_root=$ProjectRoot; registered_at=(Get-Date).ToString("o") } |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary $MarkerName) -Encoding UTF8
        if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Recurse -Force }
        Move-Item -LiteralPath $temporary -Destination $Destination
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
    }
}

function Refresh-ManagedPluginCaches {
    $cacheRoot = Join-Path $CodexHome "plugins\cache\personal\codex-media-plugin"
    if (-not (Test-Path -LiteralPath $cacheRoot -PathType Container)) { return }

    Get-ChildItem -LiteralPath $cacheRoot -Directory | ForEach-Object {
        $cachePlugin = $_.FullName
        if (-not (Test-Path -LiteralPath (Join-Path $cachePlugin ".codex-plugin\plugin.json") -PathType Leaf)) { return }
        $marker = Join-Path $cachePlugin $MarkerName
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            Write-Warning "Skipping unmanaged cached codex-media-plugin: $cachePlugin"
            return
        }

        $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($record.source_root -ne $ProjectRoot) {
            if (Test-CodexImageSourceRoot -SourceRoot ([string]$record.source_root)) {
                Write-Host "Refreshing cached codex-media-plugin from stale source root: $($record.source_root)"
            } else {
                Write-Host "Refreshing cached codex-media-plugin from unavailable source root: $($record.source_root)"
            }
        }
        try {
            Install-ManagedDirectory `
                -Source (Join-Path $ProjectRoot "codex-media-plugin") `
                -Destination $cachePlugin `
                -Kind "cached plugin" `
                -Name "codex-media-plugin"
        } catch {
            Write-Warning "Skipping locked cached codex-media-plugin refresh: $cachePlugin"
        }
    }
}

Install-ManagedDirectory `
    -Source (Join-Path $ProjectRoot "codex-media-plugin") `
    -Destination (Join-Path $PluginsRoot "codex-media-plugin") `
    -Kind "plugin" `
    -Name "codex-media-plugin" `
    -ExcludeNames @("skills")

foreach ($name in $ToolNames) {
    Install-ManagedDirectory `
        -Source (Join-Path $ProjectRoot "codex-media-plugin\skills\$name") `
        -Destination (Join-Path $SkillsRoot $name) `
        -Kind "tool-skill" `
        -Name $name
}

$PersonalPlugin = Join-Path $PersonalPluginsRoot "codex-media-plugin"
Install-ManagedDirectory `
    -Source (Join-Path $ProjectRoot "codex-media-plugin") `
    -Destination $PersonalPlugin `
    -Kind "personal plugin" `
    -Name "codex-media-plugin"
Refresh-ManagedPluginCaches

if ($ProviderSkills) {
    foreach ($name in $ProviderNames) {
        Install-ManagedDirectory -Source (Join-Path $ProjectRoot $name) -Destination (Join-Path $SkillsRoot $name) -Kind "provider-skill" -Name $name
    }
} elseif (-not $KeepLegacyProviderSkills) {
    foreach ($name in $ProviderNames) {
        $destination = Join-Path $SkillsRoot $name
        $marker = Join-Path $destination $MarkerName
        if ((Test-Path -LiteralPath $marker) -and (Test-Path -LiteralPath $destination)) {
            $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($record.source_root -eq $ProjectRoot) { Remove-Item -LiteralPath $destination -Recurse -Force }
        }
    }
    Get-ChildItem -LiteralPath $SkillsRoot -Directory -Filter "*.disabled-*" -ErrorAction SilentlyContinue | ForEach-Object {
        $marker = Join-Path $_.FullName $MarkerName
        if (Test-Path -LiteralPath $marker) {
            $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($record.source_root -eq $ProjectRoot -and $record.pipeline -in $ProviderNames) {
                Remove-Item -LiteralPath $_.FullName -Recurse -Force
            }
        }
    }
}

$statePath = Join-Path $CodexHome "codex-image-registration-state.json"
$previous = $null
$state = [ordered]@{
    schema_version = 2
    source_root = $ProjectRoot
    registered_tools = $ToolNames
    setup_completed_tools = @()
    provider_readiness = @{}
    updated_at = (Get-Date).ToString("o")
}
if (Test-Path -LiteralPath $statePath) {
    $previous = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($previous.source_root -eq $ProjectRoot -and ([int]$previous.schema_version -lt 2)) {
        $backupRoot = Join-Path $ProjectRoot ".codex-image-private\validation\state-migration"
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        $backup = [ordered]@{
            source_root = [string]$previous.source_root
            schema_version = if ($previous.schema_version) { [int]$previous.schema_version } else { 1 }
            registered_pipelines = @($previous.registered_pipelines)
            selected_pipelines = @($previous.selected_pipelines)
            setup_completed_pipelines = @($previous.setup_completed_pipelines)
            first_run_choice_completed = [bool]$previous.first_run_choice_completed
            backed_up_at = (Get-Date).ToString("o")
        }
        $backupName = "state-v1-" + (Get-Date -Format "yyyyMMdd-HHmmss-fff") + ".json"
        $backup | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $backupRoot $backupName) -Encoding UTF8
    }
    if ($previous.source_root -eq $ProjectRoot -and $previous.setup_completed_tools) {
        $state.setup_completed_tools = @($previous.setup_completed_tools | Where-Object { $_ -in $ToolNames })
    }
}
$temporaryState = "$statePath.tmp"
$state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporaryState -Encoding UTF8
Move-Item -LiteralPath $temporaryState -Destination $statePath -Force
Write-Host "Registered unified skills and plugin under: $CodexHome"
Write-Host "Restart Codex or start a new task after application-level plugin installation."
