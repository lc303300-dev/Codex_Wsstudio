[CmdletBinding()]
param([string]$RepositoryRoot)

$ErrorActionPreference = "Stop"
$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptRoot)) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Join-Path $scriptRoot "..\.."
}
$RepositoryRoot = [System.IO.Path]::GetFullPath($RepositoryRoot)

$requiredDirectories = @("config", "docs", "packages", "scripts")
$requiredFiles = @("AGENTS.md", "LICENSE", "README.md", "requirements.txt", "start-task.ps1", "new-machine-deploy.ps1")
$allowedRootFiles = @(
    ".env.example",
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "LICENSE",
    "README.md",
    "pytest.ini",
    "requirements.txt",
    "start-task.ps1",
    "new-machine-deploy.ps1"
)
$allowedRootDirectories = @(".git", ".github", ".vscode", "config", "docs", "packages", "scripts")
$requiredPackagePaths = @(
    "packages\Codex_Batch_Image",
    "packages\Codex_Batch_Image\register-global-skill.ps1",
    "packages\Codex_Batch_Image\run-batch-image-generation.ps1",
    "packages\Codex_Batch_Image\batch-image-generation\SKILL.md"
)

$errors = [System.Collections.Generic.List[string]]::new()
foreach ($directory in $requiredDirectories) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot $directory) -PathType Container)) {
        $errors.Add("Missing required root directory: $directory/")
    }
}
foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot $file) -PathType Leaf)) {
        $errors.Add("Missing required root file: $file")
    }
}
foreach ($relativePath in $requiredPackagePaths) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot $relativePath))) {
        $errors.Add("Missing required package path: $relativePath")
    }
}
foreach ($item in Get-ChildItem -LiteralPath $RepositoryRoot -Force) {
    if ($item.PSIsContainer) {
        if ($item.Name -notin $allowedRootDirectories) {
            $errors.Add("Unexpected root directory: $($item.Name)/. Put project code in packages/, documentation in docs/, configuration in config/, or automation in scripts/.")
        }
    }
    elseif ($item.Name -notin $allowedRootFiles) {
        $errors.Add("Unexpected root file: $($item.Name). Keep only repository metadata and stable entry points at the root.")
    }
}

if ($errors.Count -gt 0) {
    Write-Host "Project structure validation failed:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  - $_" }
    exit 1
}

Write-Host "Project structure validation passed."
