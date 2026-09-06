param(
    [string]$ManifestDirectory = "manifests",
    [string]$OutputsDirectory = "outputs",
    [string]$PrivateRuntimeDirectory = ".codex-image-private/batches",
    [string]$SeedanceCli,
    [string]$MediaRouter,
    [string]$Batch,
    [switch]$SkipCreditCheck,
    [switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$localConfigPath = Join-Path $root "config/pipeline.local.json"
$configPath = Join-Path $root "config/pipeline.json"
if ([string]::IsNullOrWhiteSpace($MediaRouter)) {
    foreach ($candidate in @(
        (Join-Path $root "..\Codex_image\CLI\Media-Router\run.ps1"),
        (Join-Path $root "..\Codex_image\CLI\media-router.cmd")
    )) {
        if (Test-Path -LiteralPath $candidate) {
            $MediaRouter = [IO.Path]::GetFullPath($candidate)
            break
        }
    }
}
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

if ([string]::IsNullOrWhiteSpace($MediaRouter) -or -not (Test-Path -LiteralPath $MediaRouter)) {
    throw "Unified Media Router is not configured. Codex_DT may not submit directly to Seedance CLI."
}

New-Item -ItemType Directory -Force -Path $outputsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $logsRoot | Out-Null

if (-not $SkipCreditCheck) { Write-Host "Media Router will check Dreamina credit before each paid submit." }

$manifestFiles = Get-ChildItem -LiteralPath $manifestRoot -Filter *.json -File
$tasksPath = Join-Path $runtimeRoot "tasks.jsonl"
$confirmed = @()
foreach ($file in $manifestFiles) {
    $manifest = Get-Content -LiteralPath $file.FullName -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.prompt.status -eq "confirmed" -and $manifest.generation.status -notin @("submitted", "downloaded", "success")) {
        $confirmed += [pscustomobject]@{
            File = $file
            Manifest = $manifest
        }
    }
}

if ($confirmed.Count -eq 0) {
    if (Test-Path -LiteralPath $tasksPath) {
        $existingTasks = @(
            Get-Content -LiteralPath $tasksPath -Encoding UTF8 |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                ForEach-Object { $_ | ConvertFrom-Json }
        )
        $legacyPending = @($existingTasks | Where-Object {
            [string]::IsNullOrWhiteSpace([string]$_.output_path) -or
            -not (Test-Path -LiteralPath ([string]$_.output_path))
        })
        if ($legacyPending.Count -eq 0) {
            Write-Host "No new confirmed item needs submission; all recorded videos are already downloaded."
            exit 0
        }
        Write-Host "No new confirmed item needs submission; resuming legacy polling/download for existing submit IDs."
        $waitScript = Join-Path $PSScriptRoot "wait_seedance_batch.py"
        $waitArgs = @("--batch", $Batch)
        if ($SeedanceCli) { $waitArgs += @("--seedance-cli", $SeedanceCli) }
        & python $waitScript @waitArgs
        if ($LASTEXITCODE -ne 0) { throw "Polling/download phase failed for batch $Batch." }
        exit 0
    }
    Write-Host "No confirmed manifest found and no submitted task log is available."
    exit 0
}

if (-not $Yes) {
    Write-Host "Generation consumes Dreamina credits. Re-run with -Yes after confirming you want to submit $($confirmed.Count) item(s)."
    exit 0
}

$pending = @()

foreach ($item in $confirmed) {
    $manifest = $item.Manifest
    $policyOutput = @(& python (Join-Path $PSScriptRoot "model_policy.py") --manifest $item.File.FullName 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Model policy validation failed for $($manifest.id). $($policyOutput -join ' ')"
    }
    $policyJson = $policyOutput -join "`n"
    $modelPolicy = $policyJson | ConvertFrom-Json
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

    $prompt = [System.IO.File]::ReadAllText($promptFile, [System.Text.UTF8Encoding]::new($false))
    $promptHash = ([BitConverter]::ToString(([Security.Cryptography.SHA256]::Create()).ComputeHash([Text.Encoding]::UTF8.GetBytes($prompt.Trim()))).Replace('-', '').ToLowerInvariant())
    $confirmedHash = [string]$manifest.prompt.confirmed_sha256
    if ([string]::IsNullOrWhiteSpace($confirmedHash) -or $confirmedHash -ne $promptHash) {
        throw "Prompt for $($manifest.id) changed after review or has no confirmed hash. Rebuild review and confirm the exact prompt before submission."
    }
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
    if ($null -eq $manifest.mqrox_compile.ratio -or [string]::IsNullOrWhiteSpace([string]$manifest.mqrox_compile.ratio)) {
        throw "Ratio missing for $($manifest.id). Ask the user for a ratio before generation."
    }
    $ratio = [string]$manifest.mqrox_compile.ratio
    $resolution = [string]$modelPolicy.resolution
    $modelVersion = [string]$modelPolicy.model_version
    Write-Host "Queueing $($manifest.id)..."
    $logPath = Join-Path $logsRoot ("{0}.submit.log" -f $manifest.id)
    $commandArgs = @("generate_video")
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
        "--video-prompt-sha256", $promptHash,
        "--video-duration", [string]$duration,
        "--video-ratio", $ratio,
        "--video-resolution", $resolution,
        "--video-model", $modelVersion,
        "--video-confirmation-model", $modelVersion,
        "--video-confirmation-resolution", $resolution,
        "--video-confirmation-duration", [string]$duration,
        # This entrypoint is a true two-phase batch: workers only submit here.
        # The shared wait_seedance_batch.py phase polls/downloads the whole batch
        # after every confirmed item has received a submit_id.
        "--video-execution-mode", "production_submit_only"
    )
    if ($modelVersion -ne "seedance2.5") {
        $commandArgs += @("--video-model-selection-source", "user_explicit")
    }
    $pending += [pscustomobject]@{
        Item = $item
        Manifest = $manifest
        SourceImage = $sourceImage
        PromptFile = $promptFile
        LogPath = $logPath
        CommandArgs = $commandArgs
    }
}

if ($pending.Count -gt 0) {
    # Submit the whole batch first. A slot is released as soon as Dreamina
    # returns submit_id, never after rendering/download completes.
    $queueLimit = 6
    $nextIndex = 0
    $active = @()
    $childScript = Join-Path $PSScriptRoot "run_media_router_child.ps1"
    while ($nextIndex -lt $pending.Count -or $active.Count -gt 0) {
        while ($nextIndex -lt $pending.Count -and $active.Count -lt $queueLimit) {
            $task = $pending[$nextIndex]
            $nextIndex++
            $argumentsPath = Join-Path $runtimeRoot ("{0}.args.json" -f $task.Manifest.id)
            $resultPath = Join-Path $runtimeRoot ("{0}.result.txt" -f $task.Manifest.id)
            ConvertTo-Json -InputObject @($task.CommandArgs) -Compress | Set-Content -LiteralPath $argumentsPath -Encoding UTF8
            Write-Host "Submitting $($task.Manifest.id) (in flight: $($active.Count + 1)/$queueLimit)..."
            $childArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $childScript, "-Router", $MediaRouter, "-ArgumentsJson", $argumentsPath, "-OutputPath", $resultPath)
            $process = Start-Process -FilePath "powershell.exe" -ArgumentList $childArgs -WindowStyle Hidden -PassThru
            $active += [pscustomobject]@{ Process = $process; Task = $task; ResultPath = $resultPath; ArgumentsPath = $argumentsPath }
        }

        $finished = @($active | Where-Object { $_.Process.HasExited })
        if ($finished.Count -eq 0) {
            Start-Sleep -Milliseconds 250
            continue
        }

        foreach ($entry in $finished) {
            $task = $entry.Task
            $output = @()
            if (Test-Path -LiteralPath $entry.ResultPath) {
                $output = @(Get-Content -LiteralPath $entry.ResultPath -Encoding UTF8)
            }
            $output | Set-Content -LiteralPath $task.LogPath -Encoding UTF8
            $joined = ($output -join "`n")
            $active = @($active | Where-Object { $_ -ne $entry })
            if ($entry.Process.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($joined)) {
                throw "Media Router process failed for $($task.Manifest.id). See $($task.LogPath)"
            }
            try { $routerResult = $joined | ConvertFrom-Json }
            catch { throw "Media Router returned invalid JSON for $($task.Manifest.id). See $($task.LogPath)" }
            if ([string]$routerResult.status -ne "submitted") {
                throw "Media Router did not submit $($task.Manifest.id): $([string]$routerResult.safe_reason)"
            }
            $submitId = [string]$routerResult.submit_id
            if ([string]::IsNullOrWhiteSpace($submitId)) { throw "Media Router returned submitted without submit_id for $($task.Manifest.id)." }

            $record = [ordered]@{
                id = $task.Manifest.id
                source_image = $task.SourceImage
                prompt_file = $task.PromptFile
                submit_id = $submitId
                log = $task.LogPath
                submitted_at = (Get-Date).ToString("o")
            }
            ($record | ConvertTo-Json -Compress -Depth 6) | Add-Content -LiteralPath $tasksPath -Encoding UTF8
            $task.Manifest.generation.status = "submitted"
            $task.Manifest.generation.submit_id = $submitId
            $task.Manifest.generation.error = $null
            $task.Manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $task.Item.File.FullName -Encoding UTF8
            Write-Host "Submitted $($task.Manifest.id): $submitId"
            Remove-Item -LiteralPath $entry.ResultPath, $entry.ArgumentsPath -Force -ErrorAction SilentlyContinue
        }
    }
}

if (Test-Path -LiteralPath $tasksPath) {
    # Second phase: poll and download all submitted tasks as one batch.
    $waitScript = Join-Path $PSScriptRoot "wait_seedance_batch.py"
    $waitArgs = @("--batch", $Batch)
    if ($SeedanceCli) { $waitArgs += @("--seedance-cli", $SeedanceCli) }
    & python $waitScript @waitArgs
    if ($LASTEXITCODE -ne 0) { throw "Polling/download phase failed for batch $Batch." }
}

Write-Host "Completed $($confirmed.Count) confirmed item(s) through the two-phase batch pipeline."
Write-Host "Task log: $tasksPath"
