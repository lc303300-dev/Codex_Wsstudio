[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" })
)

$ErrorActionPreference = "Stop"
$CodexHome = [IO.Path]::GetFullPath($CodexHome)
$skillsRoot = [IO.Path]::GetFullPath((Join-Path $CodexHome "skills"))
$legacySkills = @("image-skill-router", "image-skill-curator", "codex-cs-skill-curator", "video-skill-router")
$removed = [System.Collections.Generic.List[string]]::new()
$skipped = [System.Collections.Generic.List[string]]::new()

foreach ($name in $legacySkills) {
    $path = [IO.Path]::GetFullPath((Join-Path $skillsRoot $name))
    if (-not $path.StartsWith($skillsRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove outside Codex skills root: $path"
    }
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        continue
    }
    $hasLegacyMarker = (Test-Path -LiteralPath (Join-Path $path ".codex-is-registration.json") -PathType Leaf) -or
        (Test-Path -LiteralPath (Join-Path $path ".codex-cs-registration.json") -PathType Leaf)
    if (-not $hasLegacyMarker) {
        $skipped.Add($path)
        continue
    }
    Remove-Item -LiteralPath $path -Recurse -Force
    $removed.Add($path)
}

[ordered]@{
    removed = @($removed)
    skipped_unmanaged = @($skipped)
} | ConvertTo-Json -Depth 3
