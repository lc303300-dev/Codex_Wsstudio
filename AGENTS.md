# Workspace Deployment Triggers

## Chat-Escaped Windows Paths

Treat underscores in user-provided names and paths as literal filename characters. For example, `JY_003` is one complete name and must never be split into `JY` plus `_003` or interpreted as a directory boundary. Chat copy/paste may recursively Markdown-escape it as `JY\_003` or `JY\\\_003`, and may add HTML entities such as `&#x20;`. Before using any user-provided local path in a file, preview, upload, media, API, CLI, or tool call, run `${CODEX_HOME}/tools/Resolve-CodexChatPath.ps1` on the exact chat text. Continue only when it returns `status=resolved` with exactly one existing candidate. Otherwise stop and ask; never guess or reconstruct the path. Preserve the verified basename character-for-character.

## Windows Local Markdown Resources

Treat Windows local Markdown links and embedded local media as a hard output contract. Never place a raw backslash path such as `D:\workspace\file.png` inside a Markdown link or image target. Use an absolute path with forward slashes such as `D:/workspace/file.png`, never a `file://` URI; when the target contains spaces, wrap the entire target in angle brackets. When a tool returns a renderable image, file resource, or dedicated Markdown link target, forward that returned resource or target directly and never reconstruct it from `output_path`, a display path, or another raw Windows path. Before sending a final response containing a local Markdown link or image, verify that every local target is absolute, uses forward slashes, and refers to the intended existing file or directory. If any local target contains a backslash, do not send the response until it is corrected.

## Required Image Ratio

Before every image generation or image edit, require the user to explicitly choose one supported ratio: `21:9`, `16:9`, `3:2`, `4:3`, `1:1`, `3:4`, `2:3`, or `9:16`. If no ratio is explicit, refuse to submit generation and ask the user for it. Never infer image ratio from reference images, orientation, prompt context, earlier turns, filenames, or provider defaults. Pass the chosen value through the structured `generate_image` `image_ratio` field.

Image resolution is an optional sibling structured `generate_image.image_resolution` option. Supported values are `1K`, `2K`, and `4K`. When omitted, GPT image routes default to `4K`, Gemini image routes default to `2K`, and Dreamina retains `1K`.

## Explicit Image Route

Treat the configured image-provider sequence as the default rather than a mandatory workflow. Do not proactively ask ordinary users to choose a route. When the current user explicitly names one supported and unambiguous image route, pass it through the unified `generate_image.image_provider` field so the router uses only that route and does not fall back to other routes. Keep provider-specific skills and adapters private; ask a minimal clarification for ambiguous names and reject unsupported or disabled routes before paid submission.

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
- packaged projects currently live in `packages/Codex_image/`, `packages/Codex_Flow/`, `packages/Codex_DT/`, `packages/Codex_Gif/`, `packages/Codex_Github/`, and `packages/Codex_Batch_Image/`.

Do not add new implementation scripts, project directories, generated output, or standalone design documents to the repository root. Before completing any change, run `scripts/maintenance/test-project-structure.ps1`. Structural changes must update the structure document, README, validation allowlist, path references, and both repository/global guidance when applicable.

## Batch Image Generation Routing

For grouped image candidates, multiple redraws, requests such as `每组生成5张` or `10路并发生图`, and numbered selection boards, use the globally registered `batch-image-generation` skill. Require an explicit supported ratio and paid-batch confirmation. Submit only through `generate_image` and the unified Media Router. Its deterministic scheduler replaces child-Agent generation for this workflow: use at most 10 in-flight tasks, start real submissions at least one second apart, estimate one minute per concurrent wave and use 1.5 times that estimate as the default dispatch deadline, start no new tasks after that deadline, wait up to 120 additional seconds only for already-running tasks, then mark remaining running tasks failed and continue to fixed-slot contact sheets without automatic visual or size QA.

## Codex Flow Business Skill Routing

When a user wants a governed creative business workflow for image, video, mixed media, or GUI/DAG work, use the globally registered `codex-flow` entry first. Select the Skill from the user's creative goal, confirm the formal Skill name and required execution settings, and let Codex Flow manage package validation, workflow gates, project state, approvals, invalidation, and capability routing.

Codex Flow business Skills describe creative intent and quality rules only. They must not choose providers, real model versions, polling, downloads, or retry paths. Image execution still requires an explicit supported ratio before any `generate_image` call; multi-scene or multi-candidate image work still requires paid-batch confirmation and uses `batch-image-generation`. Video Prompt V1 belongs to the selected business Skill, and user-requested V2+ revisions go through Codex_DT before unified `generate_video` execution.
