# Codex Flow Phase 0 Inventory

Date: 2026-08-19

This inventory records the starting point for the Codex Flow migration. It does
not authorize deletion of the legacy CS/IS systems.

## Baseline

- Repository update check: passed.
- Project structure check: passed.
- Regression tests: 92 passed.
- Initial dirty worktree item resolved before Codex Flow changes continued.
- Phase 1 starter tests after adding validator/compiler: 99 passed.
- Phase 1 approval/release/project tests after adding hash-bound publishing
  and project idempotency: 102 passed.

## Current packages

- `packages/Codex_image/`: unified image and video media router.
- `packages/Codex_DT/`: video prompt collaboration and Seedance policy.
- `packages/Codex_Gif/`: video-to-GIF tooling.
- `packages/Codex_Github/`: external tool discovery workflow.
- `packages/Codex_Batch_Image/`: deterministic batch image scheduler.
- `packages/Codex_CS/`: legacy governed video business-skill system.
- `packages/Codex_IS/`: legacy governed image business-skill system.
- `packages/Codex_Flow/`: new unified creative-skill scaffold.

## Legacy migration sources

Video business skills under `packages/Codex_CS/business-skills/`:

- `architectural-assembly-reveal`: migrated
- `city-real-estate-habitat-promo`: migrated
- `dawn-mist-aerial-real-estate`: migrated
- `giant-3d-logo-landmark-video`: deprecated; latest legacy intake state is
  `ready_for_approval` with `user_approval.approved=false`
- `giant-ip-landmark-parade`: migrated
- `sci-fi-city-promo`: migrated

Image business skills under `packages/Codex_IS/business-skills/`:

- `scene-storyboard-grid`: migrated

## Legacy execution surfaces

- `packages/Codex_CS/video-skill-router/`
- `packages/Codex_CS/codex-cs-skill-curator/`
- `packages/Codex_CS/material-collection/`
- `packages/Codex_CS/project-pipeline/`
- `packages/Codex_CS/skill-registry/`
- `packages/Codex_IS/image-skill-router/`
- `packages/Codex_IS/image-skill-curator/`
- `packages/Codex_IS/project-pipeline/`
- `packages/Codex_IS/skill-registry/`

## Known residual references

The repository still intentionally contains executable and documentation
references to `Codex_CS`, `Codex_IS`, `video-skill-router`,
`image-skill-router`, `contract.json`, `routing.json`, `intake-report.json`,
`intake-receipt.json`, and `dt-request.json`.

These are migration targets, not acceptable final-state residuals.

## Next phase

Phase 1 has started with a lightweight validator, compiler, and focused tests.
The next increment should expand schema strictness and add approval/release
records before any legacy package is removed.
