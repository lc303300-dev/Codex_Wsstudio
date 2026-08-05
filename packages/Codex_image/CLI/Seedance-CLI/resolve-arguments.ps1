function Resolve-DreaminaArguments {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]]$InputArguments
    )

    $resolved = @($InputArguments)
    if ($resolved.Count -gt 0 -and $resolved[0] -in @("text2image", "image2image")) {
        $hasModel = @($resolved | Where-Object { $_ -eq "--model_version" -or $_ -like "--model_version=*" }).Count -gt 0
        if (-not $hasModel) {
            $resolved += "--model_version=4.0"
        }
    }
    if ($resolved.Count -gt 0 -and $resolved[0] -in @("text2video", "image2video", "frames2video", "multimodal2video")) {
        $hasModel = @($resolved | Where-Object { $_ -eq "--model_version" -or $_ -like "--model_version=*" }).Count -gt 0
        if (-not $hasModel) {
            $resolved += "--model_version=seedance2.0_vip"
        }
        $hasVideoResolution = @($resolved | Where-Object { $_ -eq "--video_resolution" -or $_ -like "--video_resolution=*" }).Count -gt 0
        if (-not $hasVideoResolution) {
            $resolved += "--video_resolution=720p"
        }
    }
    return $resolved
}
