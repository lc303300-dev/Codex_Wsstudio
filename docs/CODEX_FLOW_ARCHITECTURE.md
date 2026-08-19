# Codex Flow Architecture

Codex Flow is the planned unified creative-skill platform for this repository.
It replaces the split `Codex_CS` and `Codex_IS` model with one shared package
standard, one registry, one approval path, one project manifest, and one
workflow engine.

## Current status

- The package scaffold exists at `packages/Codex_Flow/`.
- A minimal package validator and registry compiler now exist under
  `packages/Codex_Flow/platform/`.
- Legacy `Codex_CS` and `Codex_IS` content has been migrated into
  `packages/Codex_Flow/business-skills/`; one unapproved legacy Skill is
  documented as deprecated.
- This document is the migration starting point, not the cutover record.

## Immediate next steps

1. Expand the schema validation beyond the current starter fields.
2. Add intake, approval, release, and project-state code.
3. Define capability adapters for image, video, audio, edit, and GUI/DAG.
4. Write migration checks for the existing CS/IS content.
5. Cut over the root docs and scripts once the platform is real.
