---
name: tool-scout
description: Find existing software tools across GitHub, npm, MCP, Agent Skills, VS Code Marketplace, Open VSX, and web search before building from scratch.
---

# Tool Scout

Use this Skill when the user or AI has a clear software-tool need but does not know which tool type can solve it.

## Trigger Conditions

Trigger this Skill when any of the following are true:

- The user asks to find a tool, software, open-source project, library, plugin, extension, MCP server, Skill, Agent, SaaS tool, API, automation, CLI, bridge, integration, or alternative.
- The user says or implies: "is there an existing tool?", "do not reinvent the wheel", "find a ready-made solution", "what can solve this?", "which tool should I use?", "有没有现成工具", "找一个工具", "不要重复造轮子".
- The AI is about to build a feature or project and can reasonably infer that an existing external tool may solve a meaningful part of it.
- The task mentions tool types but the correct type is unclear, for example Skill vs MCP vs Agent vs GitHub repo vs extension.
- The task involves integration, bridge, workflow automation, local agent control, file conversion, content capture, browser automation, dev tooling, or AI workflow tooling.

Do not trigger this Skill for:

- A known exact package lookup where the user already named the tool and only wants docs.
- A normal coding task where no external tool choice is relevant.
- A pure knowledge question that is not about software tools.
- A high-stakes legal, medical, or financial recommendation.

## Goal

Return a ranked shortlist of existing tools that can solve the user's stated job, not a generic directory dump.

The user does not need to know whether the answer is a Skill, MCP server, Agent, GitHub repo, npm package, VS Code extension, Open VSX extension, SaaS product, or paid tool. Tool Scout should search across types.

## Process

1. Restate the job to be done in one sentence.
2. Extract hard constraints:
   - actor or controller
   - target system
   - direction of control or data flow
   - required platform
   - local vs hosted preference
   - free/open-source preference
3. If the request is an add-on, helper, plugin, overlay, automation, workflow, or integration for a named product, run a **native feature audit before external competitor search**:
   - Check official docs, help center, release notes, and changelog.
   - Inspect or ask the user to inspect the current product UI: selected text actions, right-click/context menu, hover menu, toolbar, side panels, command palette, slash commands, and keyboard shortcuts.
   - Check whether extension/plugin/API/custom-command support already covers the job.
   - Treat native capability as a first-class "existing tool"; if it solves 70%+ of the job, say so before recommending external tools.
   - Do not assume a product lacks a feature just because external search results are stronger.
4. Generate multiple query families:
   - user wording
   - developer wording
   - capability wording
   - product type wording
   - English and Chinese synonyms where relevant
   - source-specific wording, such as `in:readme`, `MCP server`, `VS Code extension`, `npm package`
5. Run searchers in parallel.
6. Normalize and deduplicate candidates.
7. Apply V0/V1 gates:
   - V0: source exists and is not obviously dead.
   - V1: description, README-level content, metadata, or tool schema shows evidence that it can solve the task.
8. Rank only candidates that pass V0/V1.
9. Explain the ranking in plain language, including whether native product functionality already covers the need.

## Command

From this Skill directory:

```bash
python3 scripts/tool_scout.py "USER_TOOL_NEED"
```

Recommended full run:

```bash
python3 scripts/tool_scout.py "USER_TOOL_NEED" --limit 10
```

Machine-readable output:

```bash
python3 scripts/tool_scout.py "USER_TOOL_NEED" --json
```

Limit to explicit sources:

```bash
python3 scripts/tool_scout.py "USER_TOOL_NEED" --sources github,npm,vscode,openvsx,mcp,glama,agentskill,web
```

## Searchers

First-version searchers:

- GitHub repository search
- npm registry search
- Official MCP Registry
- Glama MCP directory
- OpenAgentSkill API
- agentskill.sh API
- VS Code Marketplace
- Open VSX Registry
- Brave Search if `BRAVE_API_KEY` is configured
- Jina search as a best-effort fallback

Optional keys:

- `GITHUB_TOKEN`
- `SMITHERY_API_KEY`
- `PULSEMCP_API_KEY`
- `BRAVE_API_KEY`

## Ranking

Only V0/V1-passing candidates are ranked.

- Goal match: 45%
- Evidence strength: 20%
- Project quality: 20%
- Landing friction: 10%
- Multi-source corroboration: 5%

When presenting results, include:

- tool name
- type
- source URL
- why it matches
- V0/V1 status
- ranking explanation
- known caveats

## Output Style

Lead with the best candidates. Keep the first screen short.

Use this shape:

```text
I found N credible candidates. Top choices:

1. Tool name - type - why it is ranked first
2. Tool name - type - why it is ranked second
3. Tool name - type - why it is ranked third

Rejected or lower-confidence results:
- Name - why it did not pass V1 or why it is less relevant
```
