# Workspace Deployment Triggers

## Proactive Sub-Agent Delegation

When a task contains two or more concrete, bounded, and substantially independent workstreams, proactively prefer sub-agent delegation to reduce wall-clock completion time. Delegate only when the main agent can continue useful work concurrently, scopes are clear, synchronization is limited, and agents will not edit the same files or shared state. Keep the main agent responsible for integration, verification, safety checks, and the final answer. Do not delegate small or inherently sequential tasks, or when coordination overhead, file conflicts, authorization, or skill instructions outweigh the parallel benefit. Use only as many agents as provide meaningful parallelism.

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
- packaged projects currently live in `packages/Codex_image/`, `packages/Codex_DT/`, `packages/Codex_Gif/`, `packages/Codex_Github/`, `packages/Codex_CS/`, and `packages/Codex_Batch_Image/`.

Do not add new implementation scripts, project directories, generated output, or standalone design documents to the repository root. Before completing any change, run `scripts/maintenance/test-project-structure.ps1`. Structural changes must update the structure document, README, validation allowlist, path references, and both repository/global guidance when applicable.

## Batch Image Generation Routing

For grouped image candidates, multiple redraws, requests such as `每组生成5张` or `10路并发生图`, and numbered selection boards, use the globally registered `batch-image-generation` skill. Require an explicit supported ratio and paid-batch confirmation. Submit only through `generate_image` and the unified Media Router. Its deterministic scheduler replaces child-Agent generation for this workflow: use at most 10 in-flight tasks, start real submissions at least one second apart, estimate one minute per concurrent wave and use 1.5 times that estimate as the default whole-batch deadline, permanently abandon unfinished tasks without query or retry, collect only landed successes, and create fixed-slot contact sheets for human review without automatic visual or size QA.

## Video Business Skill Routing

When a user wants to use a governed business Skill to create a video, use the globally registered `video-skill-router` first. Confirm the Skill name, ratio, and duration before creating the contract-slot project. Each Skill contract must declare per-slot pacing rules, and project creation derives the planned material count from the confirmed duration; never use one global images-per-second rule. The selected CS Skill authors prompt V1. Any user-requested revision automatically goes to Codex_DT: explicit/local edits skip the corpus, while ambiguous, creative, or structural edits may inspect at most three relevant examples. Every prompt version requires user confirmation before unified video generation. Do not choose the Skill primarily from materials already supplied.
