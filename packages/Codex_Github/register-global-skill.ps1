[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }),
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$source = Join-Path $projectRoot ".claude\skills\tool-scout"
$skillFile = Join-Path $source "SKILL.md"
if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) { throw "Tool Scout skill source is missing: $skillFile" }

$skillsRoot = Join-Path ([System.IO.Path]::GetFullPath($CodexHome)) "skills"
$destination = Join-Path $skillsRoot "codex-github"
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
    $text = [regex]::Replace($text, '(?m)^name:\s*tool-scout\s*$', 'name: codex-github')
    $note = "`r`n## Local Installation`r`n`r`nThis installed skill is self-contained. Resolve ``scripts/tool_scout.py`` relative to this ``SKILL.md`` and run that bundled copy with Python 3.10+. Do not use the registration metadata's source checkout as the runtime path.`r`n"
    $text = [regex]::Replace(
        $text,
        '(?ms)^## Local Installation\s*\r?\n.*?(?=^## |\z)',
        ''
    )
    $text = [regex]::Replace($text, '\A(---\r?\n.*?\r?\n---\r?\n)', { param($m) $m.Groups[1].Value + $note }, [Text.RegularExpressions.RegexOptions]::Singleline)
    [IO.File]::WriteAllText((Join-Path $temporary "SKILL.md"), $text, [Text.UTF8Encoding]::new($false))
    [ordered]@{ skill = "codex-github"; source_root = $projectRoot; registered_at = (Get-Date).ToString("o") } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $temporary ".codex-github-registration.json") -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $destination
} finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force } }

$installedSkill = Join-Path $destination "SKILL.md"
$installedScript = Join-Path $destination "scripts\tool_scout.py"
$registration = Get-Content -LiteralPath $marker -Encoding UTF8 -Raw | ConvertFrom-Json
$installedText = [System.IO.File]::ReadAllText($installedSkill)
if (-not (Test-Path -LiteralPath $installedScript -PathType Leaf)) {
    throw "Tool Scout registration is incomplete: $installedScript"
}
if ([System.IO.Path]::GetFullPath([string]$registration.source_root) -ne $projectRoot) {
    throw "Tool Scout registration source mismatch: $($registration.source_root)"
}
if ($installedText -notmatch [regex]::Escape('Resolve `scripts/tool_scout.py` relative to this `SKILL.md`')) {
    throw "Tool Scout SKILL.md does not declare its self-contained runtime entry point."
}

$instructionPath = Join-Path $CodexHome "codex-github-global-custom-instructions.md"
$instructions = @"
# Codex GitHub / Tool Scout

Use the globally registered `codex-github` skill (Codex_Github / Tool Scout) for tool-discovery requests: finding existing software, GitHub repositories, npm packages, MCP servers, Agent Skills, plugins, extensions, APIs, integrations, or alternatives before building from scratch. It also applies when a task involves integration, workflow automation, browser/agent control, or choosing between Skill/MCP/CLI/extension types. Run the bundled script only after reading the skill and follow the active project's AGENTS.md.

"@
[IO.File]::WriteAllText($instructionPath, $instructions.Trim() + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
Write-Host "Registered global tool-scout skill: $destination" -ForegroundColor Green
Write-Host "Wrote custom instructions: $instructionPath"
