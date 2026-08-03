[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("gemini-api", "gpt-api", "comfly-api")]
    [string]$Pipeline,
    [string]$EnvFile = (Join-Path $PSScriptRoot ".codex-image-private\.env")
)

$ErrorActionPreference = "Stop"
$KeyNames = @{
    "gemini-api" = "GEMINI_API_KEY"
    "gpt-api" = "APIMART_API_KEY"
    "comfly-api" = "COMFLY_API_KEY"
}
$KeyName = $KeyNames[$Pipeline]
$EnvFile = [System.IO.Path]::GetFullPath($EnvFile)
$parent = Split-Path -Parent $EnvFile
New-Item -ItemType Directory -Path $parent -Force | Out-Null

$secureValue = Read-Host "Enter $KeyName (input is hidden)" -AsSecureString
$bstr = [IntPtr]::Zero
try {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    $plainValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plainValue)) {
        throw "$KeyName cannot be empty."
    }
    if ($plainValue -match "[`r`n]") {
        throw "$KeyName cannot contain a newline."
    }

    $lines = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $EnvFile) {
        foreach ($line in Get-Content -LiteralPath $EnvFile) {
            $lines.Add($line)
        }
    }
    $replacement = "$KeyName=$plainValue"
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$([regex]::Escape($KeyName))\s*=") {
            if (-not $found) {
                $lines[$i] = $replacement
                $found = $true
            } else {
                $lines.RemoveAt($i)
                $i--
            }
        }
    }
    if (-not $found) {
        $lines.Add($replacement)
    }

    [System.IO.File]::WriteAllLines($EnvFile, $lines, [System.Text.UTF8Encoding]::new($false))
} finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    $plainValue = $null
}

Write-Host "$KeyName was saved to $EnvFile. The value was not printed or added to registration metadata."
