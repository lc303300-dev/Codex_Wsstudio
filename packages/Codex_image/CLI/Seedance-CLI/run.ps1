$ErrorActionPreference = "Stop"
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$dreamina = Join-Path $projectRoot ".codex-image-private\bin\seedance-cli\dreamina.exe"
if (-not (Test-Path -LiteralPath $dreamina)) { throw "dreamina.exe not found: $dreamina" }
. (Join-Path $PSScriptRoot "resolve-arguments.ps1")
$dreaminaArgs = @(Resolve-DreaminaArguments -InputArguments $args)
$imageCommands = @("text2image", "image2image", "image_upscale")
if ($dreaminaArgs.Count -gt 0 -and $dreaminaArgs[0] -in $imageCommands) {
    $timeoutSeconds = 180
    $runId = [guid]::NewGuid().ToString("N")
    $timeoutRoot = Join-Path $projectRoot ".codex-image-private\logs\seedance-cli\timeouts"
    New-Item -ItemType Directory -Force -Path $timeoutRoot | Out-Null
    $argumentsJson = Join-Path $timeoutRoot "$runId.args.json"
    $dreaminaArgs | ConvertTo-Json -Compress | Set-Content -LiteralPath $argumentsJson -Encoding UTF8
    $childScript = Join-Path $PSScriptRoot "run-image-timeout-child.ps1"
    $childArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $childScript,
        "-Dreamina",
        $dreamina,
        "-ArgumentsJson",
        $argumentsJson
    )
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $childArgs -NoNewWindow -PassThru -Wait:$false
    if (-not $process.WaitForExit($timeoutSeconds * 1000)) {
        try {
            & taskkill.exe /PID $process.Id /T /F | Out-Null
        } catch {
            Write-Warning "Failed to stop timed out Dreamina image process $($process.Id): $_"
        } finally {
            Remove-Item -LiteralPath $argumentsJson -Force -ErrorAction SilentlyContinue
        }
        throw "Dreamina image command '$($dreaminaArgs[0])' did not finish within $timeoutSeconds seconds."
    } else {
        Remove-Item -LiteralPath $argumentsJson -Force -ErrorAction SilentlyContinue
    }
    exit $process.ExitCode
}
& $dreamina @dreaminaArgs
exit $LASTEXITCODE
