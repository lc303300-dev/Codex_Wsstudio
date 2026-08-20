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
python platform/cli.py route "将目标图按参考图风格重绘"
python platform/registry.py resolve reference-style-redraw
python platform/style_library.py sync
python platform/style_library.py lookup "水彩插画风格"
python platform/style_library.py cases "水彩插画风格的城市美食地图"
python -m pytest tests
```

The registry compiler writes to `.codex-flow-private/compiled/registry.json` by
default. That path is ignored by Git.

`route` is the fast lookup path for image requests. It uses only compact
template-shaped records and never opens full Skill bodies or reference
libraries. Local business Skills and `awesome-gpt-image-2` templates are
compiled into the same record shape; route confidence, rather than source,
decides a match.
`generic-image` is the sole fallback. It marks community consultation as
recommended only for requests that mention reference images, style transfer,
redraws, layouts, or visual language. Provider-specific prompt formats remain
downstream of this decision in the unified image router.

The compiled registry has two layers: `skills` contains compact searchable
records, while `runtime` contains local entry paths, references, workflow
metadata, and package hashes. Community records resolve to template IDs and
corpus evidence instead of local files. Use `registry.py resolve <skill-id>`
after routing to obtain the runtime layer.

The generic image fallback produces a provider-neutral `ImageSpec` before
calling the unified image router. `style_library.py sync` downloads the MIT
licensed template index and parses the upstream gallery into the ignored private
runtime directory. The 22 templates are unified Registry records; the available
full cases are attributed retrieval evidence loaded only after a route is chosen.
The current upstream gallery omits the bodies for IDs 12, 169, and 170; this is
recorded in the sync manifest instead of being silently fabricated.
