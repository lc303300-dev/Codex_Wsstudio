# Codex Flow Skill Standard

This repository will move to a single skill-package standard under Codex Flow.

## Minimum package

- `SKILL.md`
- `meta.yaml`

## Optional package pieces

- `workflow.yaml`
- `references/`
- `ui/`

## Principles

- Keep business skills focused on creative intent.
- Keep provider, execution, and approval logic in the platform.
- Keep staged workflows explicit about dependencies and invalidation.
- Load only the references needed for the current stage.

## Validation

```powershell
cd packages/Codex_Flow
python platform/cli.py validate business-skills/<skill-id>
python platform/cli.py build
```

The current validator enforces the minimum package files, staged workflow
presence, basic workflow dependency integrity, reference routing, duplicate
resources, and provider/model/DAG/credential pollution checks.
