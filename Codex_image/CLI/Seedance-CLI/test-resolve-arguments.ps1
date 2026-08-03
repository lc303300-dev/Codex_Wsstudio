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

$videoCommands = @("text2video", "image2video", "frames2video", "multimodal2video")
foreach ($command in $videoCommands) {
    Assert-Arguments `
        -Name "$command defaults" `
        -InputArguments @($command) `
        -ExpectedArguments @($command, "--model_version=seedance2.0fast_vip", "--video_resolution=720p")
}

Assert-Arguments `
    -Name "explicit video resolution" `
    -InputArguments @("text2video", "--video_resolution=1080p") `
    -ExpectedArguments @("text2video", "--video_resolution=1080p", "--model_version=seedance2.0fast_vip")

Assert-Arguments `
    -Name "explicit split video resolution" `
    -InputArguments @("text2video", "--video_resolution", "4k") `
    -ExpectedArguments @("text2video", "--video_resolution", "4k", "--model_version=seedance2.0fast_vip")

Assert-Arguments `
    -Name "multiframe unsupported overrides" `
    -InputArguments @("multiframe2video") `
    -ExpectedArguments @("multiframe2video")

Write-Output "Dreamina argument resolution tests passed."
