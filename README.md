# Codex_Wsstudio

A Windows-first monorepo for Codex media tooling, image-to-video workflows, and reusable Codex configuration.

## Repository layout

```text
Codex_Wsstudio/
├─ config/codex/                 Portable Codex configuration
├─ docs/                         Repository-level documentation
├─ packages/
│  ├─ Codex_image/              Media tools, provider wrappers, and safety checks
│  ├─ Codex_Flow/               Unified creative-skill platform scaffold
│  ├─ Codex_DT/                 Dreamina/Seedance production workflow and prompt optimization
│  ├─ Codex_Gif/                Video-to-GIF package and global skill registration
│  ├─ Codex_Github/             Tool Scout discovery workflow
│  ├─ Codex_Batch_Image/        Timed concurrent image batches and human-review sheets
│  └─ Codex_Flow/               Unified governed creative-skill platform
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

The deployment synchronizes `config/codex/AGENTS.md` into the current user's global Codex
home. This includes the hard Windows local-resource contract: local Markdown links and images
use absolute forward-slash paths, never raw backslash paths or `file://` URIs, and reuse
tool-returned resource targets when available.

The same global guidance requires an explicit ratio for every image generation or edit. Missing
ratios are rejected before any provider submission instead of being inferred from references or
provider defaults.

Codex Flow is the unified creative-skill platform. Its public entry lives in
`packages/Codex_Flow/codex-flow/SKILL.md`, with migrated business Skills under
`packages/Codex_Flow/business-skills/`.

Image routes still use the configured serial fallback order by default. If the user explicitly
names one supported, unambiguous route, the unified `generate_image` tool can go directly to that
route and will not try other routes. Codex does not proactively ask ordinary users to choose one.

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
