[CmdletBinding()]
param(
    [switch]$InstallMissingTools,
    [switch]$SkipNode,
    [switch]$SkipPythonPackages
)

$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath($PSScriptRoot)
$requirements = Join-Path $root "requirements.txt"

function Get-CommandPath {
    param([string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    return $null
}

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($machinePath -or $userPath) {
        $env:Path = (($machinePath, $userPath | Where-Object { $_ }) -join ";")
    }
}

function Resolve-InstalledCommand {
    param([string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command }

    # A freshly installed app (or an existing installation) may not be on the
    # current process PATH yet. Check the standard machine locations so a
    # deployment does not try to reinstall an already-present tool.
    $knownPaths = switch ($Name) {
        "node" { @("$env:ProgramFiles\nodejs\node.exe", "$env:LOCALAPPDATA\Programs\nodejs\node.exe") }
        "python" { @("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe", "$env:ProgramFiles\Python311\python.exe") }
        "git" { @("$env:ProgramFiles\Git\cmd\git.exe", "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe") }
        default { @() }
    }
    foreach ($path in $knownPaths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $dir = Split-Path -Parent $path
            if ($env:Path -notlike "*$dir*") { $env:Path = "$dir;$env:Path" }
            return Get-Command $Name -ErrorAction SilentlyContinue
        }
    }
    return $null
}

function Install-WingetPackage {
    param([string]$Id, [string]$Label)

    $winget = Get-CommandPath "winget"
    if (-not $winget) {
        throw "$Label is missing and winget is not available. Install it manually, then rerun bootstrap-new-machine.ps1."
    }
    Write-Host "Installing $Label with winget..."
    & $winget install --id $Id --exact --source winget --accept-source-agreements --accept-package-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        # winget returns a failure code when the package is already installed
        # and no upgrade is available. Re-scan before treating it as fatal.
        Refresh-ProcessPath
        $resolvedName = switch ($Id) {
            "OpenJS.NodeJS.LTS" { "node" }
            "Python.Python.3.11" { "python" }
            "Git.Git" { "git" }
        }
        if ($resolvedName -and (Resolve-InstalledCommand $resolvedName)) {
            Write-Warning "$Label is already installed; continuing."
            return
        }
        throw "Could not install $Label with winget."
    }
}

Write-Host "Checking local build environment..."
Refresh-ProcessPath
$git = Resolve-InstalledCommand "git"
$python = Resolve-InstalledCommand "python"
$node = Resolve-InstalledCommand "node"

if (-not $git) {
    if ($InstallMissingTools) { Install-WingetPackage -Id "Git.Git" -Label "Git"; Refresh-ProcessPath; $git = Resolve-InstalledCommand "git" }
    else { throw "Git is missing. Rerun with -InstallMissingTools or install Git manually." }
}
if (-not $python) {
    if ($InstallMissingTools) { Install-WingetPackage -Id "Python.Python.3.11" -Label "Python 3.11"; Refresh-ProcessPath; $python = Resolve-InstalledCommand "python" }
    else { throw "Python is missing. Rerun with -InstallMissingTools or install Python manually." }
}
if (-not $SkipNode -and -not $node) {
    if ($InstallMissingTools) { Install-WingetPackage -Id "OpenJS.NodeJS.LTS" -Label "Node.js LTS"; Refresh-ProcessPath; $node = Resolve-InstalledCommand "node" }
    else { Write-Warning "Node.js is missing. The current Python pipeline can run without it; use -InstallMissingTools to install it." }
}

if (-not $git -or -not $python) {
    throw "Required tools are still unavailable after installation. Close and reopen PowerShell, then rerun bootstrap-new-machine.ps1."
}

Write-Host "Git: $(& git --version 2>&1 | Select-Object -First 1)"
Write-Host "Python: $(& python --version 2>&1 | Select-Object -First 1)"
if ($node) { Write-Host "Node.js: $(& node --version 2>&1 | Select-Object -First 1)" }

if (-not $SkipPythonPackages) {
    if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
        throw "Python requirements file not found: $requirements"
    }
    Write-Host "Installing/verifying Python packages..."
    & python -m pip install --user --upgrade -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Python package installation failed."
    }
    & python -c "from PIL import Image; print('Pillow OK: ' + Image.__version__)"
    if ($LASTEXITCODE -ne 0) {
        throw "Pillow verification failed."
    }
    & python -c "import pytest; print('pytest OK: ' + pytest.__version__)"
    if ($LASTEXITCODE -ne 0) {
        throw "pytest verification failed."
    }
}

Write-Host "Environment initialization complete." -ForegroundColor Green
