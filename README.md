# Codex_Wsstudio

A Windows-first monorepo for Codex media tooling, image-to-video workflows, and reusable Codex configuration.

## Repository layout

```text
Codex_Wsstudio/
├─ config/codex/                 Portable Codex configuration
├─ docs/                         Repository-level documentation
├─ packages/
│  ├─ Codex_image/              Media tools, provider wrappers, and safety checks
│  ├─ Codex_DT/                 Dreamina/Seedance production workflow
│  ├─ Codex_Gif/                Video-to-GIF package and global skill registration
│  └─ Codex_Github/             Tool Scout discovery workflow
├─ scripts/
│  ├─ codex/                    Codex configuration synchronization
│  ├─ deployment/               Installation and deployment implementation
│  └─ maintenance/              Repository checks and maintenance
├─ AGENTS.md                     Repository operating rules
├─ new-machine-deploy.ps1        Stable one-click deployment entry
└─ start-task.ps1                Stable pre-change safety entry
```

The root stays intentionally small. See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for the rules enforced on future changes.

## Requirements

- Git
- Python 3.11+
- PowerShell 7 or Windows PowerShell
- Node.js LTS for the full bootstrap path
- Provider API keys only for services you use

## Deploy

On a new computer, run from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\new-machine-deploy.ps1
```

Before writing files in this checkout, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-task.ps1
```

This validates the standard layout, fetches the upstream branch, and only fast-forwards a clean checkout when safe.

## Documentation

- [Deployment](docs/DEPLOYMENT.md)
- [New-machine deployment template](docs/NEW_MACHINE_DEPLOYMENT_TEMPLATE.md)
- [Portable Codex configuration](docs/PORTABLE_CONFIG.md)
- [Project structure standard](docs/PROJECT_STRUCTURE.md)

Secrets and machine-local runtime data are excluded from Git. Use the provided `.env.example` templates and keep private media runtime files under `packages/Codex_image/.codex-image-private/`.

## License

See [LICENSE](LICENSE).
