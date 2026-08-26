$ErrorActionPreference = "Stop"
$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$SetupScript = Join-Path $RepositoryRoot "scripts\codex\setup-codex.ps1"
$TemporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-setup-test-" + [guid]::NewGuid().ToString("N"))

try {
    New-Item -ItemType Directory -Path $TemporaryRoot -Force | Out-Null
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $SetupScript -CodexHome $TemporaryRoot -SkipProjectTrust -SkipBackup
    if ($LASTEXITCODE -ne 0) { throw "Codex setup exited with $LASTEXITCODE." }

    $config = Get-Content -LiteralPath (Join-Path $TemporaryRoot "config.toml") -Raw -Encoding UTF8
    if ($config -notmatch '(?s)\[marketplaces\.personal\].*?source_type\s*=\s*"local"') {
        throw "Personal marketplace source type was not configured."
    }
    if ($config -notmatch ('(?s)\[marketplaces\.personal\].*?source\s*=\s*' + [regex]::Escape("'" + $env:USERPROFILE + "'"))) {
        throw "Personal marketplace source was not resolved to the current user profile."
    }
    if ($config -notmatch '(?s)\[plugins\."codex-media-plugin@personal"\].*?enabled\s*=\s*true') {
        throw "codex-media-plugin@personal was not enabled."
    }
    Write-Output "Codex setup marketplace tests passed."
}
finally {
    if (Test-Path -LiteralPath $TemporaryRoot) {
        Remove-Item -LiteralPath $TemporaryRoot -Recurse -Force
    }
}
