[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" })
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$skillSource = Join-Path $projectRoot "codex-cs-skill-curator"
$skillFile = Join-Path $skillSource "SKILL.md"
if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
    throw "Codex_CS curator skill source is missing: $skillFile"
}

$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$skillsRoot = Join-Path $CodexHome "skills"
$destination = Join-Path $skillsRoot "codex-cs-skill-curator"
$marker = Join-Path $destination ".codex-cs-registration.json"
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

$temporary = Join-Path $skillsRoot (".codex-cs-install-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $temporary | Out-Null
    Get-ChildItem -LiteralPath $skillSource -Force | Copy-Item -Destination $temporary -Recurse -Force

    $installedSkill = Join-Path $temporary "SKILL.md"
    $text = [System.IO.File]::ReadAllText($installedSkill)
    $text = [regex]::Replace($text, '(?ims)^## Local Installation\s*\r?\n.*?(?=^## |\z)', '')
    $note = @'

## Local Installation

This global skill is backed by the Codex_CS checkout at `{0}`. Use it for governed video business Skill intake, migration, validation, and publication review only. It does not generate videos or call paid media execution.

'@ -f $projectRoot.Replace('\','/')
    $text = [regex]::Replace(
        $text,
        '\A(---\r?\n.*?\r?\n---\r?\n)',
        { param($match) $match.Groups[1].Value + $note },
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
    [System.IO.File]::WriteAllText($installedSkill, $text, [System.Text.UTF8Encoding]::new($false))

    [ordered]@{
        skill = "codex-cs-skill-curator"
        source_root = $projectRoot
        registered_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-cs-registration.json") -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $destination
} finally {
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary -Recurse -Force
    }
}

$instructionPath = Join-Path $CodexHome "codex-cs-global-custom-instructions.md"
$instructions = @"
# Codex CS Skill Curator

Use the globally registered `codex-cs-skill-curator` skill for adding, migrating, reviewing, validating, or publishing governed video business Skills. Codex_CS owns business Skill intake and experience preservation; it never submits videos, selects providers, selects actual model versions, polls, downloads, or spends credits. Paid video execution remains downstream in the Wsstudio media router path.

Source checkout: $($projectRoot.Replace('\','/'))
"@
[System.IO.File]::WriteAllText($instructionPath, $instructions.Trim() + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

Write-Host "Registered global codex-cs-skill-curator skill: $destination"
Write-Host "Wrote custom instructions: $instructionPath"
