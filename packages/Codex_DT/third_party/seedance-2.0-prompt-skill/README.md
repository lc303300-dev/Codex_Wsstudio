# Seedance Prompt Engineering Skill

[日本語](README.ja.md)

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Seedance 2.0](https://img.shields.io/badge/Seedance-2.0-111827.svg)](https://seed.bytedance.com/en/seedance2_0)
[![Codex Skill](https://img.shields.io/badge/Codex-skill-10A37F.svg)](build-seedance2-prompts/SKILL.md)

An evidence-backed Codex skill for building production-ready **Seedance prompts** across Dreamina, BytePlus ModelArk, Volcengine, Fal, Higgsfield, and other provider surfaces. In Codex_Wsstudio, the default path is Seedance 2.5, 480P, all-around reference mode, 4-30 seconds, and up to 50 total reference content items.

Stop re-explaining `@Image 1`, `@Video 1`, `@Audio 1`, first/last-frame roles, edit wording, shot structure, or provider-specific tag spelling. Give the creative brief and reference assets; the skill compiles the prompt, asset map, settings, and preflight checks.

This is not another prompt dump. It is a **role-aware prompt compiler and linter** for text-to-video, image-to-video, multimodal reference generation, dialogue, product advertising, video editing, extension, and clip transitions.

## Why this skill

| Common failure | What the skill does |
|---|---|
| A motion-reference video also leaks its person, palette, or audio | Assigns one primary job plus explicit `must_not_transfer` rules |
| `@Image1`, `@Image 1`, `[Image 1]`, and `@图片1` are treated as universal syntax | Stores neutral `image:1` IDs and compiles tags for the active surface |
| A reference image is confused with an exact first frame | Separates prompt labels from API transport roles such as `first_frame` and `reference_image` |
| Short clips contain too many cuts, actions, and camera moves | Routes by temporal/spatial density and keeps one primary camera move per shot |
| Video edits accidentally regenerate unrelated content or audio | Uses direct edit/extend wording and names every invariant |
| Community folklore is presented as official behavior | Separates official rules, provider behavior, practitioner evidence, and conservative heuristics |

## Core capabilities

- Seedance 2.5, 480P, all-around reference mode by default in Codex_Wsstudio; provider-specific variants only when requested or required.
- Japanese or English prompts without forcing translation.
- `vibe-explore`, `balanced`, and `precision` control lanes.
- Text-to-video, first-frame, first-and-last-frame, multimodal reference, edit, extend, and stitch modes.
- Image identity/product/composition roles; video motion/camera/timing/effect roles; audio voice/music/rhythm/ambience roles.
- Chronological `Shot 1 / Shot 2 / Shot 3` construction for complex clips.
- Dialogue, sound effects, music, subtitles, logos, and generated-text conflict handling.
- Provider-neutral asset manifest with transfer and do-not-transfer fields.
- Static validation for media limits, missing references, role conflicts, prompt density, camera stacking, unsupported controls, and contradictory constraints.

## Reference syntax by surface

The prompt tag is not the transport role. The actual upload slot or API `role` remains authoritative.

| Surface profile | Image 1 | Video 1 | Audio 1 |
|---|---|---|---|
| Dreamina | `@Image 1` | `@Video 1` | `@Audio 1` |
| Volcengine / Jimeng Chinese UI | `@图片1` | `@视频1` | `@音频1` |
| BytePlus API-facing prose | `[Image 1]` | `[Video 1]` | `[Audio 1]` |
| Fal | `@Image1` | `@Video1` | `@Audio1` |
| MuAPI | `@image1` | `@video1` | `@audio1` |
| Higgsfield | `@Image 1` | `@Video 1` | `@Audio 1` |

Provider behavior changes. The skill preserves a real UI mention token and asks for a live schema check before emitting exact paid-submission fields.

## Install for Codex

### PowerShell

```powershell
git clone https://github.com/mqrox/seedance-2.0-prompt-skill.git
Copy-Item -Recurse -Force .\seedance-2.0-prompt-skill\build-seedance2-prompts "$HOME\.codex\skills\"
```

### macOS / Linux

```bash
git clone https://github.com/mqrox/seedance-2.0-prompt-skill.git
cp -R seedance-2.0-prompt-skill/build-seedance2-prompts ~/.codex/skills/
```

If an older `build-seedance2-prompts` directory exists, back it up before replacing it. Restart or open a new Codex task if the skill list does not refresh immediately.

## Usage

Codex can trigger the skill from a normal Seedance 2.0 request. To invoke it explicitly:

```text
$build-seedance2-prompts

Image 1 is the actor, Image 2 is the product packshot, Video 1 is camera motion only,
and Audio 1 is voice timbre only. Build a 12-second 9:16 premium skincare ad
with the Japanese line: 「光は、肌の奥から。」
```

For an exact video edit:

```text
$build-seedance2-prompts

Using Fal Seedance 2.0, replace only the blue mug visible from 00:04–00:06
in Video 1 with a plain white ceramic mug. Preserve the people, hands, lighting,
camera, original audio, and total 8-second duration.
```

For open-ended text-to-video:

```text
$build-seedance2-prompts

A short vertical film: two adults part at a rainy railway station at night,
then turn back for one brief look. No reference assets. Make it emotionally restrained.
```

The default response contains:

1. a paste-ready Seedance 2.0 prompt;
2. asset upload order and one job per asset;
3. model, mode, duration, ratio, resolution, and audio intent;
4. only material assumptions or provider caveats.

## Validate a prompt

```powershell
python build-seedance2-prompts/scripts/validate_prompt.py prompt.txt `
  --images 2 --videos 1 --audios 1 `
  --duration 12 --mode multimodal --surface dreamina --strict
```

For complex jobs, validate against an asset manifest:

```powershell
python build-seedance2-prompts/scripts/validate_prompt.py prompt.txt `
  --manifest assets.json --strict
```

The schema is available at [`asset-manifest.schema.json`](build-seedance2-prompts/references/asset-manifest.schema.json).

## Evidence policy

The skill prioritizes:

1. current ByteDance Seed, BytePlus, and Volcengine documentation;
2. the active provider's official schema or live UI behavior;
3. community and practitioner findings that agree with official behavior;
4. conservative heuristics, labeled as heuristics.

Primary references include the [Seedance 2.0 model page](https://seed.bytedance.com/en/seedance2_0), [BytePlus Prompt Guide](https://docs.byteplus.com/en/docs/ModelArk/2222480), [BytePlus video-generation API](https://docs.byteplus.com/en/docs/ModelArk/1520757), [Volcengine Prompt Guide](https://www.volcengine.com/docs/82379/2222480?lang=zh), and [Volcengine's official `sd2-pe` skill](https://arkdoc.tos-cn-beijing.volces.com/files/video-generation/SKILL.md).

See the versioned [evidence ledger](build-seedance2-prompts/references/evidence-ledger.md) for source classes, conflicts, GitHub/practitioner snapshots, excluded claims, and `last_checked` dates.

The downloaded official skill exposed no explicit reuse license. This repository therefore uses an independently structured and independently worded implementation instead of copying official prose or examples wholesale.

## What this project does not claim

- No universal optimum word count, shot count, or cast size.
- No invented `[AUDIO: 8s]`-style magic syntax.
- No guarantee that `4K`, `masterpiece`, or similar prose increases resolution.
- No universal provider attachment limits or tag spelling.
- No guaranteed lip-sync, typography, logo, timing, or identity accuracy.
- No filter-evasion, unauthorized-likeness, or copyrighted-character workarounds.

## Repository structure

```text
.
├── build-seedance2-prompts/   # installable Codex skill
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/
│   └── scripts/validate_prompt.py
├── .github/                   # structured issue forms
├── tools/validate_repo.py     # repository-level smoke test
├── CONTRIBUTING.md
├── CITATION.cff
└── LICENSE
```

## Contributing

Generation results, provider-schema corrections, failure cases, and evidence-backed prompt patterns are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Use the prompt-case issue form when sharing a reproducible generation result.

## Disclaimer

This is an independent, unofficial open-source project. It is not affiliated with, endorsed by, or sponsored by ByteDance, Seed, Dreamina, BytePlus, Volcengine, Fal, Higgsfield, or other providers. Product names and trademarks belong to their respective owners.

## License

[MIT](LICENSE) © 2026 Hideaki Nagata (`mqrox`).
