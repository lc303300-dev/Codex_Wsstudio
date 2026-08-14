# Dreamina and Seedance CLI

Official installer: `curl -fsSL https://jimeng.jianying.com/cli | bash`.

The installer script's Windows x64 branch downloads `dreamina_cli_windows_amd64.exe`. It is installed from the project root at `.codex-image-private/bin/seedance-cli/dreamina.exe`.

- Verified release: `1.4.12` dated `2026-07-15`; user-provided official notes mention `v1.4.14` dated `2026-07-21`, where image generation requires explicit `--resolution_type` and video generation requires explicit `--video_resolution`
- Authentication: OAuth Device Flow via `dreamina login`
- Image commands: `text2image`, `image2image`, `image_upscale`
- Image model policy: default `text2image` and `image2image` to `4.0`; use `5.0Pro` only for explicit maximum-quality requests
- Image resolution policy: keep the requested supported resolution; use `4k` for an unspecified-resolution maximum-quality 5.0Pro request
- Enabled video commands: `text2video`, `image2video`, `frames2video`, `multimodal2video`. The legacy `multiframe2video` command is disabled and must not be selected or submitted.
- `multimodal2video` is Dreamina Web's "全能参考" / all-around reference mode. Bind local absolute paths with `--image`, `--video`, and `--audio`. Default Seedance 2.5 allows audio-only, image<=30, video<=10, audio<=10, total inputs<=50, each and total video/audio duration 2-30s, output duration 4-30s, resolution `480p` or `720p`, and ratios `1:1`, `3:4`, `16:9`, `4:3`, `9:16`, `21:9`. Explicit non-2.5 models must follow current CLI help.
- Video model policy: default supported video commands to Seedance 2.5 (`seedance2.5`)
- Video resolution policy: default supported video commands to `480p` unless the user explicitly requests another supported resolution
- Async query: `query_result`
- Account check: `user_credit`
- Independence: no Gemini or GPT fallback
