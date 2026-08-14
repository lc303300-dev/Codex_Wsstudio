[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" })
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$skillsRoot = Join-Path $CodexHome "skills"
New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null

function Install-CodexDtSkill {
    param(
        [Parameter(Mandatory = $true)][string]$SkillName,
        [Parameter(Mandatory = $true)][string]$InstallationNote
    )

    $skillSource = Join-Path $projectRoot (".claude\skills\" + $SkillName)
    $skillFile = Join-Path $skillSource "SKILL.md"
    if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
        throw "Codex_DT skill source is missing: $skillFile"
    }

    $destination = Join-Path $skillsRoot $SkillName
    $marker = Join-Path $destination ".codex-dt-registration.json"
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

This global skill is backed by the Codex_DT checkout at `{0}`. {1}

'@ -f $projectRoot.Replace('\','/'), $InstallationNote
        $text = [regex]::Replace(
            $text,
            '\A(---\r?\n.*?\r?\n---\r?\n)',
            { param($match) $match.Groups[1].Value + $note },
            [System.Text.RegularExpressions.RegexOptions]::Singleline
        )
        [System.IO.File]::WriteAllText($installedSkill, $text, [System.Text.UTF8Encoding]::new($false))

        [ordered]@{
            skill = $SkillName
            source_root = $projectRoot
            registered_at = (Get-Date).ToString("o")
        } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-dt-registration.json") -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $destination
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Recurse -Force
        }
    }

    Write-Host "Registered global $SkillName skill: $destination"
}

Install-CodexDtSkill `
    -SkillName "video-director-prompt" `
    -InstallationNote "Use it as the platform-neutral directing and prompt-authoring layer. It does not choose providers, model versions, platform labels, or submit generation."
Install-CodexDtSkill `
    -SkillName "codex-dt-video-prompt" `
    -InstallationNote "Resolve optional references relative to that checkout. Use it as the unified public video entry: semantically normalize complete prompts without changing meaning, optimize only incomplete prompts, and hand paid execution to default-video-generation."

$instructionPath = Join-Path $CodexHome "codex-dt-global-custom-instructions.md"
$instructions = @"
# Codex DT Video Prompt

Use `codex-dt-video-prompt` as the unified public orchestrator for general Dreamina/Seedance video requests and `video-director-prompt` only when creative authoring is actually needed. Apply semantic-preserving normalization to complete/final prompts: fix execution labels, reference order, formatting, punctuation, and unambiguous terminology without changing creative meaning. Optimize only incomplete or structurally weak prompts. Project-specific pipelines and local AGENTS.md guidance take priority. Treat corpus model versions as provenance metadata. Default generation to Seedance 2.5; use Seedance 2.0 only when the current user explicitly requests it, and never automatically fall back from 2.5 to 2.0. Prompt skills never call Dreamina CLI directly; paid execution goes through default-video-generation and Media Router.

Source checkout: $($projectRoot.Replace('\','/'))
"@
[System.IO.File]::WriteAllText($instructionPath, $instructions.Trim() + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

Write-Host "Wrote custom instructions: $instructionPath"
