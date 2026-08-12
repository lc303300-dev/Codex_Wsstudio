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
  - 'When a task contains two or more concrete, bounded, and substantially independent workstreams, proactively prefer sub-agent delegation to reduce wall-clock completion time. Delegate only when the main agent can continue useful work concurrently, scopes are clear, synchronization is limited, and agents will not edit the same files or shared state. Keep the main agent responsible for integration, verification, safety checks, and the final answer. Do not delegate small or inherently sequential tasks, or when coordination overhead, file conflicts, authorization, or skill instructions outweigh the parallel benefit. Use only as many agents as provide meaningful parallelism.'
  - 'Expose and use only generate_image and generate_video for ordinary media requests. Do not expose or invoke provider-specific skills or adapters directly.'
  - 'Let the active workspace configuration and unified router select enabled providers; do not ask ordinary users to choose a provider.'
  - 'Follow the active workspace AGENTS.md, use configured provider wrappers, and keep credentials, cookies, tokens, logs, caches, and generated runtime files inside .codex-image-private.'
  - 'Never expose API keys, cookies, authorization headers, or credential values.'
  - 'Before any local image is sent to an API or CLI provider, normalize its orientation and proportionally resize it when its longest edge exceeds 1920 px. Never overwrite the original; keep resized provider inputs inside .codex-image-private.'
  - 'For local raster images, never inspect the original directly. Create a preview with ${CODEX_HOME}/tools/Convert-CodexImagePreview.ps1 or the configured preview tool, longest edge <= 1024 px, then inspect only the preview.'
  - 'Run the repository safe-update check only before writing files in the Codex_Wsstudio checkout or one of its packages. Resolve the Git root from the current or explicitly targeted repository path and run that root''s start-task.ps1 only when the file exists. Do not run or search for start-task.ps1 for pure chat, public web/GitHub search, read-only work, projectless Codex directories, or work outside this checkout. If the user explicitly requests changes to this repository and its root start-task.ps1 is missing, report the problem and stop before writing. If the script reports local changes, divergence, an invalid project structure, or an unavailable remote, report that state and do not overwrite local work.'
  - 'Codex_Wsstudio uses a standard monorepo layout: projects in packages/, repository docs in docs/, shared configuration in config/, and automation in scripts/. Keep the repository root limited to metadata, manifests, governance files, and stable entry scripts. Follow docs/PROJECT_STRUCTURE.md and run scripts/maintenance/test-project-structure.ps1 before completing changes.'
  - 'For a new-computer deployment request that explicitly targets Codex_Wsstudio, first resolve its checkout root, then run that root''s new-machine-deploy.ps1. Use scripts/deployment/bootstrap-new-machine.ps1 only for the manual flow. Do not assume a projectless or unrelated current directory is the repository root.'
  - 'To synchronize this repository''s guidance and portable Codex settings into the current user global Codex home, first resolve the Codex_Wsstudio checkout root, then run scripts/codex/sync-global-codex.ps1 or scripts/codex/Sync-CodexGlobal.cmd. Never copy a machine-local config.toml directly.'
  - 'When the user asks to find an existing tool, software, GitHub repository, npm package, MCP server, Agent Skill, plugin, extension, API, integration, automation, or alternative—or when building a feature could benefit from an existing external tool—automatically read and use the globally registered codex-github skill (Codex_Github / Tool Scout) before implementing. Prefer its native feature audit and ranked V0/V1 search workflow.'
  - 'When the user asks to convert video to GIF, batch convert clips to GIF, or reduce a local video to a GIF under a size cap, prefer packages/Codex_Gif first. Use its run-video-to-gif.ps1 entry point and the globally registered video-to-gif skill instead of building a separate media router path.'
  - 'When the user provides images and a short prompt and wants to generate video, asks for general video generation, or the agent needs to supplement, newly write, repair, optimize, or rewrite a video prompt before generation, use the globally registered codex-dt-video-prompt skill as a low-priority default prompt optimization layer before generation. Do not use it when the active project has its own video or image-to-video pipeline guidance. After optimization, ask whether to call default-video-generation; do not submit paid generation from that skill.'
