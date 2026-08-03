# CODEX IMAGE TOOLS

encoding:
  default_text_encoding: 'utf-8'
  instructions:
    - 'Read and write Chinese documents as UTF-8 by default.'
    - 'If Chinese text appears garbled, retry with likely source encodings such as UTF-8 with BOM, GB18030, GBK, or Big5 before editing or summarizing.'
    - 'When using PowerShell, prefer explicit encodings, for example Get-Content -Encoding UTF8 or Set-Content -Encoding UTF8.'

media_tools:
  source_root: '${CODEX_IMAGE_ROOT}'
  private_runtime: '${CODEX_IMAGE_ROOT}/.codex-image-private'

  available_tools:
    image:
      tool: 'generate_image'
      skill: '$default-image-generation'
      capability: 'Generate or edit still images through the unified image router.'

    video:
      tool: 'generate_video'
      skill: '$default-video-generation'
      capability: 'Generate videos through the unified video tool.'

proxy:
  HTTP_PROXY: '${HTTP_PROXY}'
  HTTPS_PROXY: '${HTTPS_PROXY}'
  ALL_PROXY: '${ALL_PROXY}'

instructions:
  - 'Expose and use only generate_image and generate_video for ordinary media requests. Do not expose or invoke provider-specific skills or adapters directly.'
  - 'Let the active workspace configuration and unified router select enabled providers; do not ask ordinary users to choose a provider.'
  - 'Follow the active workspace AGENTS.md, use configured provider wrappers, and keep credentials, cookies, tokens, logs, caches, and generated runtime files inside .codex-image-private.'
  - 'Never expose API keys, cookies, authorization headers, or credential values.'
  - 'Before any local image is sent to an API or CLI provider, normalize its orientation and proportionally resize it when its longest edge exceeds 1920 px. Never overwrite the original; keep resized provider inputs inside .codex-image-private.'
  - 'For local raster images, never inspect the original directly. Create a preview with ${CODEX_HOME}/tools/Convert-CodexImagePreview.ps1 or the configured preview tool, longest edge <= 512 px, then inspect only the preview.'
  - 'At the beginning of a new task in this checkout, run powershell -NoProfile -ExecutionPolicy Bypass -File ./start-task.ps1 before editing. If the script reports local changes, divergence, or an unavailable remote, report that state and do not overwrite local work.'
  - 'For a new-computer deployment request, run powershell -NoProfile -ExecutionPolicy Bypass -File ./bootstrap-new-machine.ps1 from this root. This is the shared deployment entry for Codex_image and Codex_DT.'
  - 'To synchronize the repository guidance and portable Codex settings into the current user global Codex home, run codex-global/sync-global-codex.ps1 or double-click Sync-CodexGlobal.cmd. Never copy a machine-local config.toml directly.'
