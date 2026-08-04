# Seedance Forge

<div align="center">

![Seedance 2.0](https://img.shields.io/badge/Seedance-2.0-FF6B35?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik04IDV2MTRsOC03eiIvPjwvc3ZnPg==)
![Prompts](https://img.shields.io/badge/Prompts-2%2C366-4CAF50?style=for-the-badge)
![Authors](https://img.shields.io/badge/Authors-797-9C27B0?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![stdlib only](https://img.shields.io/badge/deps-stdlib%20only-00BCD4?style=for-the-badge)
![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-D97706?style=for-the-badge)
![Codex CLI](https://img.shields.io/badge/Codex%20CLI-Compatible-00897B?style=for-the-badge)
![npm](https://img.shields.io/npm/v/seedance-forge?style=for-the-badge&logo=npm&logoColor=white&color=CB3837)

**A portable Agent Skill packaging 2,366 real-world Seedance 2.0 video-generation prompts.**  
Structural patterns. Authored exemplars. Source attribution. Zero dependencies.

[Install](#install) · [Invoke](#invoke-the-skill) · [Search](#search-the-corpus) · [Examples](#example-output) · [Structure](#folder-structure) · [Registries](#add-to-skill-registries)

</div>

---

## What It Does

When you're drafting a Seedance 2.0 video prompt, this skill:

1. **Surfaces the canonical skeleton** — the 5–7 sections real community prompts share
2. **Searches 2,366 authored prompts** by keyword, author, or length to find structural scaffolds
3. **Cites every source** — every matched prompt comes with its `sourceLink` back to the original author

It is a **reference library**, not a generator. It teaches structure, not words.

Works in **Claude Code** and **Codex CLI** from the same install.

---

## Install

> **Prerequisite:** Python 3.9+ · No `pip install` required — stdlib only.

### Option A — Claude Code (copy)

```powershell
$dest = "$env:USERPROFILE\.claude\skills"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force .\seedance-forge $dest
```

### Option B — Codex CLI (copy)

```powershell
$dest = "$env:USERPROFILE\.codex\skills"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force .\seedance-forge $dest
```

### Option C — Both, one canonical copy (recommended)

```powershell
# 1. Place canonical copy
$canonical = "C:\skills\seedance-forge"
Copy-Item -Recurse -Force .\seedance-forge C:\skills\

# 2. Symlink into both CLIs
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.claude\skills\seedance-forge" `
  -Target $canonical

New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.codex\skills\seedance-forge" `
  -Target $canonical
```

> **Windows symlink note:** Requires elevated PowerShell **or** Developer Mode on  
> `Settings → Privacy & security → For developers → Developer Mode = On`

### Option D — npm / npx (no git clone required)

> Requires Node.js 14+. Works on Windows, macOS, Linux.

```bash
npx seedance-forge
```

Installs into `~/.claude/skills/seedance-forge` and `~/.codex/skills/seedance-forge` automatically.  
Re-run anytime to update to the latest version.

Or install globally so it's always on `$PATH`:

```bash
npm install -g seedance-forge
seedance-forge   # run installer
```

### Verify

```powershell
Get-ChildItem "$env:USERPROFILE\.claude\skills\seedance-forge"
```

Expected output:
```
Mode    Name
----    ----
d----   references
d----   scripts
-a---   README.md
-a---   SKILL.md
```

---

## Invoke the Skill

### Claude Code

The skill auto-triggers whenever you mention Seedance, i2v/t2v prompts, or video briefs.  
You can also invoke explicitly:

```
/seedance-forge
```

Or just talk naturally — the skill description catches all these:

| You say | Skill activates |
|---|---|
| *"draft a Seedance prompt for a chef scene"* | ✅ |
| *"help me write an image-to-video prompt"* | ✅ |
| *"I need a multi-shot video brief"* | ✅ |
| *"Seedance 2.0 prompt for a transformation"* | ✅ |
| *"write me a Midjourney prompt"* | ❌ (different skill) |
| *"Runway prompt for rain"* | ❌ (different platform) |

### Codex CLI

```bash
codex "draft a seedance 2.0 video prompt for a blacksmith forging a sword"
# Skill loads automatically from ~/.codex/skills/seedance-forge/SKILL.md
```

---

## Search the Corpus

Run from inside the skill folder (`cd seedance-forge`):

```bash
# Keyword search — top 5 by weighted score (title×3, desc×2, content×1)
python scripts/search.py "stealth heist cave"

# Top N results
python scripts/search.py "ramen noodles" --top 10

# Filter by author
python scripts/search.py --author "KANA"

# Length filters
python scripts/search.py --min-length 1000          # long prompts only
python scripts/search.py "anime" --max-length 200   # short anime prompts

# Random samples (great for inspiration)
python scripts/search.py --random 5

# JSON output — pipe into jq, save to file, feed to another agent
python scripts/search.py "physics liquid" --json | jq '.[0].content_preview'
```

### Example Output

```
[1] id=3747 | len=1527 | "Stealth mini-game heist video prompt"
    by KANA — https://x.com/KanaWorks_AI/status/2048407984456519965
    A mini-game style stealth theft scene, with exaggerated, humorous actions and
    expressions. No subtitles. High definition, 30fps. A massive tengu-like yokai...
    [truncated at 300 chars]

[2] id=3619 | len=1336 | "Samurai vs Fire Yokai Storyboard"
    by Pierrick Chevallier | IA — https://x.com/CharaspowerAI/status/...
    An ultra charismatic samurai standing in a burning village, facing a massive
    fire yokai made of flames and smoke. A fire yokai attacks and destroys...
```

---

## Skill Workflow (what happens when it activates)

```
1. Read  references/structure-guide.md   ← canonical skeleton + 3 archetypes
        ↓
2. Run   python scripts/search.py "<your concept>"   ← 3–5 real scaffolds
        ↓
3. Extract structural pattern (not literal phrasing) from top matches
        ↓
4. Draft prompt using skeleton + camera language conventions
        ↓
5. Cite  sourceLink of any prompt whose structure was echoed
```

---

## Structural Archetypes

The skill provides three proven archetypes from the corpus:

| Archetype | Best for | Key marker |
|---|---|---|
| **Prose Narrative** | Single-scene, character-driven, atmospheric | Flowing sentences, no headers |
| **Timestamped Sequence** | Multi-beat action, precise timing | `0:00–0:05:` segments |
| **Bold-Header Structured** | Complex multi-element scenes, collaboration | `**Action:**`, `**Camera:**` |

Full templates with fill-in-the-blanks examples → `references/structure-guide.md`

---

## Corpus Stats

| Metric | Value |
|---|---|
| Total prompts | 2,366 |
| Unique authors | 797 |
| Median prompt length | 432 chars |
| Longest prompt | 7,929 chars |
| Shortest prompt | 20 chars |
| Use 15s duration | ~416 prompts |
| Use 24fps | 48 prompts |
| Style: cinematic | ~32% of corpus |

---

## Folder Structure

```
seedance-forge/
├── SKILL.md                    ← Skill definition (auto-loaded by Claude Code / Codex)
├── README.md                   ← This file
├── references/
│   ├── seedance-prompts.csv    ← Full 2,366-row corpus (~4 MB)
│   ├── structure-guide.md      ← Canonical skeleton + 3 archetypes + camera glossary
│   └── curated-examples.md     ← 13 hand-picked exemplars across all styles
└── scripts/
    ├── search.py               ← Stdlib CLI search tool (Python 3.9+, no deps)
    └── README.md               ← Install instructions
```

---

## Trigger Keywords

The skill auto-activates in Claude Code on any of:

`Seedance` · `seedance 2.0` · `image-to-video` · `i2v` · `text-to-video` · `t2v` · `video prompt` · `video brief` · `multi-shot` · `AI video`

---

## What This Skill Does NOT Do

- ❌ Generate prompts on its own — it surfaces structure, you write
- ❌ Access the internet or refresh the corpus
- ❌ Work for Sora / Runway / Veo / Kling (different platform conventions)
- ❌ Work for image generation (Midjourney, DALL-E, Flux)
- ❌ Require any `pip install`

## Attribution

All prompts in `references/seedance-prompts.csv` are authored by the Seedance community.  
Every search result surfaces the original author name and `sourceLink`.  
Use prompts as structural scaffolds only — do not copy verbatim without crediting the source.

---

<div align="center">

Built with the [oh-my-claudecode](https://github.com/anthropics/claude-code) team skill · Python stdlib · No dependencies

</div>
