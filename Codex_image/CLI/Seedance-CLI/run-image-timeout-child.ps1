param(
    [Parameter(Mandatory = $true)]
    [string]$Dreamina,

    [Parameter(Mandatory = $true)]
    [string]$ArgumentsJson
)

$ErrorActionPreference = "Stop"
$dreaminaArgs = @(Get-Content -Raw -LiteralPath $ArgumentsJson | ConvertFrom-Json)
& $Dreamina @dreaminaArgs
exit $LASTEXITCODE
