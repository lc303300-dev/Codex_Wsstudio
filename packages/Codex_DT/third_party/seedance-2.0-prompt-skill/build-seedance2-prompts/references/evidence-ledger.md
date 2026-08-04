# Seedance 2.0 evidence ledger

`last_checked: 2026-07-14`

This file records why a rule exists. It is not a popularity list. A star, view, like, or bookmark count shows attention, not correctness or independent expert consensus.

## Evidence classes

| Class | Meaning | Allowed use |
|---|---|---|
| A | ByteDance Seed, Volcengine, or BytePlus official model, prompt, API, or skill material | capability, limit, transport role, supported setting, official prompt behavior |
| B | official documentation for a third-party Seedance surface or a live provider schema | provider tag spelling, media slot, billing or submission behavior on that surface only |
| C | reproducible community implementation or practitioner test aligned with official behavior | workflow heuristic, failure prevention, production pattern; never relabel as official |
| D | local conservative inference | lint warning or default only; never present as a model guarantee |

If sources conflict, prefer current A over older A, A over B, and B over C for the named surface. Preserve the disagreement here rather than blending claims.

## Class A: current official foundation

| Source | Role in this skill | Freshness / note |
|---|---|---|
| [ByteDance Seedance 2.0 model page](https://seed.bytedance.com/en/seedance2_0) | official model identity and multimodal positioning | checked 2026-07-14 |
| [BytePlus Prompt Guide](https://docs.byteplus.com/en/docs/ModelArk/2222480) | current English prompt structure, modes, media behavior, shot guidance, notation | page updated 2026-07-07 |
| [BytePlus video-generation API](https://docs.byteplus.com/en/docs/ModelArk/1520757) | `content` order, media roles, settings, limits, unsupported controls | page updated 2026-06-29 |
| [Volcengine Prompt Guide](https://www.volcengine.com/docs/82379/2222480?lang=zh) | Chinese official counterpart and terminology cross-check | checked 2026-07-14 |
| [Volcengine Seedance 2.0 tutorial](https://www.volcengine.com/docs/82379/2291680?lang=zh) | current official skill installation and usage context | page updated 2026-07-07 |
| [Volcengine official `sd2-pe` skill](https://arkdoc.tos-cn-beijing.volces.com/files/video-generation/SKILL.md) | official prompt-optimizer baseline; this skill independently expands and resolves it | retrieved 2026-07-14; SHA-256 `8836CDB2BC4F7D8A329C4ECD33CCA19EFDCFC71AFDD927E8DEFE6E1F9A2E2B3C` |
| [BytePlus English `sd2-pe` skill](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/1a98a5a8685547568ed9ef257ceabe85~tplv-goo7wpa0wc-image.image) | shorter official baseline and conflict audit | retrieved 2026-07-14 |

The two official skill files expose no explicit reuse license. This implementation therefore re-expresses rules in original structure and language; it does not copy their prose or examples wholesale.

## Official-origin Vibe Creating material

- [ByteDance Lark practice handbook](https://bytedance.larkoffice.com/docx/FUHudm80VoGJRcxXykzcpNrQnj3)
- [ByteDance Lark prompt-skill draft](https://bytedance.larkoffice.com/docx/AVJddCKUmoj6j7x08jbcRBzon8b)
- [Independent bilingual port with attribution notice](https://github.com/Alisa0808/vibe-creating-skill)

The Lark pages redirected to login during the 2026-07-14 check. The port attributes the concept to ByteDance and contains eight worked cases, but it is not an official repository and does not provide a seeded, repeated, blind, or statistical comparison. Adopt the creative principle—describe the intended experience through visible and audible carriers—but do not claim Vibe is universally better than precision prompting.

## Strongest cross-source intersection

| Practice | Evidence | Core status |
|---|---|---|
| Number each modality independently by actual upload / `content` order | A | mandatory |
| Treat `@`/bracket labels as prompt references, not API transport roles | A | mandatory |
| Assign every asset one primary job and a readable alias | A + C | mandatory for multi-reference work |
| Separate image identity/composition, video motion/camera/timing, and audio voice/rhythm jobs | A + C | core |
| State what a reference must not transfer when contamination is plausible | C, consistent with A role binding | core production safeguard, not official syntax |
| Use chronological shots for compound events; do not assume exact timecodes are frame locks | current A + C | core |
| Prefer one primary camera movement and one coherent action beat per shot | A + C | core |
| Fit event density to duration instead of enforcing a fixed word count or shot count | A + C | core |
| Directly say edit or extend the named video for those operations | A | mandatory |
| Build a continuation from the accepted clip's actual end state | C | production safeguard |
| Change one failed variable first after reviewing a result | C | repair heuristic |

## Conflicts resolved by this implementation

| Disagreement | Resolution |
|---|---|
| Short official English `sd2-pe` uses unconditional `0–3s` slices; current guide warns precise timing is unstable | default to ordered `Shot N`; retain target windows only for edit or required sync |
| Official skill prose can include `4K`; API exposes resolution as a setting | keep resolution in settings; prose may describe visual detail but never promise resolution |
| UI guides show `@Image 1`, Chinese guide shows `@图片1`, API samples show `[Image 1]`, providers show no-space/lowercase forms | store neutral `modality:index`; compile with a surface profile |
| A prose image can suggest opening/ending composition, while API supports strict `first_frame`/`last_frame` roles | distinguish approximate reference intent from strict transport anchoring |
| Generic marketing describes rich audio, while current API output documents generated audio behavior more narrowly | report the active surface/API behavior and do not universalize channel claims |
| Community prompt lengths and shot-count rules differ | route by temporal/spatial density; no fixed optimum |
| Vibe and precision communities frame control differently | use `vibe-explore`, `balanced`, and `precision` lanes according to non-negotiables |

## Class C: market and practitioner evidence

### GitHub snapshot

Observed 2026-07-14; counts will drift.

| Repository | Snapshot | What it supports | Limitation |
|---|---|---|---|
| [Emily2040/seedance-2.0](https://github.com/Emily2040/seedance-2.0) | 4,253 stars, 659 forks, MIT, 187 commits; checked local commit `57d01dc66f93ecb03c2475be5f22dc416d9b701d` | surface profiles, evidence registry, continuation state, evaluation, domain modules | roughly two contributors and mostly author-driven PRs; interest is not consensus |
| [dexhunter/seedance2-skill](https://github.com/dexhunter/seedance2-skill) | 2,750 stars, 278 forks, MIT | strong demand for an installable prompt skill | older and comparatively inactive |
| [YouMind-OpenLab/awesome-seedance-2-prompts](https://github.com/YouMind-OpenLab/awesome-seedance-2-prompts) | 1,564 stars, 185 forks; license unclear | broad prompt corpus and use-case diversity | examples are not controlled evaluations |
| [MapleShaw/seedance2.0-prompt-skill](https://github.com/MapleShaw/seedance2.0-prompt-skill) | 630 stars, 88 forks, MIT | alternative skill packaging and prompt patterns | community implementation, not official approval |
| [Alisa0808/vibe-creating-skill](https://github.com/Alisa0808/vibe-creating-skill) | 103 stars, 15 forks | accessible Vibe Creating interpretation | independent port, not ByteDance product |

### Practitioner and social snapshot

| Source | Observed support | Safe takeaway |
|---|---|---|
| [OpenArt Seedance 2.0 handbook](https://openart.ai/blog/seedance-2-0-handbook/) | provider team tests; 2026-04-24 | bind each asset to a job, manage competing audio, match voice length, preserve storyboard logic |
| [Dan Kieft](https://www.youtube.com/watch?v=lkL8mlpVScY) | 71,204 views at check | fit events to duration, avoid excess shots, use coherent sequences |
| [Tao Prompts](https://www.youtube.com/watch?v=UHv61jUBx7M) | 64,361 views | state where references apply and use end frames for joins |
| [Creating with Conor](https://www.youtube.com/watch?v=SvhFnN-axJw) | 64,579 views | separate identity/key visual/motion-light roles |
| [Matt Loui](https://www.youtube.com/watch?v=-k6BAe27dDU) | 67,883 views | distinguish reference, start frame, and end frame; match duration |
| [PANDA-AI 60-camera test](https://www.bilibili.com/video/BV1BrSDBcEje/) | 13,741 views, 1,283 likes, 3,860 favorites | camera vocabulary is worth testing one variable at a time; individual words are not official guarantees |
| [Creative Bloq production interview](https://www.creativebloq.com/ai/how-a-filmmaker-turned-a-10-year-old-unmakeable-movie-idea-into-reality-with-ai) | reports 3,229 generations and 242 production hours | use character-state sheets, drafts, multiple takes, editing, and selective creative freedom |

## Claims deliberately excluded

- one universally optimal word count, shot count, or number of people;
- `[AUDIO: 8s]` or similar invented universal control syntax;
- unsupported percentage claims about bitrate, sync, identity, or prompt adherence;
- guessed internal attention, negative-embedding, or sampling behavior;
- automatic `4K, UHD, masterpiece, 8K, UE5` quality boosters;
- one attachment limit, duration range, resolution list, or tag spelling for every provider;
- guaranteed dialogue, lip-sync, typography, logo, or timing accuracy;
- filter evasion, unauthorized likeness, or copyrighted-character workarounds;
- repositories using “official” in a title without ByteDance/Volcengine/BytePlus provenance.

## Maintenance rule

Re-check Class A at least every 30 days, and check the active Class B provider immediately before paid generation. Record changed facts here with source, observed date, and the rule that changed. Do not silently overwrite a conflict history.
