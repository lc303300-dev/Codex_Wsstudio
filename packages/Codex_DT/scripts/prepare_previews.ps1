param(
    [string]$InputDirectory = "inputs",
    [string]$OutputDirectory = "previews",
    [int]$MaxLongEdge = 1024,
    [string]$PreviewTool,
    [string]$Batch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($MaxLongEdge -lt 1 -or $MaxLongEdge -gt 1024) {
    throw "MaxLongEdge must be between 1 and 1024. Codex visual inspection must never receive a larger local raster preview."
}

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$localConfigPath = Join-Path $root "config/pipeline.local.json"
$configPath = Join-Path $root "config/pipeline.json"
if ([string]::IsNullOrWhiteSpace($PreviewTool)) {
    if (Test-Path -LiteralPath $localConfigPath) {
        $localConfig = Get-Content -LiteralPath $localConfigPath -Encoding UTF8 -Raw | ConvertFrom-Json
        $PreviewTool = [string]$localConfig.paths.preview_tool
    }
    elseif (Test-Path -LiteralPath $configPath) {
        $config = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw | ConvertFrom-Json
        $PreviewTool = [string]$config.paths.preview_tool
    }
}
if (-not [string]::IsNullOrWhiteSpace($Batch)) {
    $InputDirectory = Join-Path $InputDirectory $Batch
    $OutputDirectory = Join-Path $OutputDirectory $Batch
}
$inputRoot = Join-Path $root $InputDirectory
$outputRoot = Join-Path $root $OutputDirectory

if (-not (Test-Path -LiteralPath $inputRoot)) {
    throw "Input directory not found: $inputRoot"
}
if ([string]::IsNullOrWhiteSpace($PreviewTool)) {
    throw "Preview tool is not configured. Run scripts/deploy_project.ps1 first."
}
if (-not (Test-Path -LiteralPath $PreviewTool)) {
    throw "Preview tool not found: $PreviewTool"
}

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

$extensions = @(".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".heic", ".heif")
$images = Get-ChildItem -LiteralPath $inputRoot -File | Where-Object { $extensions -contains $_.Extension.ToLowerInvariant() }

$records = @()
foreach ($image in $images) {
    $json = powershell -NoProfile -ExecutionPolicy Bypass -File $PreviewTool `
        -InputPath $image.FullName `
        -MaxLongEdge $MaxLongEdge `
        -OutputDirectory $outputRoot
    $record = $json | ConvertFrom-Json
    if ([int]$record.preview_width -gt 1024 -or [int]$record.preview_height -gt 1024 -or [int]$record.max_long_edge -gt 1024) {
        throw "Preview converter returned an image larger than the permitted 1024px long edge: $($record.preview_path)"
    }
    $records += $record
    $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension([string]$record.preview_path, ".json")) -Encoding UTF8
}

$manifestPath = Join-Path $outputRoot "_previews.json"
if ($records.Count -eq 0) {
    "[]" | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}
else {
    $records | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}
Write-Host "Prepared $($records.Count) preview(s)."
Write-Host "Preview manifest: $manifestPath"
