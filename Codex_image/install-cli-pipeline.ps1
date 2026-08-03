[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("gemini-cli", "seedance-cli")]
    [string]$Pipeline,
    [switch]$ForceInstall,
    [switch]$SkipLogin
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$privateRoot = Join-Path $PSScriptRoot ".codex-image-private"
$envFile = Join-Path $privateRoot ".env"

if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*([^#][^=]*)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            if ($name -in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY") -and $value) {
                Set-Item -Path "Env:$name" -Value $value
            }
        }
    }
}
if (-not $env:HTTP_PROXY) { $env:HTTP_PROXY = "http://127.0.0.1:7897" }
if (-not $env:HTTPS_PROXY) { $env:HTTPS_PROXY = "http://127.0.0.1:7897" }
if (-not $env:ALL_PROXY) { $env:ALL_PROXY = "socks5://127.0.0.1:7897" }

if ($Pipeline -eq "gemini-cli") {
    $targetDirectory = Join-Path $privateRoot "bin\gemini-cli"
    $binary = Join-Path $targetDirectory "agy.exe"
    $loginScript = Join-Path $PSScriptRoot "CLI\gemini-cli-login.cmd"

    if ($ForceInstall -or -not (Test-Path -LiteralPath $binary)) {
        New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
        $installer = Join-Path ([System.IO.Path]::GetTempPath()) ("agy-install-" + [guid]::NewGuid().ToString("N") + ".ps1")
        try {
            Write-Host "Downloading the official Antigravity CLI installer."
            Invoke-WebRequest -UseBasicParsing -Uri "https://antigravity.google/cli/install.ps1" -OutFile $installer
            if ($ForceInstall -and (Test-Path -LiteralPath $binary)) {
                Remove-Item -LiteralPath $binary -Force
            }
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer --dir $targetDirectory
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $binary)) {
                throw "Antigravity CLI installation did not create $binary."
            }
        } finally {
            if (Test-Path -LiteralPath $installer) { Remove-Item -LiteralPath $installer -Force }
        }
        Write-Host "Antigravity CLI installed in the project: $binary"
    } else {
        Write-Host "Antigravity CLI is already installed in the project: $binary"
    }
} else {
    $targetDirectory = Join-Path $privateRoot "bin\seedance-cli"
    $binary = Join-Path $targetDirectory "dreamina.exe"
    $loginScript = Join-Path $PSScriptRoot "CLI\seedance-login.cmd"

    if ($ForceInstall -or -not (Test-Path -LiteralPath $binary)) {
        $architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
        if ($architecture -ne "AMD64") {
            throw "The bundled Dreamina installer currently supports Windows AMD64 only; detected $architecture."
        }
        New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
        $download = Join-Path ([System.IO.Path]::GetTempPath()) ("dreamina-" + [guid]::NewGuid().ToString("N") + ".exe")
        try {
            $downloadUrl = "https://lf3-static.bytednsdoc.com/obj/eden-cn/psj_hupthlyk/ljhwZthlaukjlkulzlp/dreamina_cli_beta/dreamina_cli_windows_amd64.exe"
            Write-Host "Downloading the official Dreamina CLI Windows binary."
            Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $download
            if ((Get-Item -LiteralPath $download).Length -le 0) {
                throw "The downloaded Dreamina CLI binary is empty."
            }
            Move-Item -LiteralPath $download -Destination $binary -Force
            Unblock-File -LiteralPath $binary -ErrorAction SilentlyContinue
        } finally {
            if (Test-Path -LiteralPath $download) { Remove-Item -LiteralPath $download -Force }
        }
        Write-Host "Dreamina CLI installed in the project: $binary"
    } else {
        Write-Host "Dreamina CLI is already installed in the project: $binary"
    }
}

if (-not $SkipLogin) {
    $authenticated = $false
    Write-Host "Checking the existing $Pipeline login session."
    if ($Pipeline -eq "gemini-cli") {
        $wrapper = Join-Path $PSScriptRoot "CLI\Gemini-CLI\agy-proxy.ps1"
        $loginCheck = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $wrapper models 2>&1
        $authenticated = $LASTEXITCODE -eq 0 -and @($loginCheck).Count -gt 0
    } else {
        $loginCheck = & $binary user_credit 2>&1
        $authenticated = $LASTEXITCODE -eq 0 -and (($loginCheck -join "`n") -match 'total_credit')
    }

    if ($authenticated) {
        Write-Host "The existing $Pipeline login session is valid; browser login was skipped."
    } else {
        Write-Host "Starting the $Pipeline login flow in the Windows default browser."
        & $loginScript
        if ($LASTEXITCODE -ne 0) {
            throw "$Pipeline login failed with exit code $LASTEXITCODE."
        }
    }
}
