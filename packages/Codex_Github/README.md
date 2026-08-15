# Codex_Github

Register or refresh the global Tool Scout skill after moving or updating this checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\packages\Codex_Github\register-global-skill.ps1
```

Registration replaces any previously managed copy and rewrites its source metadata to the current checkout path. The installed Skill is self-contained and always runs the bundled `scripts/tool_scout.py` relative to its own `SKILL.md`; the source metadata is used only to audit and refresh the installation.

This project-integrated pipeline packages the Tool Scout Agent Skill. It searches GitHub, npm, MCP directories, Agent Skill registries, extension marketplaces, and web sources for existing tools before implementation.

The deployment entry point is `register-global-skill.ps1`. The repository bootstrap and global synchronization scripts call it automatically, installing the skill as `codex-github` under the active Codex home.
