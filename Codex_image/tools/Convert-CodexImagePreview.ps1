[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [ValidateRange(1, 512)][int]$MaxLongEdge = 512,
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
$InputPath = (Resolve-Path -LiteralPath $InputPath).Path
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "codex-image-previews"
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path

$stem = [System.IO.Path]::GetFileNameWithoutExtension($InputPath)
$hashBytes = [System.Security.Cryptography.SHA256]::Create().ComputeHash([System.Text.Encoding]::UTF8.GetBytes($InputPath))
$suffix = -join ($hashBytes[0..3] | ForEach-Object { $_.ToString("x2") })
$outputPath = Join-Path $OutputDirectory "$stem.$suffix.preview.png"

$magick = Get-Command magick -ErrorAction SilentlyContinue
if ($magick) {
    & $magick.Source $InputPath -auto-orient -thumbnail "${MaxLongEdge}x${MaxLongEdge}>" $outputPath
    if ($LASTEXITCODE -ne 0) { throw "ImageMagick failed to create the preview." }
}
else {
    Add-Type -AssemblyName System.Drawing
    $source = [System.Drawing.Image]::FromFile($InputPath)
    try {
        $scale = [Math]::Min(1.0, $MaxLongEdge / [double][Math]::Max($source.Width, $source.Height))
        $width = [Math]::Max(1, [int][Math]::Round($source.Width * $scale))
        $height = [Math]::Max(1, [int][Math]::Round($source.Height * $scale))
        $bitmap = New-Object System.Drawing.Bitmap($width, $height)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.DrawImage($source, 0, 0, $width, $height)
            }
            finally { $graphics.Dispose() }
            $bitmap.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)
        }
        finally { $bitmap.Dispose() }
    }
    finally { $source.Dispose() }
}

Add-Type -AssemblyName System.Drawing
$preview = [System.Drawing.Image]::FromFile($outputPath)
try {
    if ([Math]::Max($preview.Width, $preview.Height) -gt $MaxLongEdge) {
        throw "Generated preview exceeds MaxLongEdge: $outputPath"
    }
    [ordered]@{
        input_path = $InputPath
        preview_path = $outputPath
        preview_width = $preview.Width
        preview_height = $preview.Height
        max_long_edge = $MaxLongEdge
    } | ConvertTo-Json -Compress
}
finally { $preview.Dispose() }
