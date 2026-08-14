[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd("\")
$PrivateRoot = Join-Path $ProjectRoot ".codex-image-private"

function Assert-ProjectPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($ProjectRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the project root: $fullPath"
    }
    return $fullPath
}

function Move-LegacyItem {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $Source = Assert-ProjectPath $Source
    $Destination = Assert-ProjectPath $Destination
    if (-not (Test-Path -LiteralPath $Source)) { return }
    if (Test-Path -LiteralPath $Destination) {
        throw "Migration destination already exists: $Destination"
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
    Move-Item -LiteralPath $Source -Destination $Destination
    Write-Host "Moved: $Source -> $Destination"
}

New-Item -ItemType Directory -Path $PrivateRoot -Force | Out-Null

Move-LegacyItem (Join-Path $ProjectRoot "CLI\.env") (Join-Path $PrivateRoot ".env")
Move-LegacyItem (Join-Path $ProjectRoot "CLI\Seedance-CLI\dreamina.exe") (Join-Path $PrivateRoot "bin\seedance-cli\dreamina.exe")
Move-LegacyItem (Join-Path $ProjectRoot "outputs") (Join-Path $PrivateRoot "outputs")
Move-LegacyItem (Join-Path $ProjectRoot "logs") (Join-Path $PrivateRoot "logs")
Move-LegacyItem (Join-Path $ProjectRoot "validation") (Join-Path $PrivateRoot "validation")

$cacheRoot = Join-Path $PrivateRoot "cache\python"
$cacheIndex = 0
Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "CLI") -Directory -Recurse -Force |
    Where-Object { $_.Name -eq "__pycache__" } |
    ForEach-Object {
        $cacheIndex++
        Move-LegacyItem $_.FullName (Join-Path $cacheRoot $cacheIndex)
    }

Write-Host "Migration complete. Delete this one folder before sharing the project: $PrivateRoot"
