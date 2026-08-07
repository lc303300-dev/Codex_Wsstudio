param(
    [string]$InputDir = ".\input",
    [string]$OutputDir = "",
    [double]$MaxSizeMB = 10,
    [switch]$Recursive,
    [switch]$Overwrite,
    [double]$MaxDurationSec = 0,
    [int]$MinFps = 1,
    [string[]]$ExtraArgs = @()
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pipeline = Join-Path $root "convert-video-to-gif.ps1"
$privateRoot = Join-Path $root ".codex-image-private"
$ffmpegBin = Join-Path $privateRoot "tools\ffmpeg\ffmpeg-master-latest-win64-gpl\bin"

function Remove-DirectoryIfInside {
    param(
        [string]$BasePath,
        [string]$Path
    )

    $baseFull = [System.IO.Path]::GetFullPath($BasePath).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($baseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove outside private runtime: $pathFull"
    }
    if ([System.IO.Directory]::Exists($pathFull)) {
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                [System.IO.Directory]::Delete($pathFull, $true)
                return
            } catch [System.IO.IOException] {
                if ($attempt -eq 3) {
                    Write-Warning "Skipping locked private runtime directory: $pathFull"
                    return
                }
                Start-Sleep -Milliseconds 300
            }
        }
    }
}

function Remove-FileIfInside {
    param(
        [string]$BasePath,
        [string]$Path
    )

    $baseFull = [System.IO.Path]::GetFullPath($BasePath).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($baseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove outside private runtime: $pathFull"
    }
    if ([System.IO.File]::Exists($pathFull)) {
        [System.IO.File]::Delete($pathFull)
    }
}

function Clear-PrivateRuntime {
    param([string]$PrivatePath)

    New-Item -ItemType Directory -Force -Path $PrivatePath | Out-Null

    $legacyDirectories = @(
        "ffmpeg-btbn",
        "original-resolution-lowfps-input",
        "pipeline-default-test-input",
        "previews",
        "python-packages",
        "quality-original-input",
        "single-input",
        "verify-input",
        "verify-input2",
        "verify-output",
        "verify-output2",
        "verify-output3",
        "verify-output4",
        "verify-output5"
    )

    foreach ($name in $legacyDirectories) {
        Remove-DirectoryIfInside -BasePath $PrivatePath -Path (Join-Path $PrivatePath $name)
    }

    Remove-FileIfInside -BasePath $PrivatePath -Path (Join-Path $PrivatePath "ffmpeg-master-latest-win64-gpl.zip")
    Remove-FileIfInside -BasePath $PrivatePath -Path (Join-Path $PrivatePath "palette.png")

    $tmpPath = Join-Path $PrivatePath "tmp"
    $reportsPath = Join-Path $PrivatePath "reports"
    Remove-DirectoryIfInside -BasePath $PrivatePath -Path $tmpPath
    Remove-DirectoryIfInside -BasePath $PrivatePath -Path $reportsPath
    New-Item -ItemType Directory -Force -Path $tmpPath | Out-Null
    New-Item -ItemType Directory -Force -Path $reportsPath | Out-Null
}

function Clear-OutputRootLooseFiles {
    param([string]$OutputRoot)

    New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
    $outputFull = [System.IO.Path]::GetFullPath($OutputRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    foreach ($file in [System.IO.Directory]::GetFiles($outputFull, "*.gif", [System.IO.SearchOption]::TopDirectoryOnly)) {
        $fileFull = [System.IO.Path]::GetFullPath($file)
        if (-not $fileFull.StartsWith($outputFull, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove outside output root: $fileFull"
        }
        [System.IO.File]::Delete($fileFull)
    }
}

if (-not (Test-Path -LiteralPath $pipeline)) {
    throw "Pipeline script not found: $pipeline"
}

Clear-PrivateRuntime -PrivatePath $privateRoot
Clear-OutputRootLooseFiles -OutputRoot (Join-Path $root "output")

if (Test-Path -LiteralPath $ffmpegBin) {
    $env:PATH = "$ffmpegBin;$env:PATH"
}

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not $ffmpeg -or -not $ffprobe) {
    throw "ffmpeg and ffprobe are required. Expected private runtime at '$ffmpegBin' or commands available in PATH."
}

if (-not $OutputDir) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDir = Join-Path (Join-Path $root "output") "task-$timestamp"
}

if (-not (Test-Path -LiteralPath (Join-Path $root "register-global-skill.ps1") -PathType Leaf)) {
    throw "Global skill registration script is missing."
}

$argsList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $pipeline,
    "-InputDir", $InputDir,
    "-OutputDir", $OutputDir,
    "-MaxSizeMB", ([string]$MaxSizeMB),
    "-MinFps", ([string]$MinFps)
)

if ($Recursive) {
    $argsList += "-Recursive"
}
if ($Overwrite) {
    $argsList += "-Overwrite"
}
if ($MaxDurationSec -gt 0) {
    $argsList += @("-MaxDurationSec", ([string]$MaxDurationSec))
}
if ($ExtraArgs.Count -gt 0) {
    $argsList += $ExtraArgs
}

& powershell @argsList
exit $LASTEXITCODE
