[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][Alias("Pipeline")][string[]]$Tool,
    [string]$CodexHome
)

$ErrorActionPreference = "Stop"
$known = @("default-image-generation", "default-video-generation")
$selected = @($Tool | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Unique)
if (-not $CodexHome) { $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" } }
foreach ($name in $selected) { if ($name -notin $known) { throw "Unknown tool '$name'." } }
$status = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "get-pipeline-setup-status.ps1") -CodexHome $CodexHome -CheckLogin | ConvertFrom-Json
foreach ($name in $selected) {
    if ($status.tools.$name.registered -ne $true -or $status.tools.$name.status -eq "unavailable") { throw "Cannot mark '$name' complete: live status is unavailable." }
}
$statePath = Join-Path $CodexHome "codex-image-registration-state.json"
$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
$state | Add-Member -NotePropertyName schema_version -NotePropertyValue 2 -Force
$state | Add-Member -NotePropertyName setup_completed_tools -NotePropertyValue @(@($state.setup_completed_tools) + $selected | Select-Object -Unique) -Force
$state | Add-Member -NotePropertyName provider_readiness -NotePropertyValue $status.providers -Force
$state | Add-Member -NotePropertyName updated_at -NotePropertyValue (Get-Date).ToString("o") -Force
$temporary = "$statePath.tmp"
$state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $temporary -Encoding UTF8
Move-Item -LiteralPath $temporary -Destination $statePath -Force
Write-Host "Setup marked complete for: $($selected -join ', ')"
