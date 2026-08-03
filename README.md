# Codex_Wsstudio

Codex_Wsstudio is a public workspace for a Codex-based media pipeline.

## What this repo includes

- `Codex_image/` - shared media tooling, provider wrappers, and safety checks.
- `Codex_DT/` - Dreamina/Seedance image-to-video pipeline and task workflow.
- `codex-global/` - portable Codex settings for a local Codex home.

## Requirements

- Git
- Python 3.11+
- PowerShell 7 or Windows PowerShell
- Node.js LTS if you want the full bootstrap path
- Provider API keys only for the services you actually use

## Key links

- `COMFLY_API_KEY` - [ai.comfly.org](https://ai.comfly.org/)
- `APIMART_API_KEY` - [apimart.ai/zh](https://apimart.ai/zh)
- `GEMINI_API_KEY` - [aistudio.google.com](https://aistudio.google.com/)

## Install

1. Clone the repository.
2. Copy [`.env.example`](.env.example) to `.env` if you want a single top-level place for local keys.
3. Copy [`Codex_image/.env.example`](Codex_image/.env.example) to `Codex_image/.env` and fill in the provider keys you use.
4. On a new machine, run [the deployment template](NEW_MACHINE_DEPLOYMENT_TEMPLATE.md) or:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-new-machine.ps1
```

## Start

Run this before writing files in this checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-task.ps1
```

That checks whether the checkout is up to date and only fast-forwards when it is safe.

This check is scoped to this Git checkout. Pure chat, public web/GitHub searches,
read-only tasks, projectless Codex directories, and unrelated repositories must not
run or search for this script. If a requested edit targets this repository but the
root script is missing, stop before writing and report the problem.

## Notes

- Secrets are not stored in Git.
- Local runtime data belongs under `.codex-image-private/`.
- Use the provided `.env.example` files as templates for local provider keys.
- For deployment details, see [DEPLOYMENT.md](DEPLOYMENT.md).
- For portable Codex settings, see [PORTABLE_CONFIG.md](PORTABLE_CONFIG.md).

## License

See [LICENSE](LICENSE).
