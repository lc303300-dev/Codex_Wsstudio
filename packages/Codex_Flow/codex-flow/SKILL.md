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

## Stage guidance

- `brief`: collect the task goal and missing inputs.
- `concept`: prepare candidate directions or reference assets.
- `production`: run the selected capability with the confirmed settings.
- `final`: validate outputs and confirm delivery.

This file is only the public entry stub for now. The platform implementation will
expand beneath `platform/` as the migration proceeds.
