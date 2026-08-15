param(
    [string]$InputDir = ".\input",
    [string]$OutputDir = ".\output",
    [double]$MaxSizeMB = 10,
    [int]$Fps = 24,
    [int]$MinFps = 1,
    [int]$StartWidth = 720,
    [int]$FpsDropBelowWidth = 9999,
    [int]$MinWidth = 480,
    [int]$MaxHeight = 0,
    [ValidateSet("strict", "quality")]
    [string]$Mode = "quality",
    [switch]$Recursive,
    [double]$MaxDurationSec = 0,
    [int[]]$Widths = @(),
    [int[]]$LowerFpsPlan = @(20, 18, 15, 12, 10, 8, 6, 5, 4, 3, 2, 1),
    [int[]]$ColorCounts = @(160),
    [ValidateSet("bayer", "sierra2_4a", "floyd_steinberg", "none")]
    [string[]]$DitherModes = @("bayer"),
    [ValidateSet("diff", "full", "single")]
    [string]$PaletteStatsMode = "diff",
    [ValidateSet("rectangle", "none")]
    [string]$DiffMode = "rectangle",
    [ValidateRange(0, 5)]
    [int]$BayerScale = 4,
    [ValidateRange(0, 200)]
    [int]$Lossy = 0,
    [ValidateSet("off", "light", "medium")]
    [string]$Denoise = "light",
    [switch]$AntiMoire,
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"

function Resolve-Tool {
    param([string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    return $null
}

function New-CleanDirectory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Get-SafeFileName {
    param([string]$Name)

    $invalidChars = [System.IO.Path]::GetInvalidFileNameChars()
    $result = $Name
    foreach ($char in $invalidChars) {
        $result = $result.Replace($char, "_")
    }
    return $result
}

function Invoke-Process {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $FilePath @Arguments 1> $stdoutPath 2> $stderrPath
        $exitCode = $LASTEXITCODE
        $stdout = Get-Content -LiteralPath $stdoutPath -Raw -Encoding UTF8
        $stderr = Get-Content -LiteralPath $stderrPath -Raw -Encoding UTF8
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
    }

    if ($exitCode -ne 0) {
        $details = (($stderr + "`n" + $stdout) -split "`r?`n" |
            Where-Object { $_ -and $_ -notmatch "^(ffmpeg|ffprobe) version " -and $_ -notmatch "^\s*(built with|configuration:|lib[a-z]+)" } |
            Select-Object -Last 8) -join "`n"
        if (-not $details) {
            $details = "Exit code $exitCode"
        }
        throw $details
    }

    return $stdout
}

function Get-VideoInfo {
    param(
        [string]$FfprobePath,
        [string]$VideoPath
    )

    $args = @(
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate:format=duration",
        "-of", "json",
        $VideoPath
    )

    $json = Invoke-Process -FilePath $FfprobePath -Arguments $args
    $info = $json | ConvertFrom-Json
    if (-not $info.streams -or $info.streams.Count -lt 1) {
        throw "No video stream found."
    }

    return [pscustomobject]@{
        Width = [int]$info.streams[0].width
        Height = [int]$info.streams[0].height
        FrameRate = [string]$info.streams[0].r_frame_rate
        Duration = [double]$info.format.duration
    }
}

function Get-ScaleFilter {
    param(
        [int]$Width,
        [int]$MaxHeight,
        [int]$Fps,
        [int]$Colors,
        [string]$Dither,
        [bool]$AntiMoire,
        [string]$PaletteStatsMode,
        [string]$DiffMode,
        [int]$BayerScale,
        [string]$Denoise
    )

    if ($MaxHeight -gt 0) {
        $scaleSize = "scale='min($Width,iw)':'min($MaxHeight,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2"
    } else {
        $scaleSize = "scale='min($Width,iw)':-2"
    }

    if ($AntiMoire) {
        $scale = "gblur=sigma=0.55:steps=1,$scaleSize`:flags=bicubic:param0=0:param1=0.5"
    } else {
        $scale = "$scaleSize`:flags=lanczos"
    }

    $preScale = @()
    if ($Denoise -eq "light") {
        $preScale += "atadenoise=0a=0.01:0b=0.04"
    } elseif ($Denoise -eq "medium") {
        $preScale += "atadenoise=0a=0.015:0b=0.06"
        $preScale += "hqdn3d=1.2:1.2:3:3"
    }

    $videoFilters = @($preScale + @("fps=$Fps", $scale)) -join ","
    $stats = "stats_mode=$PaletteStatsMode`:max_colors=$Colors"

    if ($Dither -eq "none") {
        $paletteUse = "paletteuse=dither=none"
    } elseif ($Dither -eq "bayer") {
        $paletteUse = "paletteuse=dither=bayer:bayer_scale=$BayerScale"
    } else {
        $paletteUse = "paletteuse=dither=$Dither"
    }

    if ($DiffMode -eq "rectangle") {
        $paletteUse = "$paletteUse`:diff_mode=rectangle"
    }

    return [pscustomobject]@{
        Palette = "$videoFilters,palettegen=$stats"
        Gif = "$videoFilters[x];[x][1:v]$paletteUse"
    }
}

function Convert-OneAttempt {
    param(
        [string]$FfmpegPath,
        [string]$InputPath,
        [string]$PalettePath,
        [string]$TempGifPath,
        [int]$Width,
        [int]$MaxHeight,
        [int]$Fps,
        [int]$Colors,
        [string]$Dither,
        [double]$MaxDurationSec,
        [bool]$AntiMoire,
        [string]$PaletteStatsMode,
        [string]$DiffMode,
        [int]$BayerScale,
        [string]$Denoise
    )

    $filters = Get-ScaleFilter -Width $Width -MaxHeight $MaxHeight -Fps $Fps -Colors $Colors -Dither $Dither -AntiMoire $AntiMoire -PaletteStatsMode $PaletteStatsMode -DiffMode $DiffMode -BayerScale $BayerScale -Denoise $Denoise
    $durationArgs = @()
    if ($MaxDurationSec -gt 0) {
        $durationArgs = @("-t", ([string]::Format([System.Globalization.CultureInfo]::InvariantCulture, "{0:0.###}", $MaxDurationSec)))
    }

    if (Test-Path -LiteralPath $PalettePath) {
        Remove-Item -LiteralPath $PalettePath -Force
    }
    if (Test-Path -LiteralPath $TempGifPath) {
        Remove-Item -LiteralPath $TempGifPath -Force
    }

    $paletteArgs = @("-y", "-i", $InputPath) + $durationArgs + @("-vf", $filters.Palette, $PalettePath)
    Invoke-Process -FilePath $FfmpegPath -Arguments $paletteArgs | Out-Null

    $gifArgs = @("-y", "-i", $InputPath, "-i", $PalettePath) + $durationArgs + @("-lavfi", $filters.Gif, "-loop", "0")
    $gifArgs += @($TempGifPath)
    Invoke-Process -FilePath $FfmpegPath -Arguments $gifArgs | Out-Null
}

function Optimize-Gif {
    param(
        [string]$GifsiclePath,
        [string]$InputPath,
        [string]$OutputPath,
        [int]$Lossy
    )

    if (-not $GifsiclePath) {
        Copy-Item -LiteralPath $InputPath -Destination $OutputPath -Force
        return
    }

    if (Test-Path -LiteralPath $OutputPath) {
        Remove-Item -LiteralPath $OutputPath -Force
    }

    $args = @("-O3", "--careful")
    if ($Lossy -gt 0) {
        $args += @("--lossy=$Lossy")
    }
    $args += @("-o", $OutputPath, $InputPath)

    Invoke-Process -FilePath $GifsiclePath -Arguments $args | Out-Null
}

function Get-WidthPlan {
    param(
        [int[]]$ExplicitWidths,
        [int]$StartWidth,
        [int]$MinWidth,
        [string]$Mode
    )

    if ($ExplicitWidths.Count -gt 0) {
        return $ExplicitWidths | Where-Object { $_ -gt 0 } | Sort-Object -Descending -Unique
    }

    $base = @(720, 640, 560, 480, 420, 360, 320, 280, 240)
    $selected = $base | Where-Object { $_ -le $StartWidth -and $_ -ge $MinWidth }

    if ($Mode -eq "strict") {
        $extra = @(220, 200, 180, 160, 144, 128, 112, 96)
        $selected = @($selected) + @($extra | Where-Object { $_ -lt $MinWidth })
    }

    return $selected | Sort-Object -Descending -Unique
}

function Get-FpsPlan {
    param(
        [int]$Width,
        [int]$BaseFps,
        [int]$MinFps,
        [int]$FpsDropBelowWidth,
        [int[]]$LowerFpsPlan
    )

    if ($Width -ge $FpsDropBelowWidth) {
        return @($BaseFps)
    }

    $plan = @($BaseFps) + @($LowerFpsPlan | Where-Object { $_ -ge $MinFps -and $_ -lt $BaseFps })
    return $plan | Sort-Object -Descending -Unique
}

function Get-StagedCandidatePlan {
    param(
        [int]$StartWidth,
        [int]$MinWidth,
        [int]$BaseFps,
        [int]$MinFps,
        [string[]]$DitherModes
    )

    $steps = @(
        [pscustomobject]@{ Width = 720; Fps = @($BaseFps, 20, 18, 15, 12, 10, 8); Colors = @(160) },
        [pscustomobject]@{ Width = 720; Fps = @(8); Colors = @(130, 100) },
        [pscustomobject]@{ Width = 640; Fps = @(8, 6); Colors = @(100) },
        [pscustomobject]@{ Width = 640; Fps = @(6); Colors = @(80) },
        [pscustomobject]@{ Width = 640; Fps = @(4); Colors = @(80) },
        [pscustomobject]@{ Width = 480; Fps = @(4); Colors = @(80) }
    )

    $plan = New-Object System.Collections.Generic.List[object]
    $seen = New-Object System.Collections.Generic.HashSet[string]

    foreach ($step in $steps) {
        if ($step.Width -gt $StartWidth -or $step.Width -lt $MinWidth) {
            continue
        }

        foreach ($fps in @($step.Fps | Where-Object { $_ -le $BaseFps -and $_ -ge $MinFps } | Sort-Object -Descending -Unique)) {
            foreach ($colors in $step.Colors) {
                foreach ($dither in $DitherModes) {
                    $key = "$($step.Width)|$fps|$colors|$dither"
                    if ($seen.Add($key)) {
                        $plan.Add([pscustomobject]@{
                            Width = $step.Width
                            Fps = $fps
                            Colors = $colors
                            Dither = $dither
                        }) | Out-Null
                    }
                }
            }
        }
    }

    return $plan
}

function Get-MarkdownFileLink {
    param(
        [string]$Label,
        [string]$Path
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path).Replace('\', '/')
    return "[$Label](<$fullPath>)"
}

$ffmpeg = Resolve-Tool "ffmpeg"
$ffprobe = Resolve-Tool "ffprobe"
$gifsicle = Resolve-Tool "gifsicle"

if (-not $ffmpeg -or -not $ffprobe) {
    throw "ffmpeg and ffprobe are required. Install FFmpeg and make sure both commands are available in PATH."
}

if ($Lossy -gt 0 -and -not $gifsicle) {
    Write-Warning "gifsicle is not available in PATH. -Lossy $Lossy will be ignored."
}

$inputRoot = Resolve-Path -LiteralPath $InputDir
$outputRoot = if (Test-Path -LiteralPath $OutputDir) {
    Resolve-Path -LiteralPath $OutputDir
} else {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
    Resolve-Path -LiteralPath $OutputDir
}

$privateRoot = Join-Path (Get-Location) ".codex-image-private"
$tmpRoot = Join-Path $privateRoot "tmp"
$reportRoot = Join-Path $privateRoot "reports"
New-CleanDirectory $privateRoot
New-CleanDirectory $tmpRoot
New-CleanDirectory $reportRoot

$maxBytes = [int64]($MaxSizeMB * 1000 * 1000)
$effectiveLossy = if ($gifsicle) { $Lossy } else { 0 }
$useStagedPlan = $Widths.Count -eq 0 -and $ColorCounts.Count -eq 1 -and $ColorCounts[0] -eq 160
$widthPlan = @(Get-WidthPlan -ExplicitWidths $Widths -StartWidth $StartWidth -MinWidth $MinWidth -Mode $Mode)
if ($widthPlan.Count -eq 0) {
    throw "No candidate widths available. Check StartWidth, MinWidth, or Widths."
}

$extensions = @(".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
$searchOption = if ($Recursive) { [System.IO.SearchOption]::AllDirectories } else { [System.IO.SearchOption]::TopDirectoryOnly }
$videos = [System.IO.Directory]::EnumerateFiles($inputRoot.Path, "*", $searchOption) |
    Where-Object { $extensions -contains ([System.IO.Path]::GetExtension($_).ToLowerInvariant()) } |
    Sort-Object

$results = New-Object System.Collections.Generic.List[object]

foreach ($video in $videos) {
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($video)
    $safeName = Get-SafeFileName $baseName
    $outputPath = Join-Path $outputRoot.Path "$safeName.gif"
    $attemptRoot = Join-Path $tmpRoot ([guid]::NewGuid().ToString("N"))
    New-CleanDirectory $attemptRoot

    $status = "failed"
    $reason = ""
    $finalWidth = $null
    $finalFps = $null
    $finalColors = $null
    $finalDither = $null
    $finalBytes = $null
    $finalLossy = $null
    $finalDenoise = $null

    try {
        $videoInfo = Get-VideoInfo -FfprobePath $ffprobe -VideoPath $video

        if ((Test-Path -LiteralPath $outputPath) -and -not $Overwrite) {
            throw "Output exists. Use -Overwrite to replace it."
        }

        $candidatePlan = New-Object System.Collections.Generic.List[object]
        if ($useStagedPlan) {
            foreach ($candidate in @(Get-StagedCandidatePlan -StartWidth $StartWidth -MinWidth $MinWidth -BaseFps $Fps -MinFps $MinFps -DitherModes $DitherModes)) {
                $candidatePlan.Add($candidate) | Out-Null
            }
        } else {
            foreach ($width in $widthPlan) {
                $fpsPlan = @(Get-FpsPlan -Width $width -BaseFps $Fps -MinFps $MinFps -FpsDropBelowWidth $FpsDropBelowWidth -LowerFpsPlan $LowerFpsPlan)
                foreach ($attemptFps in $fpsPlan) {
                    foreach ($colors in $ColorCounts) {
                        foreach ($dither in $DitherModes) {
                            $candidatePlan.Add([pscustomobject]@{
                                Width = $width
                                Fps = $attemptFps
                                Colors = $colors
                                Dither = $dither
                            }) | Out-Null
                        }
                    }
                }
            }
        }

        foreach ($candidate in $candidatePlan) {
            $palettePath = Join-Path $attemptRoot "palette-$($candidate.Width)-$($candidate.Fps)-$($candidate.Colors)-$($candidate.Dither).png"
            $tempGifPath = Join-Path $attemptRoot "raw-$($candidate.Width)-$($candidate.Fps)-$($candidate.Colors)-$($candidate.Dither).gif"
            $candidatePath = Join-Path $attemptRoot "candidate-$($candidate.Width)-$($candidate.Fps)-$($candidate.Colors)-$($candidate.Dither).gif"

            Convert-OneAttempt `
                -FfmpegPath $ffmpeg `
                -InputPath $video `
                -PalettePath $palettePath `
                -TempGifPath $tempGifPath `
                -Width $candidate.Width `
                -MaxHeight $MaxHeight `
                -Fps $candidate.Fps `
                -Colors $candidate.Colors `
                -Dither $candidate.Dither `
                -MaxDurationSec $MaxDurationSec `
                -AntiMoire ([bool]$AntiMoire) `
                -PaletteStatsMode $PaletteStatsMode `
                -DiffMode $DiffMode `
                -BayerScale $BayerScale `
                -Denoise $Denoise

            Optimize-Gif -GifsiclePath $gifsicle -InputPath $tempGifPath -OutputPath $candidatePath -Lossy $effectiveLossy
            $size = (Get-Item -LiteralPath $candidatePath).Length

            if ($size -le $maxBytes) {
                Copy-Item -LiteralPath $candidatePath -Destination $outputPath -Force
                $status = "success"
                $reason = ""
                $finalWidth = $candidate.Width
                $finalFps = $candidate.Fps
                $finalColors = $candidate.Colors
                $finalDither = $candidate.Dither
                $finalBytes = $size
                $finalLossy = $effectiveLossy
                $finalDenoise = $Denoise
                break
            }
        }

        if ($status -ne "success") {
            if ($useStagedPlan) {
                $reason = "Unable to fit under $MaxSizeMB MB after staged fallback through 480px / 4 fps / 80 colors."
            } else {
                $reason = "Unable to fit under $MaxSizeMB MB with fps floor=$MinFps and the configured width/color plan."
            }
        }

        $results.Add([pscustomobject]@{
            Input = $video
            Output = if ($status -eq "success") { $outputPath } else { "" }
            Status = $status
            Reason = $reason
            OriginalWidth = $videoInfo.Width
            OriginalHeight = $videoInfo.Height
            DurationSec = [math]::Round($videoInfo.Duration, 3)
            Fps = $finalFps
            Width = $finalWidth
            Colors = $finalColors
            Dither = $finalDither
            PaletteStatsMode = if ($status -eq "success") { $PaletteStatsMode } else { $null }
            DiffMode = if ($status -eq "success") { $DiffMode } else { $null }
            BayerScale = if ($status -eq "success") { $BayerScale } else { $null }
            Lossy = $finalLossy
            Denoise = $finalDenoise
            SizeBytes = $finalBytes
            SizeMB = if ($finalBytes) { [math]::Round($finalBytes / 1000000, 3) } else { $null }
        }) | Out-Null
    } catch {
        $results.Add([pscustomobject]@{
            Input = $video
            Output = ""
            Status = "failed"
            Reason = $_.Exception.Message
            OriginalWidth = $null
            OriginalHeight = $null
            DurationSec = $null
            Fps = $null
            Width = $null
            Colors = $null
            Dither = $null
            PaletteStatsMode = $null
            DiffMode = $null
            BayerScale = $null
            Lossy = $null
            Denoise = $null
            SizeBytes = $null
            SizeMB = $null
        }) | Out-Null
    } finally {
        if (Test-Path -LiteralPath $attemptRoot) {
            Remove-Item -LiteralPath $attemptRoot -Recurse -Force
        }
    }
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $reportRoot "gif-conversion-report-$timestamp.csv"
$results | Export-Csv -LiteralPath $reportPath -NoTypeInformation -Encoding UTF8

$successCount = @($results | Where-Object { $_.Status -eq "success" }).Count
$failedCount = @($results | Where-Object { $_.Status -ne "success" }).Count

Write-Host "Processed: $($results.Count)"
Write-Host "Succeeded: $successCount"
Write-Host "Failed: $failedCount"
Write-Host "Output folder: $(Get-MarkdownFileLink -Label 'Open output folder' -Path $outputRoot.Path)"
Write-Host "Report: $reportPath"

if ($failedCount -gt 0) {
    Write-Host ""
    Write-Host "Failures:"
    $results | Where-Object { $_.Status -ne "success" } | ForEach-Object {
        Write-Host "- $($_.Input): $($_.Reason)"
    }
}
