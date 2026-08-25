[CmdletBinding()]
param([string]$CodexHome, [switch]$CheckLogin, [string]$PrivateRoot)

$ErrorActionPreference = "Stop"
if (-not $CodexHome) { $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" } }
$ProjectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
if (-not $PrivateRoot) { $PrivateRoot = Join-Path $ProjectRoot ".codex-image-private" }
$ConfigPath = Join-Path $ProjectRoot "config\media-router.defaults.json"
$config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$configured = @{}
$envFile = Join-Path $PrivateRoot ".env"
if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$') { $configured[$matches[1]] = $true }
    }
}
function Test-Key([string]$Name) { return [bool]$configured[$Name] -or -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name)) }

$dreamina = Join-Path $PrivateRoot "bin\seedance-cli\dreamina.exe"
$dreaminaReady = Test-Path -LiteralPath $dreamina
if ($CheckLogin -and $dreaminaReady) {
    try { $value = & $dreamina user_credit 2>&1; $dreaminaReady = $LASTEXITCODE -eq 0 -and (($value -join "`n") -match 'total_credit') } catch { $dreaminaReady = $false }
}

$providerReady = [ordered]@{
    "comfly-gemini-lite" = (Test-Key "COMFLY_API_KEY")
    "comfly-gpt-image-2" = (Test-Key "COMFLY_API_KEY")
    "dreamina-image" = $dreaminaReady
    "dreamina-video" = $dreaminaReady
}
$providers = [ordered]@{}
foreach ($name in $providerReady.Keys) {
    $enabled = if ($null -eq $config.providers.$name.enabled) { $true } else { [bool]$config.providers.$name.enabled }
    $providers[$name] = [ordered]@{
        enabled = $enabled
        ready = ($enabled -and [bool]$providerReady[$name])
        model = [string]$config.providers.$name.model
        max_concurrency = [int]$config.providers.$name.max_concurrency
        capacity_key = [string]$config.providers.$name.capacity_key
    }
    if (-not $providers[$name].capacity_key) { $providers[$name].capacity_key = $name }
}

$pluginRegistered = Test-Path -LiteralPath (Join-Path $CodexHome "plugins\codex-media-plugin\.codex-plugin\plugin.json")
$imageSkill = Test-Path -LiteralPath (Join-Path $CodexHome "skills\default-image-generation\SKILL.md")
$videoSkill = Test-Path -LiteralPath (Join-Path $CodexHome "skills\default-video-generation\SKILL.md")
$enabledImageProviders = @($providerReady.Keys | Where-Object { $_ -ne "dreamina-video" -and $providers[$_].enabled })
$imageCount = @($enabledImageProviders | Where-Object { $providers[$_].ready }).Count
$videoEnabled = [bool]$providers["dreamina-video"].enabled
$videoCount = if ($videoEnabled -and $providers["dreamina-video"].ready) { 1 } else { 0 }
function ToolStatus([bool]$Registered, [int]$ReadyCount, [int]$Expected) {
    if (-not $Registered -or $Expected -eq 0 -or $ReadyCount -eq 0) { return "unavailable" }
    if ($ReadyCount -lt $Expected) { return "degraded" }
    return "ready"
}
$tools = [ordered]@{
    "default-image-generation" = [ordered]@{ registered=($pluginRegistered -and $imageSkill); status=(ToolStatus ($pluginRegistered -and $imageSkill) $imageCount $enabledImageProviders.Count) }
    "default-video-generation" = [ordered]@{ registered=($pluginRegistered -and $videoSkill); status=(ToolStatus ($pluginRegistered -and $videoSkill) $videoCount ([int]$videoEnabled)) }
}
[ordered]@{ tools=$tools; providers=$providers } | ConvertTo-Json -Depth 8
