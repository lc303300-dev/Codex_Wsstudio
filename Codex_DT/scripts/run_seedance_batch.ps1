param(
    [string]$ManifestDirectory = "manifests",
    [string]$OutputsDirectory = "outputs",
    [string]$PrivateRuntimeDirectory = ".codex-image-private/batches",
    [string]$SeedanceCli,
    [string]$Batch,
    [switch]$SkipCreditCheck,
    [switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$localConfigPath = Join-Path $root "config/pipeline.local.json"
$configPath = Join-Path $root "config/pipeline.json"
if ([string]::IsNullOrWhiteSpace($SeedanceCli)) {
    foreach ($envName in @("SEEDANCE_CLI", "SEEDANCE_CLI_PATH", "DREAMINA_CLI")) {
        $envValue = [Environment]::GetEnvironmentVariable($envName)
        if (-not [string]::IsNullOrWhiteSpace($envValue)) {
            $SeedanceCli = $envValue
            break
        }
    }
}
if ([string]::IsNullOrWhiteSpace($SeedanceCli)) {
    if (Test-Path -LiteralPath $localConfigPath) {
        $localConfig = Get-Content -LiteralPath $localConfigPath -Encoding UTF8 -Raw | ConvertFrom-Json
        $SeedanceCli = [string]$localConfig.paths.seedance_cli
    }
    elseif (Test-Path -LiteralPath $configPath) {
        $config = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw | ConvertFrom-Json
        $SeedanceCli = [string]$config.paths.seedance_cli
    }
}
if (-not [string]::IsNullOrWhiteSpace($Batch)) {
    $ManifestDirectory = Join-Path $ManifestDirectory $Batch
    $OutputsDirectory = Join-Path $OutputsDirectory $Batch
    $PrivateRuntimeDirectory = Join-Path $PrivateRuntimeDirectory $Batch
}
$manifestRoot = Join-Path $root $ManifestDirectory
$outputsRoot = Join-Path $root $OutputsDirectory
$runtimeRoot = Join-Path $root $PrivateRuntimeDirectory
$logsRoot = Join-Path $runtimeRoot "dreamina-logs"

if ([string]::IsNullOrWhiteSpace($SeedanceCli)) {
    throw "Seedance CLI wrapper is not configured. Run scripts/deploy_project.ps1 first."
}
if (-not (Test-Path -LiteralPath $SeedanceCli)) {
    throw "Seedance CLI wrapper not found: $SeedanceCli"
}

New-Item -ItemType Directory -Force -Path $outputsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $logsRoot | Out-Null

if (-not $SkipCreditCheck) {
    Write-Host "Checking Dreamina user credit..."
    powershell -NoProfile -ExecutionPolicy Bypass -File $SeedanceCli user_credit
}

$manifestFiles = Get-ChildItem -LiteralPath $manifestRoot -Filter *.json -File
$confirmed = @()
foreach ($file in $manifestFiles) {
    $manifest = Get-Content -LiteralPath $file.FullName -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.prompt.status -eq "confirmed") {
        $confirmed += [pscustomobject]@{
            File = $file
            Manifest = $manifest
        }
    }
}

if ($confirmed.Count -eq 0) {
    Write-Host "No confirmed manifest found. Set prompt.status to confirmed after user approval."
    exit 0
}

if (-not $Yes) {
    Write-Host "Generation consumes Dreamina credits. Re-run with -Yes after confirming you want to submit $($confirmed.Count) item(s)."
    exit 0
}

$tasksPath = Join-Path $runtimeRoot "tasks.jsonl"

foreach ($item in $confirmed) {
    $manifest = $item.Manifest
    $sourceImage = [string]$manifest.source_image
    if (-not [IO.Path]::IsPathRooted($sourceImage)) {
        $sourceImage = Join-Path $root $sourceImage
    }
    $promptFile = [string]$manifest.prompt.file
    if (-not [IO.Path]::IsPathRooted($promptFile)) {
        $promptFile = Join-Path $root $promptFile
    }
    if (-not (Test-Path -LiteralPath $sourceImage)) {
        throw "Source image missing for $($manifest.id): $sourceImage"
    }
    if (-not (Test-Path -LiteralPath $promptFile)) {
        throw "Prompt file missing for $($manifest.id): $promptFile"
    }

    $prompt = Get-Content -LiteralPath $promptFile -Encoding UTF8 -Raw
    $atSign = [string][char]64
    $zhImageLabel = ([string][char]0x56FE) + ([string][char]0x7247)
    if ($prompt.Contains($atSign + "Image") -or $prompt.Contains($atSign + $zhImageLabel)) {
        throw ("Prompt for {0} contains a Web UI mention label. Dreamina CLI multimodal2video uses bare labels such as 图片1 plus ordered --image arguments." -f $manifest.id)
    }
    if (-not $prompt.Contains($zhImageLabel + "1")) {
        throw ("Prompt for {0} must refer to the first ordered --image upload as 图片1 before paid generation." -f $manifest.id)
    }
    $assetManifest = $manifest.mqrox_compile.asset_manifest
    $imageAssets = @($assetManifest.assets | Where-Object { $_.modality -eq "image" } | Sort-Object { [int]$_.index })
    if ($imageAssets.Count -lt 1) {
        throw "Manifest for $($manifest.id) must contain at least one image asset for Dreamina CLI multimodal2video."
    }
    for ($assetIndex = 0; $assetIndex -lt $imageAssets.Count; $assetIndex++) {
        $expectedIndex = $assetIndex + 1
        $asset = $imageAssets[$assetIndex]
        $assetTag = [string]$asset.tag
        if ([int]$asset.index -ne $expectedIndex -or $assetTag -ne ($zhImageLabel + [string]$expectedIndex)) {
            throw ("Manifest image asset order for {0} must use contiguous tags 图片1, 图片2, ... matching --image upload order." -f $manifest.id)
        }
        if ($assetTag.Contains($atSign + "Image") -or $assetTag.Contains($atSign + $zhImageLabel)) {
            throw ("Manifest image asset for {0} contains a Web UI mention tag. Use bare labels such as 图片1." -f $manifest.id)
        }
    }
    if ($null -eq $manifest.mqrox_compile.duration) {
        throw "Duration missing for $($manifest.id). Ask the user for a duration before generation."
    }
    $duration = [int]$manifest.mqrox_compile.duration
    if ($duration -lt 4 -or $duration -gt 15) {
        throw "Duration for $($manifest.id) must be 4 through 15 seconds; got $duration."
    }
    if ($null -eq $manifest.mqrox_compile.ratio -or [string]::IsNullOrWhiteSpace([string]$manifest.mqrox_compile.ratio)) {
        throw "Ratio missing for $($manifest.id). Ask the user for a ratio before generation."
    }
    $ratio = [string]$manifest.mqrox_compile.ratio
    $supportedRatios = @("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
    if ($supportedRatios -notcontains $ratio) {
        throw "Ratio for $($manifest.id) must be one of $($supportedRatios -join ', '); got $ratio."
    }
    $resolution = [string]$manifest.mqrox_compile.resolution
    if ([string]::IsNullOrWhiteSpace($resolution)) {
        $resolution = "720p"
    }
    $modelVersion = "seedance2.0fast_vip"
    if ($manifest.mqrox_compile.PSObject.Properties.Name -contains "model_version") {
        $modelVersion = [string]$manifest.mqrox_compile.model_version
    }
    $poll = 60

    Write-Host "Submitting $($manifest.id)..."
    $logPath = Join-Path $logsRoot ("{0}.submit.log" -f $manifest.id)
    $commandArgs = @("multimodal2video")
    foreach ($asset in $imageAssets) {
        $assetSource = [string]$asset.source
        if ([string]::IsNullOrWhiteSpace($assetSource)) {
            $assetSource = $sourceImage
        } elseif (-not [IO.Path]::IsPathRooted($assetSource)) {
            $assetSource = Join-Path $root $assetSource
        }
        if (-not (Test-Path -LiteralPath $assetSource)) {
            throw "Image asset missing for $($manifest.id): $assetSource"
        }
        $commandArgs += @("--image", $assetSource)
    }
    $commandArgs += @(
        "--prompt", $prompt,
        "--duration", [string]$duration,
        "--ratio", $ratio,
        "--video_resolution", $resolution,
        "--model_version", $modelVersion,
        "--poll", [string]$poll
    )
    $output = powershell -NoProfile -ExecutionPolicy Bypass -File $SeedanceCli @commandArgs 2>&1
    $output | Set-Content -LiteralPath $logPath -Encoding UTF8

    $submitId = $null
    $joined = ($output -join "`n")
    if ($joined -match 'submit_id[''":=\s]+([0-9a-fA-F-]{12,})') {
        $submitId = $Matches[1]
    }

    $record = [ordered]@{
        id = $manifest.id
        source_image = $sourceImage
        prompt_file = $promptFile
        submit_id = $submitId
        log = $logPath
        submitted_at = (Get-Date).ToString("o")
    }
    ($record | ConvertTo-Json -Compress -Depth 6) | Add-Content -LiteralPath $tasksPath -Encoding UTF8

    $manifest.generation.status = "submitted"
    $manifest.generation.submit_id = $submitId
    $manifest.generation.output_dir = $outputsRoot
    $manifest.generation.error = $null
    $manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $item.File.FullName -Encoding UTF8
}

Write-Host "Submitted $($confirmed.Count) confirmed item(s)."
Write-Host "Task log: $tasksPath"
