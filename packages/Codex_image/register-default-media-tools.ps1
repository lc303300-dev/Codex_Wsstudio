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
$ProviderNames = @("gemini-api", "seedance-cli", "gpt-api", "comfly-api")
$RemovedProviderNames = @("gemini-cli")

function Test-CodexImageSourceRoot {
    param([string]$SourceRoot)

    if ([string]::IsNullOrWhiteSpace($SourceRoot)) { return $false }
    try {
        $candidate = [System.IO.Path]::GetFullPath($SourceRoot)
    } catch {
        return $false
    }
    try {
        return (Test-Path -LiteralPath (Join-Path $candidate "CLI\Media-Router") -PathType Container)
    } catch {
        return $false
    }
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
        $marker = Join-Path $cachePlugin $MarkerName
        $manifest = Join-Path $cachePlugin ".codex-plugin\plugin.json"
        if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
            $entries = @(Get-ChildItem -LiteralPath $cachePlugin -Force -ErrorAction SilentlyContinue)
            if ($entries.Count -eq 0) {
                Write-Warning "Repairing empty cached codex-media-plugin: $cachePlugin"
                Remove-Item -LiteralPath $cachePlugin -Recurse -Force
            } elseif (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
                Write-Warning "Skipping unmanaged incomplete cached codex-media-plugin: $cachePlugin"
                return
            }
        }
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            if (Test-Path -LiteralPath $cachePlugin -PathType Container) {
                Write-Warning "Skipping unmanaged cached codex-media-plugin: $cachePlugin"
                return
            }
        } else {
            $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($record.source_root -ne $ProjectRoot) {
                if (Test-CodexImageSourceRoot -SourceRoot ([string]$record.source_root)) {
                    Write-Host "Refreshing cached codex-media-plugin from stale source root: $($record.source_root)"
                } else {
                    Write-Host "Refreshing cached codex-media-plugin from unavailable source root: $($record.source_root)"
                }
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

function Remove-StaleManagedMediaCaches {
    param([string]$CurrentVersion)

    # Clean only Wsstudio-managed legacy media registrations. Unmarked
    # directories are treated as user-owned and are deliberately preserved.
    $cacheRoot = Join-Path $CodexHome "plugins\cache\personal\codex-media-plugin"
    if (Test-Path -LiteralPath $cacheRoot -PathType Container) {
        foreach ($candidate in @(Get-ChildItem -LiteralPath $cacheRoot -Directory -Force -ErrorAction SilentlyContinue)) {
            if ($candidate.Name -eq $CurrentVersion) { continue }
            $marker = Join-Path $candidate.FullName $MarkerName
            $manifest = Join-Path $candidate.FullName ".codex-plugin\plugin.json"
            $managed = $false
            if (Test-Path -LiteralPath $marker -PathType Leaf) {
                try {
                    $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
                    $managed = ([string]$record.name -eq "codex-media-plugin")
                } catch {
                    $managed = $false
                }
            } elseif (Test-Path -LiteralPath $manifest -PathType Leaf) {
                try {
                    $record = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
                    $managed = ([string]$record.name -eq "codex-media-plugin")
                } catch {
                    $managed = $false
                }
            } elseif (@(Get-ChildItem -LiteralPath $candidate.FullName -Force -ErrorAction SilentlyContinue).Count -eq 0) {
                # Empty version directories are generated cache debris.
                $managed = $true
            }
            if ($managed) {
                try {
                    [System.IO.Directory]::Delete($candidate.FullName, $true)
                    Write-Host "Removed stale media plugin cache: $($candidate.FullName)"
                } catch {
                    Write-Warning "Could not remove stale media plugin cache (it may be locked): $($candidate.FullName)"
                }
            }
        }
    }

    $legacyRoots = @(
        (Join-Path $CodexHome "plugins"),
        (Join-Path $CodexHome "skill-backups"),
        (Join-Path $CodexHome "skills")
    )
    foreach ($root in $legacyRoots) {
        if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
        foreach ($candidate in @(Get-ChildItem -LiteralPath $root -Directory -Force -ErrorAction SilentlyContinue)) {
            $isLegacyName = $candidate.Name -match '^(?:codex-media-plugin|default-(?:image|video)-generation)(?:\.backup-|\.disabled-)'
            if (-not $isLegacyName) { continue }
            $marker = Join-Path $candidate.FullName $MarkerName
            if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { continue }
            try {
                $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
                if ([string]$record.name -in @("codex-media-plugin", "default-image-generation", "default-video-generation")) {
                    [System.IO.Directory]::Delete($candidate.FullName, $true)
                    Write-Host "Removed stale global media registration: $($candidate.FullName)"
                }
            } catch {
                Write-Warning "Could not remove stale global media registration: $($candidate.FullName)"
            }
        }
    }
}

function Update-PersonalMarketplaceManifest {
    param([string]$PluginPath)

    # Codex discovers personal plugins from the marketplace manifest, not from
    # the loose %USERPROFILE%\plugins directory alone. Keep this manifest in
    # sync whenever the managed media plugin is registered.
    $marketplaceRoot = Split-Path -Parent $PersonalPluginsRoot
    $marketplaceDir = Join-Path $marketplaceRoot ".agents\plugins"
    $marketplacePath = Join-Path $marketplaceDir "marketplace.json"
    New-Item -ItemType Directory -Path $marketplaceDir -Force | Out-Null

    $manifest = [ordered]@{
        name = "personal"
        interface = [ordered]@{ displayName = "Personal" }
        plugins = @()
    }
    if (Test-Path -LiteralPath $marketplacePath -PathType Leaf) {
        try {
            $existing = Get-Content -LiteralPath $marketplacePath -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            throw "Personal marketplace manifest is invalid and was not overwritten: $marketplacePath"
        }
        if ($existing.name) { $manifest.name = [string]$existing.name }
        if ($existing.interface) { $manifest.interface = $existing.interface }
        if ($null -ne $existing.plugins) { $manifest.plugins = @($existing.plugins) }
    }

    $baseUri = [Uri]((([System.IO.Path]::GetFullPath($marketplaceRoot)).TrimEnd("\") + "\"))
    $pluginUri = [Uri]([System.IO.Path]::GetFullPath($PluginPath))
    $relative = [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pluginUri).ToString()).Replace("\", "/")
    if (-not $relative.StartsWith("./")) { $relative = "./" + $relative }
    $entry = @($manifest.plugins | Where-Object { $_.name -eq "codex-media-plugin" } | Select-Object -First 1)
    if ($entry.Count -eq 0) {
        $manifest.plugins += [ordered]@{
            name = "codex-media-plugin"
            source = [ordered]@{ source = "local"; path = $relative }
            policy = [ordered]@{ installation = "AVAILABLE"; authentication = "ON_INSTALL" }
            category = "Creative"
        }
    } else {
        $entry[0].source = [ordered]@{ source = "local"; path = $relative }
        if (-not $entry[0].policy) {
            $entry[0].policy = [ordered]@{ installation = "AVAILABLE"; authentication = "ON_INSTALL" }
        }
        if (-not $entry[0].category) { $entry[0].category = "Creative" }
    }

    $temporary = "$marketplacePath.tmp-$PID"
    $json = $manifest | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($temporary, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $marketplacePath -Force
    Write-Host "Registered codex-media-plugin in personal marketplace: $marketplacePath"
}

function Install-VersionedPluginCache {
    $manifestPath = Join-Path $ProjectRoot "codex-media-plugin\.codex-plugin\plugin.json"
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $version = [string]$manifest.version
    if ([string]::IsNullOrWhiteSpace($version) -or $version -notmatch '^[A-Za-z0-9.+_-]+$') {
        throw "codex-media-plugin has an invalid version: $version"
    }
    Remove-StaleManagedMediaCaches -CurrentVersion $version
    $cachePlugin = Join-Path $CodexHome "plugins\cache\personal\codex-media-plugin\$version"
    Install-ManagedDirectory `
        -Source (Join-Path $ProjectRoot "codex-media-plugin") `
        -Destination $cachePlugin `
        -Kind "versioned plugin cache" `
        -Name "codex-media-plugin"
    Write-Host "Prepared versioned Codex plugin cache: $cachePlugin"
}

function Install-CodexMediaPlugin {
    $defaultHome = if ($env:CODEX_HOME) { [System.IO.Path]::GetFullPath($env:CODEX_HOME) } else { [System.IO.Path]::GetFullPath((Join-Path $HOME ".codex")) }
    $defaultPersonalRoot = [System.IO.Path]::GetFullPath((Join-Path $HOME "plugins"))
    if ($CodexHome -ne $defaultHome -or $PersonalPluginsRoot -ne $defaultPersonalRoot) {
        return
    }
    $codex = $null
    if ($env:CODEX_CLI_PATH -and (Test-Path -LiteralPath $env:CODEX_CLI_PATH -PathType Leaf)) {
        $codex = $env:CODEX_CLI_PATH
    } else {
        $command = Get-Command codex.exe -ErrorAction SilentlyContinue
        if ($command) { $codex = $command.Source }
    }
    if (-not $codex) {
        Write-Warning "Codex CLI was not found; marketplace entry is ready, but plugin installation will occur when Codex refreshes or codex plugin add is run."
        return
    }
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $result = & $codex plugin add "codex-media-plugin@personal" --json 2>&1
    $pluginExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction
    if ($pluginExitCode -ne 0) {
        $message = ($result -join " ")
        if ($message -match "(?i)access denied|os error 5|being used|locked") {
            Write-Warning "Codex plugin cache is locked by a running Codex process. The marketplace entry and source plugin are current. Restart Codex, then rerun the Wsstudio registration command to refresh the cache."
            return
        }
        throw "Codex could not install codex-media-plugin from the personal marketplace: $message"
    }
    Write-Host "Codex installed codex-media-plugin into its managed plugin cache."
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
Update-PersonalMarketplaceManifest -PluginPath $PersonalPlugin
Install-VersionedPluginCache
Install-CodexMediaPlugin

if ($ProviderSkills) {
    foreach ($name in $ProviderNames) {
        Install-ManagedDirectory -Source (Join-Path $ProjectRoot $name) -Destination (Join-Path $SkillsRoot $name) -Kind "provider-skill" -Name $name
    }
} elseif (-not $KeepLegacyProviderSkills) {
    foreach ($name in @($ProviderNames + $RemovedProviderNames)) {
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
            if ($record.source_root -eq $ProjectRoot -and $record.pipeline -in @($ProviderNames + $RemovedProviderNames)) {
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
