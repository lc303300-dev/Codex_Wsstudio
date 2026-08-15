# Codex_CS Skill Governance

Read and write Chinese text as UTF-8. Treat this repository as a provider-neutral
business-Skill authoring system. Do not add provider CLIs, credentials, model
selection, polling, downloading, or paid submission implementations.

All video business Skills must enter through `codex-cs-skill-curator`. A Skill is
discoverable only after it has a valid standard package and an `intake-receipt.json`
whose package hash matches the current files. Directly dropping a Markdown file into
`business-skills/` is not a supported publication path.

When a user wants to use a business Skill to create a video, run the local
`video-skill-router` workflow first. Select the Skill from the user's creative intent
(purpose, subject, style, narrative, and shot pattern), not primarily from materials
they already possess. After selection, read that Skill's `contract.json` and guide the
user to provide every required reference slot before Codex_DT authoring begins.

Preserve source experience without promoting every source statement to a hard rule:

- deterministic input and binding facts belong in `contract.json`;
- essential operating instructions belong in `SKILL.md`;
- professional creative knowledge belongs in `references/creative-guidance.md`;
- community knowledge belongs in `references/community-experience.md`;
- known defects and mitigations belong in `references/failure-cases.md`;
- examples belong in `references/examples.md` and never define the contract.

Every video Skill must require at least one image, video, or audio reference. Do not
publish `text2video` contracts. Business Skills must not select a provider or actual
generation model. Model/version mentions from source material may be retained only as
clearly labelled provenance or historical context in reference documents.

Before publishing or changing a business Skill, run:

```powershell
python .\codex-cs-skill-curator\scripts\validate_skill_package.py <skill-directory>
```
