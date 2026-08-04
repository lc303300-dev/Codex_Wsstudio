# Google Antigravity CLI

Official documentation:

- Getting started: `https://antigravity.google/docs/cli/getting-started`
- Installation and auth: `https://antigravity.google/docs/cli/install`

Installed binary from the project root: `.codex-image-private/bin/gemini-cli/agy.exe`

- Version verified at installation: `1.1.4`
- Windows installer: `irm https://antigravity.google/cli/install.ps1 | iex`
- Authentication occurs on first interactive `agy` launch and uses Windows Credential Manager.
- Automated invocations must use the bundled proxy wrapper.
- This route does not read an API key from `.env`.
