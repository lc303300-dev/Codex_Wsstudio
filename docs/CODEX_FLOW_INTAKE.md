# Codex Flow Intake

Codex Flow intake will normalize Markdown files, existing skill directories,
ZIP packages, legacy CS/IS packages, GUI/DAG skills, and prompt documents into
the unified lightweight skill standard.

Intake must not run source scripts, submit media jobs, or write provider
configuration into a business skill.

Planned checks include:

- required package files;
- duplicate and unreferenced resources;
- local path, credential, provider, model, and DAG pollution;
- workflow reachability and cycles;
- missing references;
- review-card hash binding before publication.

Starter commands:

```powershell
cd packages/Codex_Flow
python platform/cli.py review <draft-skill> --source-hash <sha256>
python platform/cli.py approve .codex-flow-private/reviews/<review-id>.json
python platform/cli.py publish <draft-skill> --review .codex-flow-private/reviews/<review-id>.json --approval .codex-flow-private/approvals/<approval-id>.json
```
