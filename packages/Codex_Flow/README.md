# Codex_Flow

Codex_Flow is the planned unified creative-skill platform for Codex_Wsstudio.
This package owns the public entry surface, migrated business-skill library,
registry compilation, approval/release records, project-state helpers, and
cutover checks.

Initial scope:

- one public Skill entry at `codex-flow/SKILL.md`;
- one package-level operating guide in `AGENTS.md`;
- a platform workspace for schemas, routing, workflow, and project state;
- a migration path that can later absorb image, video, audio, edit, and GUI/DAG
  capabilities under one registry.

The platform is intentionally compact and test-backed. Additional capabilities
should extend the existing validator, registry, approval, and project modules
instead of reintroducing media-specific business-skill systems.

## Local commands

```powershell
python platform/cli.py validate business-skills/<skill-id>
python platform/cli.py review <draft-skill> --source-hash <sha256>
python platform/cli.py approve .codex-flow-private/reviews/<review-id>.json
python platform/cli.py publish <draft-skill> --review .codex-flow-private/reviews/<review-id>.json --approval .codex-flow-private/approvals/<approval-id>.json
python platform/cli.py build
python platform/cli.py lookup "poster"
python -m pytest tests
```

The registry compiler writes to `.codex-flow-private/compiled/registry.json` by
default. That path is ignored by Git.
