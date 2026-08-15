# Workspace Deployment Triggers

## Proactive Sub-Agent Delegation

When a task contains two or more concrete, bounded, and substantially independent workstreams, proactively prefer sub-agent delegation to reduce wall-clock completion time. Delegate only when the main agent can continue useful work concurrently, scopes are clear, synchronization is limited, and agents will not edit the same files or shared state. Keep the main agent responsible for integration, verification, safety checks, and the final answer. Do not delegate small or inherently sequential tasks, or when coordination overhead, file conflicts, authorization, or skill instructions outweigh the parallel benefit. Use only as many agents as provide meaningful parallelism.

When the user is clearly asking to set up, install, deploy, update deployment, or bootstrap this repository, treat the request as a one-click deployment request and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\new-machine-deploy.ps1
```

Treat these as deployment triggers when they refer to this repository:

- `初始化`
- `部署`
- `更新部署`
- `安装`
- `一键部署`
- `初始化部署`
- `新电脑部署`

Before starting a deployment, if the required API keys are not already present in `packages/Codex_image/.codex-image-private/.env`, ask the user to provide them as a copy-fill checklist and include clickable official links:

- `COMFLY_API_KEY` - [ai.comfly.org](https://ai.comfly.org/)
- `APIMART_API_KEY` - [apimart.ai/zh](https://apimart.ai/zh)
- `GEMINI_API_KEY` - [aistudio.google.com](https://aistudio.google.com/)

Also ask the user to sign in ahead of time for Dreamina/Jimeng at [jimeng.jianying.com](https://jimeng.jianying.com/).

Do not ask the user to hand-copy machine-local Codex config paths such as `notify`, `mcp_servers.node_repl.*`, `CODEX_CLI_PATH`, `marketplaces.*`, `projects.*`, or `shell_environment_policy.*`. Those are regenerated or preserved by the Codex setup scripts on each machine.

If the user asks for the older step-by-step flow instead, use `scripts/deployment/bootstrap-new-machine.ps1` and the existing manual deployment docs.

Keep this root instruction aligned with `README.md`, `docs/DEPLOYMENT.md`, and `docs/NEW_MACHINE_DEPLOYMENT_TEMPLATE.md`.

## Repository Update Check Scope

Before writing files in this checkout, run the root `start-task.ps1`. This rule applies only when the current or explicitly targeted path resolves inside this Git checkout and the root script exists.

Do not run or search for `start-task.ps1` for pure chat, public network or GitHub searches, read-only work, projectless Codex directories, or unrelated repositories. If the user explicitly requests changes to this repository but the root script is missing, report the problem and stop before writing.

## Standard Project Structure

This repository uses the monorepo layout defined in `docs/PROJECT_STRUCTURE.md`:

- application and tool projects belong under `packages/`;
- repository documentation belongs under `docs/`;
- shared configuration belongs under `config/`;
- automation belongs under `scripts/`, grouped by purpose;
- the root is reserved for repository metadata, dependency/test manifests, governance files, and stable entry scripts.
- packaged projects currently live in `packages/Codex_image/`, `packages/Codex_DT/`, `packages/Codex_Gif/`, `packages/Codex_Github/`, and `packages/Codex_CS/`.

Do not add new implementation scripts, project directories, generated output, or standalone design documents to the repository root. Before completing any change, run `scripts/maintenance/test-project-structure.ps1`. Structural changes must update the structure document, README, validation allowlist, path references, and both repository/global guidance when applicable.

## Video Business Skill Routing

When a user wants to use a governed business Skill to create a video, use the globally registered `video-skill-router` first. Select the Skill from the user's creative intent, then read the selected Skill contract and guide the user to provide required materials. Do not choose the Skill primarily from materials already supplied. Codex_DT remains the downstream prompt-authoring and video-generation orchestrator after the contract is satisfied.
