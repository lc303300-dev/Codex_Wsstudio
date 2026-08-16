# Project structure standard

This repository is a monorepo. Its root is reserved for repository-wide metadata and stable human-facing entry points.

## Placement rules

| Content | Location |
| --- | --- |
| Product or independently deployable project | `packages/<project>/` |
| Repository-level documentation | `docs/` |
| Shared portable configuration | `config/<system>/` |
| Deployment implementation | `scripts/deployment/` |
| Codex configuration automation | `scripts/codex/` |
| Maintenance and validation | `scripts/maintenance/` |
| Project-specific tests, docs, config, and scripts | Inside that project under `packages/<project>/` |

Root files are limited to repository metadata, dependency and test-runner manifests, governance files, and stable entry scripts. New implementation scripts, design documents, outputs, caches, or project folders must not be added directly to the root.

## Stable entry points

- `start-task.ps1` remains at the root because all agents must run it before modifying this checkout.
- `new-machine-deploy.ps1` remains at the root as the one-click deployment command.
- Implementation behind these entry points belongs under `scripts/`.

## Enforcement

`scripts/maintenance/test-project-structure.ps1` validates required directories and the root allowlist. The root `start-task.ps1` runs this validation automatically before its Git safety check.

Every structural change must update all of the following in the same commit:

1. `docs/PROJECT_STRUCTURE.md`
2. `README.md`
3. root `AGENTS.md`
4. `config/codex/AGENTS.md` when global operating guidance is affected
5. `scripts/maintenance/test-project-structure.ps1`
6. any scripts and documentation containing affected paths

The workspace currently includes the following packaged projects:

- `packages/Codex_image/`
- `packages/Codex_DT/`
- `packages/Codex_Gif/`
- `packages/Codex_Github/`
- `packages/Codex_CS/`
- `packages/Codex_Batch_Image/`
- `packages/Codex_IS/`

Codex_CS keeps governed published packages in `business-skills/`, rebuildable intent
index code in `skill-registry/`, contract-driven collection logic in
`material-collection/`, the governed runtime state bridge in `project-pipeline/`,
and the global routing entry in `video-skill-router/`.

Codex_Batch_Image owns manifest scheduling, SQLite state, dispatch-deadline cutoff plus bounded completion grace,
successful-result collection, and numbered human-review sheets. Paid single-image
execution remains in Codex_image's unified Media Router.

Codex_IS keeps provider-neutral image business packages in `business-skills/`, validated intent lookup in
`skill-registry/`, contract-derived material slots and prompt confirmation in `project-pipeline/`, and the public
entry in `image-skill-router/`. Its private registry, materials, state, prompts, and results stay under
`.codex-is-private/`.

Do not create compatibility copies of moved implementation files at the root. If a root command must remain stable, keep a small forwarding entry script instead.
