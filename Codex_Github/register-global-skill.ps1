[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }),
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$source = Join-Path $projectRoot "tool-scout-skill\.claude\skills\tool-scout"
$skillFile = Join-Path $source "SKILL.md"
if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) { throw "Tool Scout skill source is missing: $skillFile" }

$skillsRoot = Join-Path ([System.IO.Path]::GetFullPath($CodexHome)) "skills"
$destination = Join-Path $skillsRoot "tool-scout"
$marker = Join-Path $destination ".codex-github-registration.json"
New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null

if (Test-Path -LiteralPath $destination) {
    if (-not $Force -and -not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        throw "Global skill '$destination' already exists and is unmanaged. Use -Force to replace it."
    }
    Remove-Item -LiteralPath $destination -Recurse -Force
}

$temporary = Join-Path $skillsRoot (".codex-github-install-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $temporary | Out-Null
    Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $temporary -Recurse -Force
    $text = [System.IO.File]::ReadAllText((Join-Path $temporary "SKILL.md"))
    $note = "`r`n## Local Installation`r`n`r`nThis global skill is backed by the Codex_Github checkout at ``$($projectRoot.Replace('\','/'))``. Run the bundled ``scripts/tool_scout.py`` with Python 3.10+ when the task matches the discovery triggers.`r`n"
    if ($text -notmatch '(?m)^## Local Installation\s*$') {
        $text = [regex]::Replace($text, '\A(---\r?\n.*?\r?\n---\r?\n)', { param($m) $m.Groups[1].Value + $note }, [Text.RegularExpressions.RegexOptions]::Singleline)
    }
    [IO.File]::WriteAllText((Join-Path $temporary "SKILL.md"), $text, [Text.UTF8Encoding]::new($false))
    [ordered]@{ skill = "tool-scout"; source_root = $projectRoot; registered_at = (Get-Date).ToString("o") } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-github-registration.json") -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $destination
} finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force } }

$instructionPath = Join-Path $CodexHome "codex-github-global-custom-instructions.md"
$instructions = @"
# Codex GitHub / Tool Scout

Use the globally registered `tool-scout` skill for tool-discovery requests: finding existing software, GitHub repositories, npm packages, MCP servers, Agent Skills, plugins, extensions, APIs, integrations, or alternatives before building from scratch. It also applies when a task involves integration, workflow automation, browser/agent control, or choosing between Skill/MCP/CLI/extension types. Run the bundled script only after reading the skill and follow the active project's AGENTS.md.

Source checkout: $($projectRoot.Replace('\','/'))
"@
[IO.File]::WriteAllText($instructionPath, $instructions.Trim() + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
Write-Host "Registered global tool-scout skill: $destination" -ForegroundColor Green
Write-Host "Wrote custom instructions: $instructionPath"
