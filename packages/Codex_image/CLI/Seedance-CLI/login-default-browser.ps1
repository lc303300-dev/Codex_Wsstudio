$ErrorActionPreference = "Stop"
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$dreamina = Join-Path $projectRoot ".codex-image-private\bin\seedance-cli\dreamina.exe"
if (-not (Test-Path -LiteralPath $dreamina)) { throw "dreamina.exe not found: $dreamina" }

$output = & $dreamina login --headless 2>&1
$output | ForEach-Object { Write-Host $_ }
$text = $output -join "`n"

if ($text -match '\[DREAMINA:LOGIN_REUSED\]') {
    Write-Host "The existing Dreamina login session is still valid."
    exit 0
}

$uriMatch = [regex]::Match($text, '(?m)^verification_uri:\s*(\S+)')
$codeMatch = [regex]::Match($text, '(?m)^user_code:\s*(\S+)')
$deviceMatch = [regex]::Match($text, '(?m)^device_code:\s*(\S+)')
if (-not $uriMatch.Success -or -not $deviceMatch.Success) {
    throw "Dreamina login did not return verification_uri and device_code."
}

Write-Host "Opening the login page in the Windows default browser."
if ($codeMatch.Success) { Write-Host "user_code: $($codeMatch.Groups[1].Value)" }
Start-Process $uriMatch.Groups[1].Value
& $dreamina login checklogin "--device_code=$($deviceMatch.Groups[1].Value)" --poll=300
if ($LASTEXITCODE -ne 0) { throw "Dreamina OAuth login failed with exit code $LASTEXITCODE." }
Write-Host "Dreamina login succeeded and the local session was saved."
