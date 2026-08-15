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
  - 'Use codex-dt-video-prompt as the unified public video-generation orchestrator. Before any creative rewrite, classify the user prompt. If it is final or already executable, apply only semantic-preserving normalization: fix adapter reference labels/order, broken formatting, punctuation, and unambiguous terminology mistakes without changing subject, action, shot intent, timing, style, emotion, constraints, audio, or outcome. Never add creative content; leave ambiguous corrections unchanged. Optimize only incomplete, short, contradictory, or structurally weak prompts. Read the Seedance/forge corpus only for those incomplete prompts or when the user explicitly requests corpus assistance.'
  - 'Use the Codex_DT `video-director-prompt` skill as the platform-neutral authoring layer for video prompts. Treat corpus model/version fields as provenance metadata only. Default all supported video generation to Seedance 2.5; use Seedance 2.0 only when the current user explicitly requests it, and never automatically fall back from 2.5 to 2.0.'
  - 'When Codex explicitly tests video submission, use generate_video with video_execution_mode=test_submit_only. This paid test channel force-selects non-VIP seedance2.0 at 720p with polling disabled, returns after submit_id plus querying/success, and tells the user to inspect the Dreamina website backend. Never query or download afterward. Ordinary 2.0 requests still normalize to seedance2.0_vip.'
  - 'Treat Dreamina multiframe2video / intelligent multi-frame as disabled legacy functionality. Never select, suggest, expose, or submit it. Route multiple-image video work through multimodal2video (全能参考), except explicit first/last-frame work which uses frames2video.'
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
  - 'When adding, migrating, reviewing, validating, or publishing governed video business Skills, use packages/Codex_CS and the globally registered codex-cs-skill-curator skill. Codex_CS preserves business prompt experience and contracts only; it must not submit videos, choose providers, choose actual model versions, poll, download, or spend credits.'
  - 'When a user wants to use a governed business Skill to create a video, use the globally registered video-skill-router first. Confirm Skill name, ratio, and duration before creating contract-slot project directories. Each Skill contract declares per-slot pacing rules; derive planned material counts from duration and never apply one global images-per-second rule. The selected CS Skill authors prompt V1; every requested revision automatically goes to Codex_DT. Explicit/local edits skip the corpus, while ambiguous, creative, or structural edits may inspect at most three examples. Confirm every prompt version before unified generate_video execution. Do not choose the Skill primarily from materials already supplied.'
  - 'For general video generation, enter through the globally registered codex-dt-video-prompt skill unless a stronger project pipeline applies. Codex_DT decides whether authoring is needed, while default-video-generation and Media Router remain the only paid execution layer. Never call Dreamina CLI directly from prompt skills.'
