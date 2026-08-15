[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" })
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$skillsRoot = Join-Path $CodexHome "skills"
New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null

function Install-CodexCsSkill {
    param(
        [Parameter(Mandatory = $true)][string]$SkillName,
        [Parameter(Mandatory = $true)][string]$InstallationNote
    )
    $skillSource = Join-Path $projectRoot $SkillName
    $skillFile = Join-Path $skillSource "SKILL.md"
    if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
        throw "Codex_CS skill source is missing: $skillFile"
    }
    $destination = Join-Path $skillsRoot $SkillName
    $marker = Join-Path $destination ".codex-cs-registration.json"
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
    $temporary = Join-Path $skillsRoot (".codex-cs-install-" + [guid]::NewGuid().ToString("N"))
    try {
        New-Item -ItemType Directory -Path $temporary | Out-Null
        Get-ChildItem -LiteralPath $skillSource -Force | Copy-Item -Destination $temporary -Recurse -Force

        $installedSkill = Join-Path $temporary "SKILL.md"
        $text = [System.IO.File]::ReadAllText($installedSkill)
        $text = [regex]::Replace($text, '(?ims)^## Local Installation\s*\r?\n.*?(?=^## |\z)', '')
        $note = @'

## Local Installation

This global skill is backed by the Codex_CS checkout at `{0}`. {1}

'@ -f $projectRoot.Replace('\','/'), $InstallationNote
        $text = [regex]::Replace($text, '\A(---\r?\n.*?\r?\n---\r?\n)', { param($match) $match.Groups[1].Value + $note }, [System.Text.RegularExpressions.RegexOptions]::Singleline)
        [System.IO.File]::WriteAllText($installedSkill, $text, [System.Text.UTF8Encoding]::new($false))

        [ordered]@{ skill = $SkillName; source_root = $projectRoot; registered_at = (Get-Date).ToString("o") } |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-cs-registration.json") -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $destination
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
    }
    Write-Host "Registered global $SkillName skill: $destination"
}

Install-CodexCsSkill -SkillName "codex-cs-skill-curator" -InstallationNote "Use it for governed video business Skill intake, migration, validation, and publication review only. It does not generate videos or call paid media execution."
Install-CodexCsSkill -SkillName "video-skill-router" -InstallationNote "Use it as the Codex_CS project orchestrator: confirm Skill, ratio, and duration; create contract-slot folders; branch between user-supplied and generated images; let the business Skill author the first prompt; and route only requested revisions to Codex_DT."

$instructionPath = Join-Path $CodexHome "codex-cs-global-custom-instructions.md"
$instructions = @"
# Codex CS Skill Curator

Use the globally registered `codex-cs-skill-curator` skill for adding, migrating, reviewing, validating, or publishing governed video business Skills. When a user wants to use a business Skill to make a video, use `video-skill-router` to select the Skill from creative intent and explicitly confirm the Skill name, ratio, and duration before creating a project. Create contract-slot material folders, ask whether images should be generated, and persist the ordered final media set. The business Skill creates prompt V1. Any user-requested revision automatically routes to Codex_DT; clear local edits skip corpus search, while ambiguous creative or structural changes may search at most three examples. Every prompt version must be confirmed before paid video execution. Do not choose a Skill primarily from materials the user happens to have. Codex_CS never selects providers or actual model versions. Paid image and video execution remains downstream in the Wsstudio media router path.

Source checkout: $($projectRoot.Replace('\','/'))
"@
[System.IO.File]::WriteAllText($instructionPath, $instructions.Trim() + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

Write-Host "Wrote custom instructions: $instructionPath"
