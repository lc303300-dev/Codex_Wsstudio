# Codex_Flow Package Rules

This package is the new unified creative-skill platform scaffold.

## Current scope

- Keep the public entry in `codex-flow/SKILL.md`.
- Keep platform implementation under `platform/`.
- Keep package-local documentation and tests under this package.
- Keep runtime state and generated artifacts outside Git.

## Migration stance

- Do not add compatibility copies of legacy intake, receipt, or routing formats.
- Keep one-time migration history in repository docs, not runtime business skills.
- Keep this package small and test-backed as platform capabilities are added.

## Editing notes

- Use UTF-8 for Chinese text.
- Keep local paths absolute when referenced from Markdown.
- Prefer repository scripts and shared utilities over one-off ad hoc files.
