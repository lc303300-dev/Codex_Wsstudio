# Codex Flow Workflow

Codex Flow supports two workflow profiles:

- `simple`
- `staged`

Supported gate types:

- `none`
- `decision`
- `approval`
- `paid-execution`
- `batch-approval`

Approvals bind to the current artifact hashes and become invalid when dependent
inputs change. Automatic checks are shown together with the artifact review
instead of creating a separate user gate.
