$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$PrivateRoot = Join-Path $ProjectRoot ".codex-image-private\validation\registration-test"
if (Test-Path -LiteralPath $PrivateRoot) { [System.IO.Directory]::Delete($PrivateRoot, $true) }
New-Item -ItemType Directory -Path (Join-Path $PrivateRoot "skills\unmanaged-skill") -Force | Out-Null
Set-Content -LiteralPath (Join-Path $PrivateRoot "skills\unmanaged-skill\SKILL.md") -Value "unmanaged" -Encoding UTF8
$legacy = [ordered]@{
    source_root = $ProjectRoot
    first_run_choice_completed = $true
    registered_pipelines = @("gemini-api", "seedance-cli")
    selected_pipelines = @("gemini-api", "seedance-cli")
    setup_completed_pipelines = @("gemini-api", "seedance-cli")
    updated_at = (Get-Date).ToString("o")
}
$legacy | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PrivateRoot "codex-image-registration-state.json") -Encoding UTF8
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "register-default-media-tools.ps1") -CodexHome $PrivateRoot

$skills = @(Get-ChildItem -LiteralPath (Join-Path $PrivateRoot "skills") -Directory | Select-Object -ExpandProperty Name | Sort-Object)
$expected = @("default-image-generation", "default-video-generation", "unmanaged-skill")
if (($skills -join "|") -ne ($expected -join "|")) { throw "Unexpected isolated skill list: $($skills -join ', ')" }
if (Test-Path -LiteralPath (Join-Path $PrivateRoot "plugins\codex-media-plugin\skills")) {
    throw "Default media skills should be installed globally, not under the plugin."
}
$state = Get-Content -LiteralPath (Join-Path $PrivateRoot "codex-image-registration-state.json") -Raw -Encoding UTF8 | ConvertFrom-Json
if ($state.schema_version -ne 2) { throw "State did not migrate to schema v2." }
$backups = @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot ".codex-image-private\validation\state-migration") -File -Filter "state-v1-*.json")
if (-not $backups.Count) { throw "State migration backup was not created." }
Write-Output "Registration migration tests passed."
