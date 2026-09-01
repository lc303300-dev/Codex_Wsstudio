param(
    [Parameter(Mandatory = $true)][string]$Router,
    [Parameter(Mandatory = $true)][string]$ArgumentsJson,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"
$parsed = Get-Content -LiteralPath $ArgumentsJson -Raw -Encoding UTF8 | ConvertFrom-Json
$arguments = @(
    foreach ($item in @($parsed)) {
        if ($null -ne $item -and $item.PSObject.Properties['value']) { [string]$item.value }
        else { [string]$item }
    }
)
$output = @(& $Router @arguments 2>&1)
$invocationSucceeded = $?
$lastExitVariable = Get-Variable -Name LASTEXITCODE -ErrorAction SilentlyContinue
$exitCode = if ($null -ne $lastExitVariable) { [int]$lastExitVariable.Value } elseif ($invocationSucceeded) { 0 } else { 1 }
$combined = $output | Out-String
[System.IO.File]::WriteAllText($OutputPath, $combined, [System.Text.UTF8Encoding]::new($false))
exit $exitCode
