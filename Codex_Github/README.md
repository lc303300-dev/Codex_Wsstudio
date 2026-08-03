# Codex_Github

This project-integrated pipeline packages the Tool Scout Agent Skill. It searches GitHub, npm, MCP directories, Agent Skill registries, extension marketplaces, and web sources for existing tools before implementation.

The deployment entry point is `register-global-skill.ps1`. The repository bootstrap and global synchronization scripts call it automatically, installing the skill as `tool-scout` under the active Codex home.
