# Multi-computer workflow

## New computer

Clone this repository, open PowerShell in the checkout root, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-new-machine.ps1
```

For a guided one-shot template that also prompts for API keys, use [NEW_MACHINE_DEPLOYMENT_TEMPLATE.md](NEW_MACHINE_DEPLOYMENT_TEMPLATE.md) and run `new-machine-deploy.ps1`.

In Codex chat, deployment-style requests such as `初始化`, `部署`, `更新部署`, `安装`, `一键部署`, or `初始化部署` should map to `new-machine-deploy.ps1` by default.

The command is repeatable. It:

- checks the Git update state when a remote is configured;
- installs missing Git, Python, Node.js, and Python packages when `winget` is available;
- merges portable Codex settings without replacing machine-generated settings;
- installs the repository's global `AGENTS.md` and merges the global `config.toml`;
- migrates legacy credentials and binaries into `Codex_image/.codex-image-private/`;
- installs Dreamina CLI when it is missing and starts login when required;
- installs the bundled 512 px preview converter into `CODEX_HOME/tools/`;
- registers the unified image/video tools and plugin;
- deploys `Codex_DT` using the sibling `Codex_image` CLI.

API keys are intentionally excluded from Git. Configure only the providers you use:

```powershell
.\Codex_image\configure-api-key.ps1 -Pipeline comfly-api
.\Codex_image\configure-api-key.ps1 -Pipeline gpt-api
.\Codex_image\configure-api-key.ps1 -Pipeline gemini-api
```

Key sources:

- `COMFLY_API_KEY` - [ai.comfly.org](https://ai.comfly.org/)
- `APIMART_API_KEY` - [apimart.ai/zh](https://apimart.ai/zh)
- `GEMINI_API_KEY` - [aistudio.google.com](https://aistudio.google.com/)

Dreamina/Jimeng should be signed in ahead of time at [jimeng.jianying.com](https://jimeng.jianying.com/).

Machine-local Codex paths such as `notify`, `mcp_servers.node_repl.*`, `CODEX_CLI_PATH`, `marketplaces.*`, `projects.*`, and `shell_environment_policy.*` are not copy-fill inputs. They are rebuilt or preserved by the Codex setup scripts on each computer.

## Before every new task

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-task.ps1
```

The script fetches the remote branch. It automatically pulls only when the checkout is clean, strictly behind, and can be fast-forwarded. It stops for local changes, divergence, detached HEAD, missing upstream, authentication failures, or network failures.

It never runs `reset`, `stash`, merge, rebase, or a force operation.

## Synchronize global Codex files

The `codex-global/AGENTS.md` file is the shared global guidance source. The repository's
`config.toml` is intentionally machine-local and must not be copied directly because
it contains runtime and absolute-path settings. To update global Codex safely, double-click:

```text
Sync-CodexGlobal.cmd
```

Or run it from PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\sync-global-codex.ps1 -Yes
```

The script backs up the existing global `AGENTS.md` and `config.toml`, replaces `AGENTS.md`
from `codex-global/AGENTS.md`, and regenerates/updates `config.toml` from
`codex-global/config.portable.toml` while preserving
machine-generated paths and existing MCP/project settings.
