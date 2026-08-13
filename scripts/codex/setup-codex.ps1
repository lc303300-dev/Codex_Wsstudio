[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }),
    [string]$ConfigPath,
    [string]$CnHousingRoot,
    [switch]$SkipProjectTrust,
    [switch]$SkipBackup
)

$ErrorActionPreference = "Stop"

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $CodexHome "config.toml"
}

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$templatePath = Join-Path $repositoryRoot "config\codex\config.portable.toml"
if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
    throw "Portable template not found: $templatePath"
}

function Get-HeaderName {
    param([string]$Line)

    if ($Line -match '^\s*\[([^\]]+)\]\s*(?:#.*)?$') {
        return $matches[1]
    }
    return $null
}

function Get-TemplateAssignment {
    param(
        [string[]]$Lines,
        [AllowEmptyString()][string]$Table,
        [string]$Key
    )

    $currentTable = ""
    foreach ($line in $Lines) {
        $header = Get-HeaderName $line
        if ($null -ne $header) {
            $currentTable = $header
            continue
        }
        if ($currentTable -eq $Table -and $line -match ('^\s*' + [regex]::Escape($Key) + '\s*=\s*(.+?)\s*$')) {
            return $matches[1]
        }
    }
    throw "Missing [$Table] $Key in portable template."
}

function Set-TomlAssignment {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [AllowEmptyString()][string]$Table,
        [string]$Key,
        [string]$Value
    )

    $tableStart = 0
    $tableEnd = $Lines.Count

    if ($Table) {
        $tableStart = -1
        for ($i = 0; $i -lt $Lines.Count; $i++) {
            if ((Get-HeaderName $Lines[$i]) -eq $Table) {
                $tableStart = $i
                break
            }
        }

        if ($tableStart -lt 0) {
            if ($Lines.Count -gt 0 -and $Lines[$Lines.Count - 1] -ne "") {
                $Lines.Add("")
            }
            $Lines.Add("[$Table]")
            $Lines.Add("$Key = $Value")
            return
        }

        $tableEnd = $Lines.Count
        for ($i = $tableStart + 1; $i -lt $Lines.Count; $i++) {
            if ($null -ne (Get-HeaderName $Lines[$i])) {
                $tableEnd = $i
                break
            }
        }
        $searchStart = $tableStart + 1
    }
    else {
        $searchStart = 0
        for ($i = 0; $i -lt $Lines.Count; $i++) {
            if ($null -ne (Get-HeaderName $Lines[$i])) {
                $tableEnd = $i
                break
            }
        }
    }

    for ($i = $searchStart; $i -lt $tableEnd; $i++) {
        if ($Lines[$i] -match ('^\s*' + [regex]::Escape($Key) + '\s*=')) {
            $Lines[$i] = "$Key = $Value"
            return
        }
    }

    $Lines.Insert($tableEnd, "$Key = $Value")
}

function ConvertTo-TomlLiteralString {
    param([string]$Value)

    return "'" + ($Value -replace "'", "''") + "'"
}

function Find-CnHousingRoot {
    param([string]$ExplicitRoot)

    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($ExplicitRoot) { $candidates.Add($ExplicitRoot) }
    if ($env:CODEX_HOUSING_ROOT) { $candidates.Add($env:CODEX_HOUSING_ROOT) }

    $candidates.Add((Join-Path $PSScriptRoot "cn-housing-mcp"))
    $candidates.Add((Join-Path $env:USERPROFILE "Documents\Codex\cn-housing-mcp"))

    foreach ($drive in Get-PSDrive -PSProvider FileSystem) {
        $candidates.Add((Join-Path $drive.Root "Codex\Codex_ZF\cn-housing-mcp"))
        $candidates.Add((Join-Path $drive.Root "Codex\cn-housing-mcp"))
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        $server = Join-Path $candidate "server.py"
        if (Test-Path -LiteralPath $server -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

$templateLines = @(Get-Content -LiteralPath $templatePath -Encoding UTF8)
$targetLines = [System.Collections.Generic.List[string]]::new()
if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
    foreach ($line in Get-Content -LiteralPath $ConfigPath -Encoding UTF8) {
        $targetLines.Add($line)
    }
}

$managedSettings = @(
    @{ Table = ""; Key = "model_provider" },
    @{ Table = ""; Key = "model" },
    @{ Table = ""; Key = "model_reasoning_effort" },
    @{ Table = ""; Key = "disable_response_storage" },
    @{ Table = ""; Key = "personality" },
    @{ Table = "model_providers.codex"; Key = "name" },
    @{ Table = "model_providers.codex"; Key = "base_url" },
    @{ Table = "model_providers.codex"; Key = "wire_api" },
    @{ Table = "desktop"; Key = "followUpQueueMode" },
    @{ Table = "desktop"; Key = "conversationDetailMode" },
    @{ Table = 'plugins."computer-use@openai-bundled"'; Key = "enabled" },
    @{ Table = 'plugins."documents@openai-primary-runtime"'; Key = "enabled" },
    @{ Table = 'plugins."pdf@openai-primary-runtime"'; Key = "enabled" },
    @{ Table = 'plugins."spreadsheets@openai-primary-runtime"'; Key = "enabled" },
    @{ Table = 'plugins."presentations@openai-primary-runtime"'; Key = "enabled" },
    @{ Table = 'plugins."template-creator@openai-primary-runtime"'; Key = "enabled" },
    @{ Table = 'plugins."cowart@personal"'; Key = "enabled" },
    @{ Table = 'plugins."visualize@openai-bundled"'; Key = "enabled" },
    @{ Table = 'plugins."browser@openai-bundled"'; Key = "enabled" },
    @{ Table = 'plugins."codex-media-plugin@personal"'; Key = "enabled" },
    @{ Table = "features"; Key = "js_repl" },
    @{ Table = "windows"; Key = "sandbox" }
)

foreach ($setting in $managedSettings) {
    $value = Get-TemplateAssignment -Lines $templateLines -Table $setting.Table -Key $setting.Key
    Set-TomlAssignment -Lines $targetLines -Table $setting.Table -Key $setting.Key -Value $value
}

if (-not $SkipProjectTrust) {
    foreach ($projectPath in @($repositoryRoot, (Join-Path $repositoryRoot "packages\Codex_DT"), (Join-Path $repositoryRoot "packages\Codex_image"), (Join-Path $repositoryRoot "packages\Codex_Github"))) {
        if (Test-Path -LiteralPath $projectPath -PathType Container) {
            $resolvedProject = (Resolve-Path -LiteralPath $projectPath).Path.ToLowerInvariant()
            Set-TomlAssignment -Lines $targetLines -Table ("projects." + (ConvertTo-TomlLiteralString $resolvedProject)) -Key "trust_level" -Value '"trusted"'
        }
    }
}

$codexImageRoot = Join-Path $repositoryRoot "packages\Codex_image"
if (Test-Path -LiteralPath (Join-Path $codexImageRoot "CLI\Media-Router") -PathType Container) {
    Set-TomlAssignment -Lines $targetLines -Table "shell_environment_policy.set" -Key "CODEX_IMAGE_ROOT" -Value (ConvertTo-TomlLiteralString $codexImageRoot)
}

$housingRoot = Find-CnHousingRoot -ExplicitRoot $CnHousingRoot
if ($housingRoot) {
    $housingPython = Join-Path $housingRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $housingPython -PathType Leaf)) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCommand) { $housingPython = $pythonCommand.Source }
    }
    if (Test-Path -LiteralPath $housingPython -PathType Leaf) {
        Set-TomlAssignment -Lines $targetLines -Table "mcp_servers.cn-housing" -Key "command" -Value (ConvertTo-TomlLiteralString $housingPython)
        Set-TomlAssignment -Lines $targetLines -Table "mcp_servers.cn-housing" -Key "args" -Value ("[" + (ConvertTo-TomlLiteralString (Join-Path $housingRoot "server.py")) + "]")
    }
}

$parent = Split-Path -Parent $ConfigPath
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}

$newText = (($targetLines -join "`r`n").TrimEnd() + "`r`n")
$oldText = if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) { Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 } else { "" }

if ($newText -eq $oldText) {
    Write-Output "Codex config is already up to date: $ConfigPath"
    return
}

if ($PSCmdlet.ShouldProcess($ConfigPath, "merge portable Codex settings")) {
    if ((Test-Path -LiteralPath $ConfigPath -PathType Leaf) -and -not $SkipBackup) {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $backupPath = "$ConfigPath.backup-$stamp"
        Copy-Item -LiteralPath $ConfigPath -Destination $backupPath
        Write-Output "Backup: $backupPath"
    }

    $temporaryPath = "$ConfigPath.tmp-$PID"
    [System.IO.File]::WriteAllText($temporaryPath, $newText, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporaryPath -Destination $ConfigPath -Force
    Write-Output "Updated: $ConfigPath"
    Write-Output "Machine-generated runtime, marketplace, notification, MCP, and existing project sections were preserved."
}
