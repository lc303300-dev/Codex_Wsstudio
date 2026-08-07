[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" })
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$skillSource = Join-Path $projectRoot ".claude\skills\video-to-gif"
$skillFile = Join-Path $skillSource "SKILL.md"
if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
    throw "GIF skill source is missing: $skillFile"
}

$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$skillsRoot = Join-Path $CodexHome "skills"
$destination = Join-Path $skillsRoot "video-to-gif"
$marker = Join-Path $destination ".codex-gif-registration.json"
New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null

if (Test-Path -LiteralPath $destination) {
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        throw "Refusing to replace unmanaged skill '$destination'."
    }
    $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($record.source_root -ne $projectRoot) {
        throw "Refusing to replace a skill managed by another source root."
    }
    Remove-Item -LiteralPath $destination -Recurse -Force
}

$temporary = Join-Path $skillsRoot (".codex-gif-install-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $temporary | Out-Null
    Get-ChildItem -LiteralPath $skillSource -Force | Copy-Item -Destination $temporary -Recurse -Force
    [ordered]@{
        skill = "video-to-gif"
        source_root = $projectRoot
        registered_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-gif-registration.json") -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $destination
} finally {
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary -Recurse -Force
    }
}

$instructionPath = Join-Path $CodexHome "video-to-gif-global-custom-instructions.md"
$instructions = @"
# Video to GIF

Use the globally registered `video-to-gif` skill for requests that convert local videos to GIFs, batch process clips, or need a GIF under a size cap. Prefer the `Codex_Gif` package pipeline first and use its `run-video-to-gif.ps1` entry point.

Source checkout: $($projectRoot.Replace('\','/'))
"@
[IO.File]::WriteAllText($instructionPath, $instructions.Trim() + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))

Write-Host "Registered global video-to-gif skill: $destination"
Write-Host "Wrote custom instructions: $instructionPath"
