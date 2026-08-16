# Multi-computer workflow

## New computer

Clone this repository, open PowerShell in the checkout root, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deployment\bootstrap-new-machine.ps1
```

For a guided one-shot template that also prompts for API keys, use [NEW_MACHINE_DEPLOYMENT_TEMPLATE.md](NEW_MACHINE_DEPLOYMENT_TEMPLATE.md) and run `new-machine-deploy.ps1`.

In Codex chat, deployment-style requests such as `初始化`, `部署`, `更新部署`, `安装`, `一键部署`, or `初始化部署` should map to `new-machine-deploy.ps1` by default.

The command is repeatable. It:

- checks the Git update state when a remote is configured;
- installs missing Git, Python, Node.js, and Python packages when `winget` is available;
- merges portable Codex settings without replacing machine-generated settings;
- installs the repository's global `AGENTS.md` and merges the global `config.toml`;
- migrates legacy credentials and binaries into `packages/Codex_image/.codex-image-private/`;
- installs Dreamina CLI when it is missing and starts login when required;
- installs the bundled 1024 px preview converter into `CODEX_HOME/tools/`;
- registers the unified image/video tools and plugin;
- registers the video-to-GIF, Tool Scout, Codex_DT, Codex_CS, batch-image-generation, and Codex_IS global skills;
- deploys `Codex_DT` using the sibling `Codex_image` CLI.
- runs a post-deployment verification that checks required paths, installed global guidance, the sub-agent delegation rule, and project structure.

API keys are intentionally excluded from Git. Configure only the providers you use:

```powershell
.\packages\Codex_image\configure-api-key.ps1 -Pipeline comfly-api
.\packages\Codex_image\configure-api-key.ps1 -Pipeline gpt-api
.\packages\Codex_image\configure-api-key.ps1 -Pipeline gemini-api
```

Key sources:

- `COMFLY_API_KEY` - [ai.comfly.org](https://ai.comfly.org/)
- `APIMART_API_KEY` - [apimart.ai/zh](https://apimart.ai/zh)
- `GEMINI_API_KEY` - [aistudio.google.com](https://aistudio.google.com/)

Dreamina/Jimeng should be signed in ahead of time at [jimeng.jianying.com](https://jimeng.jianying.com/).

Machine-local Codex paths such as `notify`, `mcp_servers.node_repl.*`, `CODEX_CLI_PATH`, `marketplaces.*`, `projects.*`, and `shell_environment_policy.*` are not copy-fill inputs. They are rebuilt or preserved by the Codex setup scripts on each computer.

## Before writing in this checkout

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-task.ps1
```

The script fetches the remote branch. It automatically pulls only when the checkout is clean, strictly behind, and can be fast-forwarded. It stops for local changes, divergence, detached HEAD, missing upstream, authentication failures, or network failures.

It never runs `reset`, `stash`, merge, rebase, or a force operation.

Only apply this check when the current or explicitly targeted path is inside this Git
checkout and the root `start-task.ps1` exists. Do not run or search for the script for
pure chat, public web/GitHub searches, read-only work, projectless Codex directories,
or unrelated repositories. If an edit explicitly targets this repository but the root
script is missing, report the problem and stop before writing.

## Synchronize global Codex files

The `config/codex/AGENTS.md` file is the shared global guidance source. The repository's
`config.toml` is intentionally machine-local and must not be copied directly because
it contains runtime and absolute-path settings. To update global Codex safely, double-click:

```text
scripts\codex\Sync-CodexGlobal.cmd
```

Or run it from PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex\sync-global-codex.ps1 -Yes
```

The script backs up the existing global `AGENTS.md` and `config.toml`, replaces `AGENTS.md`
from `config/codex/AGENTS.md`, and regenerates/updates `config.toml` from
`config/codex/config.portable.toml` while preserving
machine-generated paths and existing MCP/project settings.

The synchronized global guidance also installs the Windows local-resource output contract:
Markdown links and embedded local media must use absolute forward-slash paths, must not use
`file://` URIs, and must reuse tool-returned resource/link targets instead of rebuilding them
from raw Windows paths. Deployment verification fails if this contract is missing from either
the repository guidance source or the installed global `AGENTS.md`.

It also installs the required image-ratio contract. Every image generation or edit must have
an explicit user-selected ratio before submission; the ratio is passed through the structured
`generate_image.image_ratio` field, and missing values are rejected before any paid provider call. Image resolution is an optional sibling `generate_image.image_resolution` option with `1K`, `2K`, and `4K`; when omitted, GPT image routes default to `4K`, Gemini image routes default to `2K`, and Dreamina retains `1K`.
Deployment verification fails if this rule is absent from the installed global guidance.

The installed guidance treats the configured image route order as the default rather than a
mandatory path. Ordinary requests continue to use automatic serial fallback. If the current user
explicitly names a supported, unambiguous route, Codex passes it through
`generate_image.image_provider`, uses only that route, and does not invoke a provider-specific
skill directly.

It also refreshes the unified media tools and `codex-media-plugin` from
`packages/Codex_image/`, including managed personal marketplace and cached plugin
copies, then refreshes the globally registered `codex-github`, `video-to-gif`,
`codex-dt-video-prompt`, and `codex-cs-skill-curator` skills from
`packages/Codex_Github/`, `packages/Codex_Gif/`, `packages/Codex_DT/`,
`packages/Codex_CS/`, `packages/Codex_Batch_Image/`, and `packages/Codex_IS/` when those package scripts are present.

After deployment, the same pipeline runs `scripts/maintenance/verify-deployment.ps1`.
Run it independently to audit an existing machine:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\maintenance\verify-deployment.ps1
```
