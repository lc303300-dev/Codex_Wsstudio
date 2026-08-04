# Searcher Notes

Tool Scout treats each source as a separate searcher. Searchers should be run in parallel and merged after retrieval.

## First-Version Searchers

### GitHub Repo Search

Purpose:

- Open-source projects
- CLI tools
- bridges
- plugins
- Agent runtimes
- project READMEs that mention a capability but do not use the user's exact wording

Fields:

- repository name
- description
- README match when available
- stars
- forks
- topics
- language
- license
- archived flag
- last updated

Notes:

- Use `in:name,description,readme`.
- Query both precise phrases and broad capability wording.
- Sort by stars and updated time where useful.

### npm Registry

Purpose:

- Node CLIs
- MCP servers distributed as npm packages
- VS Code or agent helper packages
- JavaScript SDKs and bridges

Fields:

- package name
- description
- keywords
- version
- downloads
- updated date
- repository URL
- npm quality, popularity, and maintenance hints when returned

### Official MCP Registry

Purpose:

- trusted MCP server metadata
- package names and transport info
- environment variable requirements

Notes:

- Treat as high-trust but not high-recall.

### Glama MCP

Purpose:

- MCP discovery with richer metadata
- tool schemas, repository URLs, license, environment requirements

### Agent Skill Directories

Sources:

- OpenAgentSkill
- agentskill.sh

Purpose:

- Agent Skills, Claude Skills, Codex/Cursor reusable workflows
- workflow-like solutions that are not packaged as normal software

### VS Code Marketplace

Purpose:

- editor extensions
- Claude Code / Codex extensions
- bridge extensions that interact with local terminals

Fields:

- publisher
- extension name
- display name
- short description
- install count
- rating
- last updated

### Open VSX

Purpose:

- open extension registry
- VSCodium and non-Microsoft VS Code-compatible extensions

### Web Search

Purpose:

- catch migration notes, product pages, docs, marketplaces, and tools not indexed by structured registries
- find paid or hosted tools

Preferred:

- Brave Search if configured.
- Jina search/reader as best-effort free fallback.

## V0/V1 Gates

V0 pass:

- URL exists.
- Source item exists.
- Project is not obviously archived, deleted, or unavailable.

V1 pass:

- Description, README, metadata, package keywords, skill text, or MCP tool schema directly supports the user's job.
- Control/data direction is not contradicted.
- At least one hard constraint is clearly covered.

## Ranking Factors

Only candidates passing V0/V1 are ranked.

- Goal match: directness, direction, hard constraints.
- Evidence strength: how explicit the source evidence is.
- Project quality: stars, downloads, update recency, license, docs, release metadata.
- Landing friction: free/open source, local use, setup complexity, need for API keys or public network.
- Multi-source corroboration: same tool found in multiple sources.

