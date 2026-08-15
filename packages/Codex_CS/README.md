# Codex_CS

This clean repository is being rebuilt around a governed, provider-neutral video
business-Skill library. The first completed component is
`codex-cs-skill-curator`, the mandatory intake and normalization workflow for all
existing and future video Skills.

`video-skill-router` provides the runtime half of the system: a generated local
SQLite/FTS5 registry selects a published Skill from the user's creative intent, then
`material-collection` turns the selected Skill's `contract.json` into a progressive
Chinese material checklist. The generated database stays under `.codex-cs-private/`.

Published business Skills will live in `business-skills/`. Uploaded originals,
staging output, review reports, projects, and other runtime data stay outside Git
under `.codex-cs-private/` or ignored staging directories.
