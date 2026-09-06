$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "resolve-arguments.ps1")

function Assert-Arguments {
    param(
        [string]$Name,
        [string[]]$InputArguments,
        [string[]]$ExpectedArguments
    )

    $actual = @(Resolve-DreaminaArguments -InputArguments $InputArguments)
    if (($actual -join "`n") -ne ($ExpectedArguments -join "`n")) {
        throw "$Name failed.`nExpected: $($ExpectedArguments -join ' ')`nActual:   $($actual -join ' ')"
    }
}

$videoCommands = @("text2video", "image2video", "multimodal2video")
foreach ($command in $videoCommands) {
    Assert-Arguments `
        -Name "$command defaults" `
        -InputArguments @($command) `
        -ExpectedArguments @($command, "--model_version=seedance2.5", "--video_resolution=480p")
}

Assert-Arguments `
    -Name "explicit video resolution" `
    -InputArguments @("text2video", "--video_resolution=1080p") `
    -ExpectedArguments @("text2video", "--video_resolution=1080p", "--model_version=seedance2.5")

Assert-Arguments `
    -Name "explicit split video resolution" `
    -InputArguments @("text2video", "--video_resolution", "4k") `
    -ExpectedArguments @("text2video", "--video_resolution", "4k", "--model_version=seedance2.5")

Assert-Arguments `
    -Name "multiframe unsupported overrides" `
    -InputArguments @("multiframe2video") `
    -ExpectedArguments @("multiframe2video")

try {
    Resolve-DreaminaArguments -InputArguments @("frames2video") | Out-Null
    throw "frames2video should be disabled"
}
catch {
    if ($_.Exception.Message -notmatch "frames2video is disabled") { throw }
}

Write-Output "Dreamina argument resolution tests passed."
