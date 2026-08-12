[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" })
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$skillSource = Join-Path $projectRoot ".claude\skills\codex-dt-video-prompt"
$skillFile = Join-Path $skillSource "SKILL.md"
if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
    throw "Codex_DT skill source is missing: $skillFile"
}

$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$skillsRoot = Join-Path $CodexHome "skills"
$destination = Join-Path $skillsRoot "codex-dt-video-prompt"
$marker = Join-Path $destination ".codex-dt-registration.json"
New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null

if (Test-Path -LiteralPath $destination) {
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        throw "Refusing to replace unmanaged skill '$destination'."
    }
    $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([System.IO.Path]::GetFullPath([string]$record.source_root) -ne $projectRoot) {
        throw "Refusing to replace a skill managed by another source root."
    }
    Remove-Item -LiteralPath $destination -Recurse -Force
}

$temporary = Join-Path $skillsRoot (".codex-dt-install-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $temporary | Out-Null
    Get-ChildItem -LiteralPath $skillSource -Force | Copy-Item -Destination $temporary -Recurse -Force

    $installedSkill = Join-Path $temporary "SKILL.md"
    $text = [System.IO.File]::ReadAllText($installedSkill)
    $text = [regex]::Replace($text, '(?ims)^## Local Installation\s*\r?\n.*?(?=^## |\z)', '')
    $note = @'

## Local Installation

This global skill is backed by the Codex_DT checkout at `{0}`. Resolve optional references relative to that checkout. Use it only for prompt optimization and hand off actual generation to `default-video-generation` after user confirmation.

'@ -f $projectRoot.Replace('\','/')
    $text = [regex]::Replace(
        $text,
        '\A(---\r?\n.*?\r?\n---\r?\n)',
        { param($match) $match.Groups[1].Value + $note },
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
    [System.IO.File]::WriteAllText($installedSkill, $text, [System.Text.UTF8Encoding]::new($false))

    [ordered]@{
        skill = "codex-dt-video-prompt"
        source_root = $projectRoot
        registered_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-dt-registration.json") -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $destination
} finally {
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary -Recurse -Force
    }
}

$instructionPath = Join-Path $CodexHome "codex-dt-global-custom-instructions.md"
$instructions = @"
# Codex DT Video Prompt

Use the globally registered `codex-dt-video-prompt` skill as the low-priority default prompt optimization layer for general Dreamina/Seedance video generation requests. Project-specific video pipelines and local AGENTS.md guidance take priority. After prompt optimization, ask whether to call `default-video-generation`; do not submit paid generation from this skill.

Source checkout: $($projectRoot.Replace('\','/'))
"@
[System.IO.File]::WriteAllText($instructionPath, $instructions.Trim() + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

Write-Host "Registered global codex-dt-video-prompt skill: $destination"
Write-Host "Wrote custom instructions: $instructionPath"
