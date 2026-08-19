[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" })
)

$ErrorActionPreference = "Stop"
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$CodexHome = [IO.Path]::GetFullPath($CodexHome)
$skillsRoot = Join-Path $CodexHome "skills"
New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null

function Install-CodexFlowSkill {
    param(
        [Parameter(Mandatory = $true)][string]$SkillName,
        [Parameter(Mandatory = $true)][string]$Source
    )

    $skillSource = [IO.Path]::GetFullPath($Source)
    if (-not (Test-Path -LiteralPath (Join-Path $skillSource "SKILL.md") -PathType Leaf)) {
        throw "Codex_Flow Skill source is missing: $skillSource"
    }
    $destination = Join-Path $skillsRoot $SkillName
    $marker = Join-Path $destination ".codex-flow-registration.json"
    $legacyIsMarker = Join-Path $destination ".codex-is-registration.json"
    $legacyCsMarker = Join-Path $destination ".codex-cs-registration.json"
    if (Test-Path -LiteralPath $destination) {
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            if ((Test-Path -LiteralPath $legacyIsMarker -PathType Leaf) -or (Test-Path -LiteralPath $legacyCsMarker -PathType Leaf)) {
                Write-Host "Replacing legacy managed Skill with Codex_Flow Skill: $destination"
                Remove-Item -LiteralPath $destination -Recurse -Force
            } else {
                throw "Refusing to replace unmanaged Skill '$destination'."
            }
        }
        else {
            $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
            if ([IO.Path]::GetFullPath([string]$record.source_root) -ne $projectRoot) {
                throw "Refusing to replace a Skill managed by another source root."
            }
            Remove-Item -LiteralPath $destination -Recurse -Force
        }
    }
    $temporary = Join-Path $skillsRoot (".codex-flow-install-" + [guid]::NewGuid().ToString("N"))
    try {
        New-Item -ItemType Directory -Path $temporary | Out-Null
        Get-ChildItem -LiteralPath $skillSource -Force | Copy-Item -Destination $temporary -Recurse -Force
        [ordered]@{
            skill = $SkillName
            source_root = $projectRoot
            registered_at = (Get-Date).ToString("o")
        } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-flow-registration.json") -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $destination
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
    }
    Write-Host "Registered global $SkillName Skill: $destination"
}

Install-CodexFlowSkill -SkillName "codex-flow" -Source (Join-Path $projectRoot "codex-flow")

$businessRoot = Join-Path $projectRoot "business-skills"
if (Test-Path -LiteralPath $businessRoot -PathType Container) {
    Get-ChildItem -LiteralPath $businessRoot -Directory | Sort-Object Name | ForEach-Object {
        Install-CodexFlowSkill -SkillName $_.Name -Source $_.FullName
    }
}
