---
name: codex-flow
description: 统一的 Codex 创意技能平台入口，用于承接图片、视频、音频、剪辑和 GUI/DAG 工作流的统一路由与治理。
---

# Codex Flow

Codex Flow is the public platform entry for unified creative-skill workflows.

## Core task

- Route a user request to the appropriate creative workflow.
- Keep business intent, workflow stage, and execution capability separated.
- Load only the minimum required reference material for the current stage.
- Use the platform registry and project state to avoid duplicate work.

## Operating rules

1. Keep business skill content lightweight.
2. Keep media capability behavior in the platform layer.
3. Keep approval and publication centralized.
4. Keep provider, model, and execution details out of business-level skill text.
5. Keep staged workflows precise about dependencies and invalidation.

## Image Routing

For an image request, use the compiled registry fast path before loading any
Skill body or reference corpus. The searchable `skills` records use one compact
template shape for local Skills and community templates. A high-confidence match
is resolved through the separate runtime layer before execution. Otherwise enter
`generic-image`.

The generic path produces a model-neutral ImageSpec. Only consult the local
community template and case index when the route marks it as recommended. It must preserve the
target image's content and composition while treating a style reference as
visual language only. The downstream unified image router owns provider-specific
compilation and paid execution; require an explicit supported image ratio before
that execution.

## Stage guidance

- `brief`: collect the task goal and missing inputs.
- `concept`: prepare candidate directions or reference assets.
- `production`: run the selected capability with the confirmed settings.
- `final`: validate outputs and confirm delivery.

This file is only the public entry stub for now. The platform implementation will
expand beneath `platform/` as the migration proceeds.
