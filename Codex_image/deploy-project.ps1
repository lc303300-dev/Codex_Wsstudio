[CmdletBinding()]
param(
    [string]$CodexHome,
    [switch]$SkipLoginCheck
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
if (-not $CodexHome) {
    $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
}
$CodexHome = [System.IO.Path]::GetFullPath($CodexHome)
$ToolsRoot = Join-Path $CodexHome "tools"
$PreviewSource = Join-Path $ProjectRoot "tools\Convert-CodexImagePreview.ps1"
$PreviewDestination = Join-Path $ToolsRoot "Convert-CodexImagePreview.ps1"

Write-Host "Deploying Codex_image from: $ProjectRoot"
Write-Host "Codex home: $CodexHome"

if (-not (Test-Path -LiteralPath $PreviewSource -PathType Leaf)) {
    throw "Bundled preview converter is missing: $PreviewSource"
}
New-Item -ItemType Directory -Path $ToolsRoot -Force | Out-Null
Copy-Item -LiteralPath $PreviewSource -Destination $PreviewDestination -Force
Write-Host "Installed preview converter: $PreviewDestination"

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "register-default-media-tools.ps1") -CodexHome $CodexHome
if ($LASTEXITCODE -ne 0) { throw "Default media tool registration failed." }

$statusArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $ProjectRoot "get-pipeline-setup-status.ps1"),
    "-CodexHome", $CodexHome
)
if (-not $SkipLoginCheck) { $statusArgs += "-CheckLogin" }

$statusJson = & powershell.exe @statusArgs
if ($LASTEXITCODE -ne 0) { throw "Pipeline status check failed." }
$status = $statusJson | ConvertFrom-Json
$readyTools = @($status.tools.PSObject.Properties | Where-Object {
    $_.Name -in @("default-image-generation", "default-video-generation") -and $_.Value.status -eq "ready"
} | ForEach-Object { $_.Name })

if ($readyTools.Count) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "complete-pipeline-setup.ps1") -Tool ($readyTools -join ",") -CodexHome $CodexHome
    if ($LASTEXITCODE -ne 0) { throw "Marking ready tools complete failed." }
}

Write-Host ""
Write-Host "Deployment status:"
$statusJson | Write-Output

$missingTools = @("default-image-generation", "default-video-generation") | Where-Object { $_ -notin $readyTools }
if ($missingTools.Count) {
    Write-Host ""
    Write-Host "Deployment finished, but these tools are not ready yet: $($missingTools -join ', ')" -ForegroundColor Yellow
    Write-Host "Configure missing API keys with configure-api-key.ps1 or login/install CLI providers with install-cli-pipeline.ps1, then run this script again."
} else {
    Write-Host ""
    Write-Host "Deployment complete. The default image and video tools are registered and ready."
    Write-Host "Restart Codex or start a new task if newly installed plugin tools are not visible immediately."
}
