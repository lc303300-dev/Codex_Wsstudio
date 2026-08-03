# Contributing

Thank you for helping improve the Seedance 2.0 Prompt Engineering Skill.

## Good contributions

- a current official Seedance 2.0 or provider-schema correction;
- a reproducible prompt failure with surface, mode, duration, asset roles, and observed result;
- a prompt pattern tested across more than one generation;
- a validator rule that catches a real contradiction without blocking valid creative work;
- language improvements that preserve technical meaning.

## Evidence requirements

For behavioral or capability claims, include:

1. source URL;
2. source class: official, provider-official, practitioner-tested, or heuristic;
3. date checked;
4. affected surface and model variant;
5. whether the claim changes a hard rule, adapter, warning, or example.

Do not present stars, views, likes, or one successful generation as universal model proof. Do not copy substantial official or community prose when its reuse license is absent or unclear.

## Pull requests

- Keep the installable skill inside `build-seedance2-prompts/`.
- Keep public project documentation at repository root, not inside the skill folder.
- Update `references/evidence-ledger.md` when a source or conflict resolution changes.
- Update `last_checked` only for sources actually re-verified.
- Run `python tools/validate_repo.py` before submitting.
- Keep one logical change per pull request when practical.

## Generation evidence

Remove private files, credentials, personal data, and unauthorized likenesses before sharing. State whether the result can be redistributed. A screenshot or clip is helpful but never required when the prompt and failure are reproducible.

## Safety and rights

Do not contribute filter-evasion methods, unauthorized-likeness workflows, copyrighted-character workarounds, deceptive endorsements, or claims that a provider guarantees exact identity, typography, audio, or timing.
