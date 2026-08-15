[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Manifest, [string]$RouterPath, [switch]$DryRun)
$ErrorActionPreference = "Stop"
$arguments = @("-B", (Join-Path $PSScriptRoot "batch-image-generation\scripts\run_batch.py"), "--manifest", $Manifest)
if ($RouterPath) { $arguments += @("--router", $RouterPath) }
if ($DryRun) { $arguments += "--dry-run" }
& python @arguments
exit $LASTEXITCODE
