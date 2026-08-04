param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [Parameter(Mandatory = $true)]
    [string]$MetadataPath,

    [int]$MaxLongEdge = 1920
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($MaxLongEdge -lt 1) {
    throw "MaxLongEdge must be greater than 0."
}

$resolvedInput = Resolve-Path -LiteralPath $InputPath
$inputItem = Get-Item -LiteralPath $resolvedInput.Path
if ($inputItem.PSIsContainer) {
    throw "InputPath must point to an image file."
}

Add-Type -AssemblyName System.Drawing

$source = [System.Drawing.Image]::FromFile($inputItem.FullName)
try {
    # Normalize EXIF orientation before calculating the provider-facing dimensions.
    if ($source.PropertyIdList -contains 0x0112) {
        $orientation = [int]$source.GetPropertyItem(0x0112).Value[0]
        $rotation = switch ($orientation) {
            2 { [System.Drawing.RotateFlipType]::RotateNoneFlipX }
            3 { [System.Drawing.RotateFlipType]::Rotate180FlipNone }
            4 { [System.Drawing.RotateFlipType]::Rotate180FlipX }
            5 { [System.Drawing.RotateFlipType]::Rotate90FlipX }
            6 { [System.Drawing.RotateFlipType]::Rotate90FlipNone }
            7 { [System.Drawing.RotateFlipType]::Rotate270FlipX }
            8 { [System.Drawing.RotateFlipType]::Rotate270FlipNone }
            default { [System.Drawing.RotateFlipType]::RotateNoneFlipNone }
        }
        if ($rotation -ne [System.Drawing.RotateFlipType]::RotateNoneFlipNone) {
            $source.RotateFlip($rotation)
        }
    }

    $sourceWidth = [int]$source.Width
    $sourceHeight = [int]$source.Height
    $longEdge = [Math]::Max($sourceWidth, $sourceHeight)
    $resized = $longEdge -gt $MaxLongEdge

    if ($resized) {
        $scale = [double]$MaxLongEdge / [double]$longEdge
        $targetWidth = [Math]::Max(1, [int][Math]::Round($sourceWidth * $scale))
        $targetHeight = [Math]::Max(1, [int][Math]::Round($sourceHeight * $scale))
        $outputDirectory = Split-Path -Parent $OutputPath
        New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
        $temporaryPath = Join-Path $outputDirectory (".{0}.{1}.tmp.png" -f [IO.Path]::GetFileNameWithoutExtension($OutputPath), [Guid]::NewGuid().ToString("N"))

        $bitmap = [System.Drawing.Bitmap]::new($targetWidth, $targetHeight, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
                $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
                $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
                $graphics.DrawImage($source, 0, 0, $targetWidth, $targetHeight)
            } finally {
                $graphics.Dispose()
            }
            $bitmap.Save($temporaryPath, [System.Drawing.Imaging.ImageFormat]::Png)
            Move-Item -LiteralPath $temporaryPath -Destination $OutputPath -Force
        } finally {
            $bitmap.Dispose()
            if (Test-Path -LiteralPath $temporaryPath) {
                Remove-Item -LiteralPath $temporaryPath -Force
            }
        }
        $providerPath = [System.IO.Path]::GetFullPath($OutputPath)
    } else {
        $targetWidth = $sourceWidth
        $targetHeight = $sourceHeight
        $providerPath = $inputItem.FullName
    }

    $metadata = [ordered]@{
        provider_path = $providerPath
        resized = $resized
        original_width = $sourceWidth
        original_height = $sourceHeight
        provider_width = $targetWidth
        provider_height = $targetHeight
        max_long_edge = $MaxLongEdge
    }
    $metadataDirectory = Split-Path -Parent $MetadataPath
    New-Item -ItemType Directory -Force -Path $metadataDirectory | Out-Null
    $metadata | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $MetadataPath -Encoding UTF8
} finally {
    $source.Dispose()
}
