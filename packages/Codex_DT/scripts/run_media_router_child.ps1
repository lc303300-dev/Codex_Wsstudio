param(
    [Parameter(Mandatory = $true)][string]$Router,
    [Parameter(Mandatory = $true)][string]$ArgumentsJson,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"
$arguments = @(Get-Content -LiteralPath $ArgumentsJson -Raw -Encoding UTF8 | ConvertFrom-Json | ForEach-Object { [string]$_ })
$output = (& powershell -NoProfile -ExecutionPolicy Bypass -File $Router @arguments 2>&1 | Out-String)
$output | Set-Content -LiteralPath $OutputPath -Encoding UTF8
exit $LASTEXITCODE
