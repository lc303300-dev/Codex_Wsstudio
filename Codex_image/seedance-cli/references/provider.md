# Dreamina and Seedance CLI

Official installer: `curl -fsSL https://jimeng.jianying.com/cli | bash`.

The installer script's Windows x64 branch downloads `dreamina_cli_windows_amd64.exe`. It is installed from the project root at `.codex-image-private/bin/seedance-cli/dreamina.exe`.

- Verified release: `1.4.12` dated `2026-07-15`; user-provided official notes mention `v1.4.14` dated `2026-07-21`, where image generation requires explicit `--resolution_type` and video generation requires explicit `--video_resolution`
- Authentication: OAuth Device Flow via `dreamina login`
- Image commands: `text2image`, `image2image`, `image_upscale`
- Image model policy: default `text2image` and `image2image` to `4.0`; use `5.0Pro` only for explicit maximum-quality requests
- Image resolution policy: keep the requested supported resolution; use `4k` for an unspecified-resolution maximum-quality 5.0Pro request
- Video commands: `text2video`, `image2video`, `frames2video`, `multiframe2video`, `multimodal2video`
- `multimodal2video` is Dreamina Web's "全能参考" / all-around reference mode. Bind local absolute paths with `--image`, `--video`, and `--audio`; at least one image or video is required. Current CLI help allows image<=9, video<=3, audio<=3, audio length 2-15s, duration 4-15s, and ratios `1:1`, `3:4`, `16:9`, `4:3`, `9:16`, `21:9`.
- Video model policy: default supported video commands to Seedance 2.0 Fast VIP (`seedance2.0fast_vip`); do not inject a model for `multiframe2video` because the current CLI does not support model overrides there
- Video resolution policy: default supported video commands to `720p` unless the user explicitly requests another supported resolution; do not inject a resolution for `multiframe2video` because the current CLI does not support resolution overrides there
- Async query: `query_result`
- Account check: `user_credit`
- Independence: no Gemini or GPT fallback
