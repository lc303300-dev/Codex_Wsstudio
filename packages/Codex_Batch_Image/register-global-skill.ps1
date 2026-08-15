[CmdletBinding()]
param([string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }))
$ErrorActionPreference = "Stop"
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$source = Join-Path $projectRoot "batch-image-generation"
if (-not (Test-Path -LiteralPath (Join-Path $source "SKILL.md") -PathType Leaf)) { throw "Batch image skill source is missing." }
$skillsRoot = Join-Path ([IO.Path]::GetFullPath($CodexHome)) "skills"
$destination = Join-Path $skillsRoot "batch-image-generation"
$marker = Join-Path $destination ".codex-batch-image-registration.json"
New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null
if (Test-Path -LiteralPath $destination) {
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw "Refusing to replace unmanaged skill '$destination'." }
    $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([IO.Path]::GetFullPath([string]$record.source_root) -ne $projectRoot) { throw "Refusing to replace a skill managed by another source root." }
    Remove-Item -LiteralPath $destination -Recurse -Force
}
$temporary = Join-Path $skillsRoot (".codex-batch-image-install-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $temporary | Out-Null
    Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $temporary -Recurse -Force
    [ordered]@{ skill="batch-image-generation"; source_root=$projectRoot; registered_at=(Get-Date).ToString("o") } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-batch-image-registration.json") -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $destination
} finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force } }
Write-Host "Registered global batch-image-generation skill: $destination"
