# Codex_IS

Codex_IS is the governed image-business Skill layer for Codex_Wsstudio. It owns intent routing, per-Skill material contracts, prompt authoring and confirmation, and auditable project state. Paid image execution remains in the unified `generate_image` layer; deterministic multi-candidate work remains in `batch-image-generation`.

V0 ships one published business Skill, `scene-storyboard-grid`, plus:

- `image-skill-router/` for the user-facing workflow;
- `image-skill-curator/` for source intake, anti-generalization review, schema validation, user approval, and atomic publication;
- `skill-registry/` for validated intent lookup;
- `project-pipeline/` for contract-derived material slots, hashes, prompt versions, confirmation, and dry-run execution manifests;
- `shared/schemas/` for the platform-wide contract schema;
- `tests/` for contract, state invalidation, registry, and dry-run coverage.

Private runtime data is created under `.codex-is-private/` and is ignored by Git.

## Local commands

```powershell
python skill-registry/scripts/registry.py build
python skill-registry/scripts/registry.py lookup "九宫格分镜"
python image-skill-curator/scripts/scaffold_business_skill.py my-image-skill --output .codex-is-private/drafts
python project-pipeline/scripts/project_pipeline.py create --skill-id scene-storyboard-grid --display-name "场景一致性九宫格分镜" --ratio 16:9 --candidate-count 1 --scene-count 1 --skill-confirmed
python -m pytest tests
```

Register the two public Skills globally with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\register-global-skills.ps1
```
