[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$PrivateRoot = Join-Path $ProjectRoot ".codex-image-private"
$Findings = [System.Collections.Generic.List[string]]::new()

if (Test-Path -LiteralPath $PrivateRoot) {
    $Findings.Add("Private runtime folder still exists: $PrivateRoot")
}

$legacyPrivatePaths = @(
    "CLI\.env",
    "CLI\Gemini-CLI\agy.exe",
    "CLI\Seedance-CLI\dreamina.exe",
    "outputs",
    "logs",
    "validation"
)
foreach ($relativePath in $legacyPrivatePaths) {
    $candidate = Join-Path $ProjectRoot $relativePath
    if (Test-Path -LiteralPath $candidate) {
        $Findings.Add("Legacy private path still exists: $candidate")
    }
}

Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "CLI") -Directory -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "__pycache__" } |
    ForEach-Object { $Findings.Add("Python cache still exists: $($_.FullName)") }

if ($Findings.Count) {
    Write-Host "The project is not ready to share:" -ForegroundColor Yellow
    $Findings | ForEach-Object { Write-Host "- $_" }
    Write-Host "Delete .codex-image-private and resolve any listed legacy paths, then run this check again."
    exit 1
}

Write-Host "Share-ready check passed. No known project-local credentials, downloaded CLI binaries, generated outputs, logs, validation artifacts, or Python caches were found."
Write-Host "Provider login sessions stored in Windows or user-profile locations are outside this project and are not included in the shared folder."
