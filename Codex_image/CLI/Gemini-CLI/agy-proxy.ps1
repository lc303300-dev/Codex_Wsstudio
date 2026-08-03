param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $AgyArgs
)

$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$privateRoot = Join-Path $projectRoot ".codex-image-private"
$envFile = Join-Path $privateRoot ".env"
if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*([^#][^=]*)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            if ($name -in @('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY') -and $value) {
                Set-Item -Path "Env:$name" -Value $value
            }
        }
    }
}

if (-not $env:HTTP_PROXY) { $env:HTTP_PROXY = "http://127.0.0.1:7897" }
if (-not $env:HTTPS_PROXY) { $env:HTTPS_PROXY = "http://127.0.0.1:7897" }
if (-not $env:ALL_PROXY) { $env:ALL_PROXY = "socks5://127.0.0.1:7897" }

$agy = Join-Path $privateRoot "bin\gemini-cli\agy.exe"
if (-not (Test-Path -LiteralPath $agy)) { throw "agy.exe not found: $agy" }
& $agy @AgyArgs
exit $LASTEXITCODE
