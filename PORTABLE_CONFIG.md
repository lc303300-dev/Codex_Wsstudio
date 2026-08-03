# Portable Codex configuration

`codex-global/config.portable.toml` contains settings that are safe to share between computers.
`setup-codex.ps1` merges those settings into the current machine's Codex config.

The installer deliberately preserves machine-generated sections such as:

- `notify`
- `marketplaces.*`
- `mcp_servers.node_repl` and its runtime hashes or pipe names
- existing MCP servers
- existing `projects.*` trust records
- `shell_environment_policy.*`

Run on each computer after cloning or pulling this directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-codex.ps1
```

Preview without writing:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-codex.ps1 -WhatIf
```

If `cn-housing-mcp` is stored in a nonstandard location, pass its directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-codex.ps1 -CnHousingRoot D:\path\to\cn-housing-mcp
```

The script creates a timestamped backup before changing an existing config. The machine-local
`config.toml` lives under `CODEX_HOME` and is not part of this project repository.
