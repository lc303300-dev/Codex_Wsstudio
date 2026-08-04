[CmdletBinding()]
param(
    [string]$CodexHome,
    [switch]$ProviderSkills,
    [switch]$KeepLegacyProviderSkills
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
if (-not $CodexHome) {
    $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
}
$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$SkillsRoot = Join-Path $CodexHome "skills"
$PluginsRoot = Join-Path $CodexHome "plugins"
$MarkerName = ".codex-image-registration.json"
$ToolNames = @("default-image-generation", "default-video-generation")
$ProviderNames = @("gemini-api", "gemini-cli", "seedance-cli", "gpt-api", "comfly-api")

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
        if ($record.source_root -ne $ProjectRoot) { throw "Refusing to replace $Kind '$Name' from another source root." }
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

$PersonalPlugin = Join-Path $HOME "plugins\codex-media-plugin"
if (Test-Path -LiteralPath (Join-Path $PersonalPlugin ".codex-plugin\plugin.json")) {
    $personalMarker = Join-Path $PersonalPlugin $MarkerName
    if (Test-Path -LiteralPath $personalMarker) {
        $personalRecord = Get-Content -LiteralPath $personalMarker -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($personalRecord.source_root -ne $ProjectRoot) {
            Write-Warning "Skipping personal codex-media-plugin update because it is managed by another source root."
            $PersonalPlugin = $null
        }
    }
    if ($PersonalPlugin) {
        Copy-Item -LiteralPath (Join-Path $ProjectRoot "codex-media-plugin\mcp\server.py") -Destination (Join-Path $PersonalPlugin "mcp\server.py") -Force
        [ordered]@{ name="codex-media-plugin"; kind="plugin"; source_root=$ProjectRoot; registered_at=(Get-Date).ToString("o") } |
            ConvertTo-Json | Set-Content -LiteralPath $personalMarker -Encoding UTF8
    }
}

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
