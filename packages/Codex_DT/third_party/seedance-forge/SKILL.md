---
name: seedance-forge
description: Reference library of 2,269 real-world Seedance 2.0 video-generation prompts with structural patterns and authored exemplars. Use this skill whenever the user mentions Seedance, drafts a video prompt, asks for an image-to-video (i2v) or text-to-video (t2v) prompt, plans a multi-shot AI video brief, or asks for help structuring a video generation prompt — even if they don't say "Seedance" by name. Provides a canonical skeleton, archetype templates, and a search script for finding similar real prompts with source attribution.
---

## What This Skill Does

This is a decoupled reference library of authored Seedance video-generation prompts sourced from real-world community corpora. It provides a canonical structural skeleton, independently tracked sources, archetype templates, and search over a rebuildable combined index. Every surfaced prompt includes source metadata where available so users can trace inspiration back to the original author or source project.

## When to Use

- Drafting a new Seedance 2.0 video prompt from scratch
- Refining or extending an existing prompt
- Looking up structural patterns (timestamped, prose narrative, section-header styles)
- Comparing author styles across the corpus
- Finding prompts similar to a target concept for inspiration
- Building a multi-shot or multi-scene video brief

## When NOT to Use

- Sora prompts (different platform conventions)
- Runway ML prompts (different platform conventions)
- Veo / VideoFX prompts (different platform conventions)
- Image generation prompts (Midjourney, DALL-E, Flux — different skill territory)
- General video scripting without AI generation context

## Core Workflow

1. Read `references/structure-guide.md` for the canonical skeleton and archetype templates.
2. Run `python scripts/search.py "<keywords>"` to fetch 3–5 matching real prompts from the combined source index.
3. Use matches as **scaffolds, not copy targets** — extract structural patterns, not literal phrasing.
4. Always cite the `sourceLink` or `source_project` of any prompt whose structure you echoed.

## Corpus Layout

All corpora live under `references/sources/<source_id>/`:

- `forge-original` — the original Seedance Forge CSV corpus.
- `youmind` — imported Chinese entries from YouMind OpenLab's `awesome-seedance-2-prompts`.
- `zerolu` — imported Chinese curated entries from ZeroLu's `awesome-seedance`.

`references/indexes/combined.index.jsonl` is a rebuildable search index generated from those sources. Do not treat it as the authoritative corpus.

## Output Format Conventions

Seedance community standards — apply these when drafting any prompt:

- Multi-scene prompts use `---` as scene separators
- Tech specs at top or bottom: framerate (24fps standard, also 30/60fps), resolution ("High definition"), duration (15s standard)
- Camera language: "wide shot", "tracking shot", "POV", "cut to", "match cut", "handheld", "FPV", "bird's-eye"
- Reference-image clauses: `@Image1`, `@img1`, "based on reference image (upper-body)"
- No-subtitles clause: "No subtitles" (include when relevant)
- Timestamped beats: "0:00-0:05:" or "0.0–4.0 sec" format for multi-beat sequences

## Search Tool Quick Reference

```
python scripts/search.py "keyword"                  # top 5 results
python scripts/search.py "keyword" --top 10         # top N
python scripts/search.py "keyword" --source zerolu  # source filter
python scripts/search.py --author "KANA"            # by author name
python scripts/search.py --min-length 1000          # long prompts only
python scripts/search.py --max-length 200           # short prompts only
python scripts/search.py --random 5                 # random samples
python scripts/search.py "keyword" --json           # JSON output for piping
```

## Exemplars

For 12–15 hand-picked exemplars across diverse styles (short/long, anime/cinematic/mini-game/realistic, single-shot/multi-cut), see `references/curated-examples.md`.
