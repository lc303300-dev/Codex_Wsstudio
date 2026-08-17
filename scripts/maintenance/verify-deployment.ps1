[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" })
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Join-Path $PSScriptRoot "..\.."
}
$RepositoryRoot = [System.IO.Path]::GetFullPath($RepositoryRoot)
$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)

$errors = [System.Collections.Generic.List[string]]::new()
function Require-Path {
    param([string]$Path, [string]$Description, [ValidateSet("Leaf", "Container")][string]$Type = "Leaf")
    if (-not (Test-Path -LiteralPath $Path -PathType $Type)) { $errors.Add("Missing $Description`: $Path") }
}

Require-Path (Join-Path $RepositoryRoot "AGENTS.md") "repository guidance"
Require-Path (Join-Path $RepositoryRoot "config\codex\AGENTS.md") "global guidance source"
Require-Path (Join-Path $RepositoryRoot "config\codex\config.portable.toml") "portable config source"
Require-Path (Join-Path $RepositoryRoot "packages") "packages directory" "Container"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_Gif") "GIF package" "Container"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_Gif\register-global-skill.ps1") "GIF registration script"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_Gif\.claude\skills\video-to-gif\SKILL.md") "GIF skill"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_Github\register-global-skill.ps1") "Tool Scout registration script"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_Github\.claude\skills\tool-scout\SKILL.md") "Tool Scout skill"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_image\register-default-media-tools.ps1") "Codex_image media tool registration script"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_DT\register-global-skill.ps1") "Codex_DT registration script"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_DT\.claude\skills\codex-dt-video-prompt\SKILL.md") "Codex_DT skill"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_DT\.claude\skills\video-director-prompt\SKILL.md") "Codex_DT video director skill"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_CS\register-global-skill.ps1") "Codex_CS registration script"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_CS\codex-cs-skill-curator\SKILL.md") "Codex_CS curator skill"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_Batch_Image\register-global-skill.ps1") "batch image registration script"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_Batch_Image\run-batch-image-generation.ps1") "batch image entry point"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_Batch_Image\batch-image-generation\SKILL.md") "batch image skill"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_IS\register-global-skills.ps1") "Codex_IS registration script"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_IS\image-skill-router\SKILL.md") "Codex_IS image router Skill"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_IS\image-skill-curator\SKILL.md") "Codex_IS image curator Skill"
Require-Path (Join-Path $RepositoryRoot "packages\Codex_IS\business-skills\scene-storyboard-grid\SKILL.md") "Codex_IS scene storyboard Skill"
Require-Path (Join-Path $RepositoryRoot "scripts") "scripts directory" "Container"
Require-Path (Join-Path $CodexHome "AGENTS.md") "global Codex guidance"
Require-Path (Join-Path $CodexHome "config.toml") "global Codex config"
Require-Path (Join-Path $CodexHome "skills\default-image-generation\SKILL.md") "global default image generation skill"
Require-Path (Join-Path $CodexHome "skills\default-video-generation\SKILL.md") "global default video generation skill"
Require-Path (Join-Path $CodexHome "skills\batch-image-generation\SKILL.md") "global batch image generation skill"
Require-Path (Join-Path $CodexHome "skills\batch-image-generation\.codex-batch-image-registration.json") "global batch image registration marker"
Require-Path (Join-Path $CodexHome "skills\image-skill-router\SKILL.md") "global Codex_IS image router Skill"
Require-Path (Join-Path $CodexHome "skills\image-skill-router\.codex-is-registration.json") "global Codex_IS router marker"
Require-Path (Join-Path $CodexHome "skills\image-skill-curator\SKILL.md") "global Codex_IS curator Skill"
Require-Path (Join-Path $CodexHome "skills\scene-storyboard-grid\SKILL.md") "global Codex_IS storyboard Skill"
Require-Path (Join-Path $CodexHome "skills\codex-github\SKILL.md") "global Tool Scout skill"
Require-Path (Join-Path $CodexHome "skills\codex-github\scripts\tool_scout.py") "global Tool Scout runtime"
Require-Path (Join-Path $CodexHome "plugins\codex-media-plugin\.codex-plugin\plugin.json") "global codex-media plugin"

$globalConfig = Join-Path $CodexHome "config.toml"
if (Test-Path -LiteralPath $globalConfig -PathType Leaf) {
    $configText = Get-Content -LiteralPath $globalConfig -Raw -Encoding UTF8
    if ($configText -notmatch '\[plugins\."codex-media-plugin@personal"\]' -or $configText -notmatch '(?s)\[plugins\."codex-media-plugin@personal"\].*?enabled\s*=\s*true') {
        $errors.Add("Global Codex config does not enable codex-media-plugin@personal: $globalConfig")
    }
}

$toolScoutSkill = Join-Path $CodexHome "skills\codex-github\SKILL.md"
if (Test-Path -LiteralPath $toolScoutSkill -PathType Leaf) {
    $toolScoutText = Get-Content -LiteralPath $toolScoutSkill -Raw -Encoding UTF8
    if (-not $toolScoutText.Contains('Resolve `scripts/tool_scout.py` relative to this `SKILL.md`')) {
        $errors.Add("Global Tool Scout skill does not use its self-contained runtime entry point: $toolScoutSkill")
    }
    if ($toolScoutText -like '*This global skill is backed by the Codex_Github checkout at*') {
        $errors.Add("Global Tool Scout skill still exposes the source checkout as its runtime path: $toolScoutSkill")
    }
}

$source = Join-Path $RepositoryRoot "config\codex\AGENTS.md"
$target = Join-Path $CodexHome "AGENTS.md"
if ((Test-Path -LiteralPath $source -PathType Leaf) -and (Test-Path -LiteralPath $target -PathType Leaf)) {
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash) {
        $errors.Add("Global AGENTS.md differs from repository source: $target")
    }
}

$ruleText = "proactively prefer sub-agent delegation"
if ((Test-Path -LiteralPath $source -PathType Leaf) -and -not ((Get-Content -LiteralPath $source -Raw -Encoding UTF8) -like "*$ruleText*")) {
    $errors.Add("Sub-agent delegation rule is absent from the repository global guidance source.")
}
if ((Test-Path -LiteralPath $target -PathType Leaf) -and -not ((Get-Content -LiteralPath $target -Raw -Encoding UTF8) -like "*$ruleText*")) {
    $errors.Add("Sub-agent delegation rule is absent from the installed global guidance.")
}

$localMarkdownRuleMarkers = @(
    "Windows local Markdown links and embedded local media as a hard output contract",
    "Use an absolute path with forward slashes",
    "never a file:// URI",
    "if any local target contains a backslash, do not send the response"
)
foreach ($marker in $localMarkdownRuleMarkers) {
    if ((Test-Path -LiteralPath $source -PathType Leaf) -and -not ((Get-Content -LiteralPath $source -Raw -Encoding UTF8) -like "*$marker*")) {
        $errors.Add("Local Markdown resource rule is absent from the repository global guidance source: $marker")
    }
    if ((Test-Path -LiteralPath $target -PathType Leaf) -and -not ((Get-Content -LiteralPath $target -Raw -Encoding UTF8) -like "*$marker*")) {
        $errors.Add("Local Markdown resource rule is absent from the installed global guidance: $marker")
    }
}

$imageRatioRuleMarkers = @(
    "Before every image generation or image edit, require the user to explicitly choose one supported ratio",
    "If no ratio is explicit, refuse to submit generation",
    "structured generate_image image_ratio field"
)
foreach ($marker in $imageRatioRuleMarkers) {
    if ((Test-Path -LiteralPath $source -PathType Leaf) -and -not ((Get-Content -LiteralPath $source -Raw -Encoding UTF8) -like "*$marker*")) {
        $errors.Add("Required image-ratio rule is absent from the repository global guidance source: $marker")
    }
    if ((Test-Path -LiteralPath $target -PathType Leaf) -and -not ((Get-Content -LiteralPath $target -Raw -Encoding UTF8) -like "*$marker*")) {
        $errors.Add("Required image-ratio rule is absent from the installed global guidance: $marker")
    }
}

$imageRouteRuleMarkers = @(
    "Treat the configured image-provider order as the default, not a mandatory workflow",
    "generate_image.image_provider",
    "does not fall back to other routes"
)
foreach ($marker in $imageRouteRuleMarkers) {
    if ((Test-Path -LiteralPath $source -PathType Leaf) -and -not ((Get-Content -LiteralPath $source -Raw -Encoding UTF8) -like "*$marker*")) {
        $errors.Add("Explicit image-route rule is absent from the repository global guidance source: $marker")
    }
    if ((Test-Path -LiteralPath $target -PathType Leaf) -and -not ((Get-Content -LiteralPath $target -Raw -Encoding UTF8) -like "*$marker*")) {
        $errors.Add("Explicit image-route rule is absent from the installed global guidance: $marker")
    }
}

$expectedImageRoot = Join-Path $RepositoryRoot "packages\Codex_image"
$mediaConfigPath = Join-Path $expectedImageRoot "config\media-router.defaults.json"
if (Test-Path -LiteralPath $mediaConfigPath -PathType Leaf) {
    try {
        $mediaConfig = Get-Content -LiteralPath $mediaConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $geminiModel = [string]$mediaConfig.providers."comfly-gemini-lite".model
        if ($geminiModel -ne "gemini-3.1-flash-image-preview") {
            $errors.Add("Comfly Gemini route is not current: $geminiModel")
        }
        $geminiModels = $mediaConfig.providers."comfly-gemini-lite".models_by_resolution
        if ([string]$geminiModels."2K" -ne "gemini-3.1-flash-image-preview-2k" -or [string]$geminiModels."4K" -ne "gemini-3.1-flash-image-preview-4k") {
            $errors.Add("Comfly Gemini resolution model mapping is not current.")
        }
        if ($null -ne $mediaConfig.providers."comfly-gpt-image-2-all") {
            $errors.Add("Retired Comfly gpt-image-2-all route is still configured.")
        }
    } catch {
        $errors.Add("Invalid media router configuration: $mediaConfigPath")
    }
} else {
    $errors.Add("Missing media router configuration: $mediaConfigPath")
}
$routerRoot = Join-Path $expectedImageRoot "CLI\Media-Router"
if ((Test-Path -LiteralPath $routerRoot -PathType Container) -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $probe = @'
import json
from media_router.config import load_config
from media_router.providers.registry import build_registry
config = load_config()
adapter = build_registry(config)["comfly-gemini-lite"]
print(json.dumps({"model": adapter.model_id, "size_profile": adapter.size_profile, "models_by_resolution": adapter.models_by_resolution}))
'@
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = $routerRoot
        $runtimeJson = $probe | python -B -
        if ($LASTEXITCODE -ne 0) { throw "runtime probe failed" }
        $runtime = $runtimeJson | ConvertFrom-Json
        if ([string]$runtime.model -ne "gemini-3.1-flash-image-preview") {
            $errors.Add("Runtime Comfly Gemini route is not current: $($runtime.model)")
        }
        if ([string]$runtime.size_profile -ne "gemini-resolution") {
            $errors.Add("Runtime Comfly Gemini size profile is not current: $($runtime.size_profile)")
        }
        if ([string]$runtime.models_by_resolution."2K" -ne "gemini-3.1-flash-image-preview-2k" -or [string]$runtime.models_by_resolution."4K" -ne "gemini-3.1-flash-image-preview-4k") {
            $errors.Add("Runtime Comfly Gemini resolution model mapping is not current.")
        }
    } catch {
        $errors.Add("Unable to verify the effective runtime Comfly Gemini route.")
    } finally {
        $env:PYTHONPATH = $previousPythonPath
    }
}
$mediaMarkers = @(
    Join-Path $CodexHome "skills\default-image-generation\.codex-image-registration.json"
    Join-Path $CodexHome "skills\default-video-generation\.codex-image-registration.json"
    Join-Path $CodexHome "plugins\codex-media-plugin\.codex-image-registration.json"
    Join-Path ([Environment]::GetFolderPath("UserProfile")) "plugins\codex-media-plugin\.codex-image-registration.json"
)
foreach ($marker in $mediaMarkers) {
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        $errors.Add("Missing media registration marker: $marker")
        continue
    }
    try {
        $record = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([System.IO.Path]::GetFullPath([string]$record.source_root) -ne $expectedImageRoot) {
            $errors.Add("Media registration marker points to stale source root: $marker -> $($record.source_root)")
        }
    } catch {
        $errors.Add("Invalid media registration marker: $marker")
    }
}

$installedMediaMcp = Join-Path $CodexHome "plugins\codex-media-plugin\mcp\run.ps1"
if (Test-Path -LiteralPath $installedMediaMcp -PathType Leaf) {
    try {
        $toolListRequest = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
        $toolListOutput = $toolListRequest | powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installedMediaMcp
        if ($LASTEXITCODE -ne 0) {
            throw "codex-media MCP probe exited with code $LASTEXITCODE"
        }
        $toolListJson = @($toolListOutput | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })[-1]
        $toolList = $toolListJson | ConvertFrom-Json
        if ($toolList.error) {
            throw "codex-media MCP tools/list returned error: $($toolList.error.message)"
        }
        $mediaToolNames = @($toolList.result.tools | ForEach-Object { [string]$_.name })
        foreach ($expectedTool in @("generate_image", "generate_video")) {
            if ($expectedTool -notin $mediaToolNames) {
                $errors.Add("codex-media MCP tools/list does not expose $expectedTool. Returned: $($mediaToolNames -join ', ')")
            }
        }
    } catch {
        $errors.Add("Unable to verify codex-media MCP tools/list from installed plugin: $installedMediaMcp ($($_.Exception.Message))")
    }
} else {
    $errors.Add("Missing installed codex-media MCP runner: $installedMediaMcp")
}

$batchMarker = Join-Path $CodexHome "skills\batch-image-generation\.codex-batch-image-registration.json"
if (Test-Path -LiteralPath $batchMarker -PathType Leaf) {
    try {
        $record = Get-Content -LiteralPath $batchMarker -Raw -Encoding UTF8 | ConvertFrom-Json
        $expectedBatchRoot = Join-Path $RepositoryRoot "packages\Codex_Batch_Image"
        if ([IO.Path]::GetFullPath([string]$record.source_root) -ne $expectedBatchRoot) {
            $errors.Add("Batch image registration marker points to stale source root: $batchMarker -> $($record.source_root)")
        }
    } catch { $errors.Add("Invalid batch image registration marker: $batchMarker") }
}

$expectedPreview = Join-Path $CodexHome "tools\Convert-CodexImagePreview.ps1"
if (-not (Test-Path -LiteralPath $expectedPreview -PathType Leaf)) {
    $errors.Add("Missing global preview converter: $expectedPreview")
} else {
    $previewText = Get-Content -LiteralPath $expectedPreview -Raw -Encoding UTF8
    if ($previewText -notmatch '\[ValidateRange\(1, 1024\)\]\[int\]\$MaxLongEdge = 1024') {
        $errors.Add("Global preview converter is not updated to the 1024px limit: $expectedPreview")
    }
}

$cacheRoot = Join-Path $CodexHome "plugins\cache\personal\codex-media-plugin"
if (Test-Path -LiteralPath $cacheRoot -PathType Container) {
    Get-ChildItem -LiteralPath $cacheRoot -Directory | ForEach-Object {
        $requiredCachePaths = @(
            ".codex-plugin\plugin.json",
            ".mcp.json",
            "mcp\run.ps1",
            "skills\default-image-generation\SKILL.md",
            "skills\default-video-generation\SKILL.md"
        )
        foreach ($relativePath in $requiredCachePaths) {
            $requiredPath = Join-Path $_.FullName $relativePath
            if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
                $errors.Add("Incomplete cached media plugin; missing $relativePath`: $($_.FullName)")
            }
        }
        $cacheMarker = Join-Path $_.FullName ".codex-image-registration.json"
        if (-not (Test-Path -LiteralPath $cacheMarker -PathType Leaf)) {
            $errors.Add("Missing cached media plugin registration marker: $cacheMarker")
            return
        }
        try {
            $record = Get-Content -LiteralPath $cacheMarker -Raw -Encoding UTF8 | ConvertFrom-Json
            if ([System.IO.Path]::GetFullPath([string]$record.source_root) -ne $expectedImageRoot) {
                $errors.Add("Cached media plugin marker points to stale source root: $cacheMarker -> $($record.source_root)")
            }
        } catch {
            $errors.Add("Invalid cached media plugin marker: $cacheMarker")
        }
    }
}

$gifRuleText = "video to GIF"
$gifSource = Join-Path $RepositoryRoot "config\codex\AGENTS.md"
if ((Test-Path -LiteralPath $gifSource -PathType Leaf) -and -not ((Get-Content -LiteralPath $gifSource -Raw -Encoding UTF8) -like "*$gifRuleText*")) {
    $errors.Add("GIF trigger rule is absent from the repository global guidance source.")
}

$structure = Join-Path $RepositoryRoot "scripts\maintenance\test-project-structure.ps1"
if (Test-Path -LiteralPath $structure -PathType Leaf) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $structure -RepositoryRoot $RepositoryRoot
    if ($LASTEXITCODE -ne 0) { $errors.Add("Project structure validation failed.") }
}
else { $errors.Add("Project structure validator is missing: $structure") }

if ($errors.Count -gt 0) {
    Write-Host "Deployment verification failed:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host "Deployment verification passed: paths, guidance, config, and structure are current." -ForegroundColor Green
