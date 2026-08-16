[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" })
)

$ErrorActionPreference = "Stop"
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$CodexHome = [IO.Path]::GetFullPath($CodexHome)
$skillsRoot = Join-Path $CodexHome "skills"
New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null

function Install-CodexIsSkill {
    param([Parameter(Mandatory = $true)][string]$SkillName, [Parameter(Mandatory = $true)][string]$Source)

    $skillSource = [IO.Path]::GetFullPath($Source)
    if (-not (Test-Path -LiteralPath (Join-Path $skillSource "SKILL.md") -PathType Leaf)) {
        throw "Codex_IS Skill source is missing: $skillSource"
    }
    $destination = Join-Path $skillsRoot $SkillName
    $marker = Join-Path $destination ".codex-is-registration.json"
    if (Test-Path -LiteralPath $destination) {
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw "Refusing to replace unmanaged Skill '$destination'." }
        $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([IO.Path]::GetFullPath([string]$record.source_root) -ne $projectRoot) { throw "Refusing to replace a Skill managed by another source root." }
        Remove-Item -LiteralPath $destination -Recurse -Force
    }
    $temporary = Join-Path $skillsRoot (".codex-is-install-" + [guid]::NewGuid().ToString("N"))
    try {
        New-Item -ItemType Directory -Path $temporary | Out-Null
        Get-ChildItem -LiteralPath $skillSource -Force | Copy-Item -Destination $temporary -Recurse -Force
        [ordered]@{ skill = $SkillName; source_root = $projectRoot; registered_at = (Get-Date).ToString("o") } |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-is-registration.json") -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $destination
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
    }
    Write-Host "Registered global $SkillName Skill: $destination"
}

Install-CodexIsSkill -SkillName "image-skill-router" -Source (Join-Path $projectRoot "image-skill-router")
Install-CodexIsSkill -SkillName "image-skill-curator" -Source (Join-Path $projectRoot "image-skill-curator")
Install-CodexIsSkill -SkillName "scene-storyboard-grid" -Source (Join-Path $projectRoot "business-skills\scene-storyboard-grid")
