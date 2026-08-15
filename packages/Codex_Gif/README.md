# Codex GIF Pipeline

This package provides the default video-to-GIF workflow for this workspace.

It keeps:

- output size at or below `10 MB` (`10,000,000` bytes)
- aspect ratio unchanged
- quality-first defaults that use a staged fallback path and stop once a candidate fits under `10 MB`
- temporary files inside `.codex-image-private`

## Requirements

Install FFmpeg and make sure these commands are available in `PATH`:

```powershell
ffmpeg
ffprobe
```

Optional but recommended:

```powershell
gifsicle
```

`gifsicle` improves GIF compression and enables optional lossy compression. If it is unavailable, the script still works with FFmpeg only.

## Package Layout

```text
packages/Codex_Gif/
  convert-video-to-gif.ps1
  run-video-to-gif.ps1
  register-global-skill.ps1
  .claude/skills/video-to-gif/SKILL.md
  input\
  output\
  .codex-image-private\
    tmp\
    reports\
```

Create `input` and put videos there. The wrapper creates `output` and private runtime folders if needed.

Supported input extensions:

```text
.mp4 .mov .mkv .webm .avi .m4v
```

## Basic Usage

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -MaxSizeMB 10
```

Recursive batch conversion:

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -Recursive
```

Overwrite existing GIF files:

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -Overwrite
```

## Quality Controls

Default behavior is quality-first and uses these rules:

- optimization target: preserve larger size, smoother motion, and higher color depth until a candidate fits
- output style: use `bayer` dithering with light denoise

The tested reference output for `D:\测试\1.mp4` was:

```text
480 x 854 / 4 fps / 80 colors / bayer / light denoise / under 10 MB
```

Important parameters:

```powershell
-Fps 24
-MinFps 1
-StartWidth 720
-FpsDropBelowWidth 9999
-MinWidth 480
-ColorCounts 160
-DitherModes bayer
-MaxSizeMB 10
-Mode quality
```

The pipeline uses FFmpeg's two-pass palette flow by default:

```text
palettegen=stats_mode=diff
paletteuse=diff_mode=rectangle
```

This usually compresses screen recordings and UI videos better because static areas are reused instead of being redrawn every frame.

The default staged fallback path is:

```text
720px: 24, 20, 18, 15, 12, 10, 8 fps at 160 colors
720px: 8 fps at 130, then 100 colors
640px: 8, then 6 fps at 100 colors
640px: 6 fps at 80 colors
640px: 4 fps at 80 colors
480px: 4 fps at 80 colors
```

If the 480px / 4 fps / 80 colors candidate is still larger than `10 MB`, the task fails. Custom `-Widths` or non-default `-ColorCounts` values switch back to the general nested search order:

```text
width -> fps -> color count -> dither mode
```

You can limit the search if you do not want very low frame-rate output:

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -MinFps 4
```

`quality` mode stops at `-MinWidth` and reports failure instead of producing a very small GIF.

`strict` mode may go below `-MinWidth` if needed to satisfy the size limit:

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -Mode strict -MinWidth 240 -ColorCounts 256,192,160,128,96,64
```

For long videos, GIF may be a poor container for `24 fps` plus `10 MB`. You can cap duration:

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -MaxDurationSec 8
```

## Optimization Controls

Quality reference preset:

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -StartWidth 720 -MinWidth 720 -ColorCounts 160 -DitherModes bayer -Denoise light -Overwrite
```

Smaller file preset:

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -Fps 12 -StartWidth 560 -ColorCounts 192,160,128,96,64 -Lossy 80 -Denoise medium -Overwrite
```

High-motion video may look better with error-diffusion dithering:

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -DitherModes sierra2_4a,bayer,none
```

Screen recordings and static-background clips usually compress better with bayer dithering:

```powershell
.\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -DitherModes bayer,none -BayerScale 4
```

Additional parameters:

```powershell
-PaletteStatsMode diff   # diff, full, or single
-DiffMode rectangle      # rectangle or none
-BayerScale 4            # 0..5, higher is more regular and often smaller
-Lossy 40                # gifsicle lossy level, 0 disables
-Denoise light           # off, light, or medium
```

The script no longer asks FFmpeg to stop at the size limit while writing. It writes a complete GIF candidate, runs optional `gifsicle`, measures the result, and only accepts candidates under `-MaxSizeMB`.

## Global Skill

Run `register-global-skill.ps1` to install the package as the global `video-to-gif` skill under the active Codex home.
The repository sync and deployment flows call it automatically, so this skill is registered on other computers after updates.

## Reports

Each run writes a CSV report to:

```text
.codex-image-private\reports\
```

The report includes input path, output path, status, reason, duration, final width, color count, dither mode, palette mode, rectangle diff mode, denoise level, lossy level, and final size.

At the end of each run, the script also prints a clickable Markdown link for opening the output folder directly. On Windows, the link target is an absolute path with forward slashes so Markdown renderers do not treat backslashes as escapes.
