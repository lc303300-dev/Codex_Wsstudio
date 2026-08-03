[CmdletBinding()]
param(
    [string[]]$Pipeline,
    [switch]$All,
    [switch]$Force,
    [string]$CodexHome
)

Write-Warning "register-global-skills.ps1 is the legacy provider-skill installer. Unified media tools are now the default."
if (-not $Pipeline -and -not $All) {
    & (Join-Path $PSScriptRoot "register-default-media-tools.ps1") -CodexHome $CodexHome
    exit $LASTEXITCODE
}

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$KnownPipelines = [ordered]@{
    "gemini-api"   = "Official Google Gemini API image generation and editing"
    "gemini-cli"   = "Google Antigravity CLI image generation and editing"
    "seedance-cli" = "Dreamina image generation and Seedance video generation"
    "gpt-api"      = "APIMart GPT Image 2 image generation and editing"
    "comfly-api"    = "Comfly OpenAI-compatible image generation and editing"
}
$ProviderWebsites = [ordered]@{
    "gemini-api"   = "https://aistudio.google.com/"
    "gemini-cli"   = "https://aistudio.google.com/"
    "seedance-cli" = "https://jimeng.jianying.com/"
    "gpt-api"      = "https://apimart.ai/zh"
    "comfly-api"    = "https://ai.comfly.org/"
}

if (-not $CodexHome) {
    $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
}
$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$SkillsRoot = Join-Path $CodexHome "skills"
$MarkerName = ".codex-image-registration.json"

if ($All -and $Pipeline) {
    throw "Use either -All or -Pipeline, not both."
}

if ($All) {
    $Selected = @($KnownPipelines.Keys)
} elseif ($Pipeline) {
    $Selected = @($Pipeline | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Unique)
    foreach ($name in $Selected) {
        if (-not $KnownPipelines.Contains($name)) {
            throw "Unknown pipeline '$name'. Valid values: $($KnownPipelines.Keys -join ', ')."
        }
    }
} else {
    Write-Host "Select the Codex_image pipelines to register globally:"
    $index = 1
    foreach ($name in $KnownPipelines.Keys) {
        Write-Host "  $index. $name - $($KnownPipelines[$name])"
        Write-Host "     Service/payment website: $($ProviderWebsites[$name])"
        $index++
    }
    Write-Host "  A. All pipelines"
    $answer = (Read-Host "Enter numbers separated by commas, or A").Trim()
    if ($answer -match "^(?i:a|all)$") {
        $Selected = @($KnownPipelines.Keys)
    } else {
        $Selected = foreach ($item in ($answer -split ",")) {
            $number = 0
            if (-not [int]::TryParse($item.Trim(), [ref]$number) -or $number -lt 1 -or $number -gt $KnownPipelines.Count) {
                throw "Invalid selection: $item"
            }
            @($KnownPipelines.Keys)[$number - 1]
        }
        $Selected = @($Selected | Select-Object -Unique)
    }
}

if (-not $Selected.Count) {
    throw "No pipelines selected."
}

New-Item -ItemType Directory -Path $SkillsRoot -Force | Out-Null
$resolvedSkillsRoot = (Resolve-Path -LiteralPath $SkillsRoot).Path.TrimEnd("\")

foreach ($name in $Selected) {
    $source = Join-Path $ProjectRoot $name
    $destination = Join-Path $SkillsRoot $name
    $marker = Join-Path $destination $MarkerName

    if (-not (Test-Path -LiteralPath (Join-Path $source "SKILL.md"))) {
        throw "Skill source is missing: $source"
    }

    if (Test-Path -LiteralPath $destination) {
        $managed = Test-Path -LiteralPath $marker
        if (-not $managed -and -not $Force) {
            throw "Global skill '$name' already exists and is not managed by Codex_image. Use -Force to replace it."
        }
        $destinationParent = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($destination)).TrimEnd("\")
        if ($destinationParent -ne $resolvedSkillsRoot) {
            throw "Refusing to replace a skill outside the global skills directory: $destination"
        }
        Remove-Item -LiteralPath $destination -Recurse -Force
    }

    $temporary = Join-Path $SkillsRoot (".codex-image-install-" + [guid]::NewGuid().ToString("N"))
    try {
        New-Item -ItemType Directory -Path $temporary | Out-Null
        Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $temporary -Recurse -Force

        $skillFile = Join-Path $temporary "SKILL.md"
        $skillText = [System.IO.File]::ReadAllText($skillFile)
        $projectRootForMarkdown = $ProjectRoot.Replace("\", "/")
        $imageReadingGuardrail = @"

## Image Reading Guardrail

Before Codex visually reads, inspects, previews, or calls ``view_image`` on any local raster image, create a preview with ``C:/Users/A/.codex/tools/Convert-CodexImagePreview.ps1`` and inspect only that preview. The preview's longest edge must be at most 512 px. Keep original image paths only for filesystem operations and provider inputs.

"@
        $installationNote = @"

## Local Installation

This global skill is backed by the Codex_image checkout at ``$projectRootForMarkdown``.
Resolve ``../CLI/...`` as ``$projectRootForMarkdown/CLI/...`` and ``../.codex-image-private/...`` as ``$projectRootForMarkdown/.codex-image-private/...``. Use the resulting absolute path when invoking a command.

"@
        if ($skillText -notmatch "(?m)^## Image Reading Guardrail\s*$") {
            $installationNote += $imageReadingGuardrail
        }
        $skillText = [regex]::Replace(
            $skillText,
            "\A(---\r?\n.*?\r?\n---\r?\n)",
            { param($match) $match.Groups[1].Value + $installationNote },
            [System.Text.RegularExpressions.RegexOptions]::Singleline
        )
        [System.IO.File]::WriteAllText($skillFile, $skillText, [System.Text.UTF8Encoding]::new($false))

        $registration = [ordered]@{
            pipeline = $name
            source_root = $ProjectRoot
            registered_at = (Get-Date).ToString("o")
        }
        $registration | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary $MarkerName) -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $destination
        Write-Host "Registered: $name -> $destination"
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Recurse -Force
        }
    }
}

$Registered = foreach ($name in $KnownPipelines.Keys) {
    $destination = Join-Path $SkillsRoot $name
    $marker = Join-Path $destination $MarkerName
    if ((Test-Path -LiteralPath (Join-Path $destination "SKILL.md")) -and (Test-Path -LiteralPath $marker)) {
        $metadata = Get-Content -Raw -LiteralPath $marker | ConvertFrom-Json
        if ($metadata.source_root -eq $ProjectRoot) {
            $name
        }
    }
}

$instructionLines = @(
    "# Codex Image Tools"
    ""
    "The following global Codex skills are installed and available on this computer:"
    ""
)
foreach ($name in $Registered) {
    $instructionLines += ('- `${0}`: {1}.' -f $name, $KnownPipelines[$name])
}
$instructionLines += @(
    ""
    "The source checkout is ``$($ProjectRoot.Replace('\', '/'))``. Read the selected skill before using its pipeline. Follow the active project's AGENTS.md for project-specific rules."
    ""
    "Before Codex visually reads any local raster image, create a preview with ``C:/Users/A/.codex/tools/Convert-CodexImagePreview.ps1`` and inspect only the preview. The preview's longest edge must be at most 512 px. Do not call image-reading tools on original-size images; keep originals only for file operations and provider inputs."
    ""
    "For providers that require the local proxy, use:"
    ""
    "- ``HTTP_PROXY=http://127.0.0.1:7897``"
    "- ``HTTPS_PROXY=http://127.0.0.1:7897``"
    "- ``ALL_PROXY=socks5://127.0.0.1:7897``"
)
$instructions = $instructionLines -join [Environment]::NewLine
$instructionPath = Join-Path $CodexHome "codex-image-global-custom-instructions.md"
[System.IO.File]::WriteAllText($instructionPath, $instructions + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

$statePath = Join-Path $CodexHome "codex-image-registration-state.json"
$existingCompleted = @()
if (Test-Path -LiteralPath $statePath) {
    $existingState = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
    if ($existingState.source_root -eq $ProjectRoot) {
        $existingCompleted = @($existingState.setup_completed_pipelines)
    }
}
$state = [ordered]@{
    source_root = $ProjectRoot
    registered_pipelines = @($Registered)
    selected_pipelines = @($Registered)
    setup_completed_pipelines = @($existingCompleted | Where-Object { $_ -in $Registered })
    first_run_choice_completed = $true
    updated_at = (Get-Date).ToString("o")
}
$state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8

Write-Host ""
Write-Host "Global custom instructions written to: $instructionPath"
Write-Host "Registration state written to: $statePath"
Write-Host ""
Write-Output $instructions
Write-Host ""
Write-Host "The registered skills will be discoverable by Codex on the next turn or after restarting Codex."
