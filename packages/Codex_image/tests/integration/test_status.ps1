$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$TestRoot = Join-Path $ProjectRoot ".codex-image-private\validation\status-test"
if (Test-Path -LiteralPath $TestRoot) { [System.IO.Directory]::Delete($TestRoot, $true) }
$CodexHome = Join-Path $TestRoot "codex-home"
$EmptyPrivate = Join-Path $TestRoot "empty-private"
New-Item -ItemType Directory -Path $CodexHome, $EmptyPrivate -Force | Out-Null
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "register-default-media-tools.ps1") -CodexHome $CodexHome | Out-Null
$status = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "get-pipeline-setup-status.ps1") -CodexHome $CodexHome -PrivateRoot $EmptyPrivate | ConvertFrom-Json
if ($status.tools.'default-image-generation'.status -ne "unavailable") { throw "Expected image tool to be unavailable with no provider." }
if ($status.tools.'default-video-generation'.status -ne "unavailable") { throw "Expected video tool to be unavailable with no provider." }

$envFile = Join-Path $EmptyPrivate ".env"
Set-Content -LiteralPath $envFile -Value "GEMINI_API_KEY=offline-placeholder" -Encoding UTF8
$status = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "get-pipeline-setup-status.ps1") -CodexHome $CodexHome -PrivateRoot $EmptyPrivate | ConvertFrom-Json
if ($status.tools.'default-image-generation'.status -ne "degraded") { throw "Expected image tool to be degraded with one provider." }
if ($status.tools.'default-video-generation'.status -ne "unavailable") { throw "Expected video tool to remain unavailable." }
Write-Output "Status ready/degraded/unavailable tests passed."
