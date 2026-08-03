# Multi-computer workflow

## New computer

Clone the private Git repository, open PowerShell in the checkout root, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-new-machine.ps1
```

The command is repeatable. It:

- checks the Git update state when a remote is configured;
- merges portable Codex settings without replacing machine-generated settings;
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

## Before every new task

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-task.ps1
```

The script fetches the remote branch. It automatically pulls only when the checkout is clean, strictly behind, and can be fast-forwarded. It stops for local changes, divergence, detached HEAD, missing upstream, authentication failures, or network failures.

It never runs `reset`, `stash`, merge, rebase, or a force operation.
