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
    if ($resolved.Count -gt 0 -and $resolved[0] -eq "frames2video") {
        throw "frames2video is disabled; use multimodal2video"
    }
    if ($resolved.Count -gt 0 -and $resolved[0] -in @("text2video", "image2video", "multimodal2video")) {
        $hasModel = @($resolved | Where-Object { $_ -eq "--model_version" -or $_ -like "--model_version=*" }).Count -gt 0
        if (-not $hasModel) {
            $resolved += "--model_version=seedance2.5"
        }
        $hasVideoResolution = @($resolved | Where-Object { $_ -eq "--video_resolution" -or $_ -like "--video_resolution=*" }).Count -gt 0
        if (-not $hasVideoResolution) {
            $resolved += "--video_resolution=480p"
        }
    }
    return $resolved
}
