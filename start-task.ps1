[CmdletBinding()]
param(
    [string]$RepositoryRoot = $PSScriptRoot,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = [System.IO.Path]::GetFullPath($RepositoryRoot)

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or is not available in PATH."
}

$previousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$gitRoot = (& git -C $RepositoryRoot rev-parse --show-toplevel 2>$null)
$gitRootExit = $LASTEXITCODE
$ErrorActionPreference = $previousErrorPreference
if ($gitRootExit -ne 0 -or -not $gitRoot) {
    Write-Warning "Update check skipped: $RepositoryRoot is not a Git repository yet."
    Write-Host "Initialize this checkout and connect a private remote repository to enable multi-computer updates."
    exit 2
}
$gitRoot = [System.IO.Path]::GetFullPath(($gitRoot | Select-Object -First 1).Trim())

$branch = (& git -C $gitRoot branch --show-current).Trim()
if (-not $branch) {
    throw "The repository is in detached HEAD state. Select a branch before starting new work."
}

$remote = (& git -C $gitRoot config --get "branch.$branch.remote")
if ($remote) { $remote = ($remote | Select-Object -First 1).Trim() }
if (-not $remote) { $remote = (& git -C $gitRoot remote | Select-Object -First 1) }
if (-not $remote) {
    Write-Warning "Update check skipped: no Git remote is configured for $gitRoot."
    exit 2
}

Write-Host "Checking updates: $remote/$branch"
& git -C $gitRoot fetch $remote --prune
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fetch from remote '$remote'. Check network access and Git credentials."
}

$upstream = (& git -C $gitRoot for-each-ref --format='%(upstream:short)' "refs/heads/$branch" | Select-Object -First 1)
if (-not $upstream) {
    Write-Warning "Branch '$branch' has no upstream branch. Push it once with: git push -u $remote $branch"
    exit 2
}
$upstream = ($upstream | Select-Object -First 1).Trim()

$counts = (& git -C $gitRoot rev-list --left-right --count "HEAD...$upstream").Trim() -split '\s+'
if ($counts.Count -ne 2) {
    throw "Could not compare HEAD with $upstream."
}
$ahead = [int]$counts[0]
$behind = [int]$counts[1]
$dirty = [bool](& git -C $gitRoot status --porcelain)

if ($behind -eq 0) {
    Write-Host "Update check complete: local branch is current. Ahead=$ahead, Behind=0, Dirty=$dirty"
    exit 0
}

if ($CheckOnly) {
    Write-Warning "Remote updates are available. Ahead=$ahead, Behind=$behind, Dirty=$dirty"
    exit 3
}

if ($dirty) {
    Write-Warning "Remote updates are available, but the worktree has local changes. No pull was attempted."
    Write-Host "Commit or stash the local changes, then rerun .\start-task.ps1."
    exit 3
}

if ($ahead -gt 0) {
    Write-Warning "Local and remote branches have diverged. No automatic merge or rebase was attempted."
    Write-Host "Ahead=$ahead, Behind=$behind. Resolve the branch history before starting new work."
    exit 3
}

& git -C $gitRoot pull --ff-only
if ($LASTEXITCODE -ne 0) {
    throw "Fast-forward update failed. No merge or rebase was attempted."
}

Write-Host "Update complete. The checkout is ready for a new task."
