---
name: codex-dt-video-prompt
description: Act as the unified public Codex_DT entry for Dreamina/Seedance video generation. Use whenever the user asks to generate or test a video from text, images, video, or audio. Semantically normalize complete prompts without changing their meaning, and creatively optimize only incomplete, short, or structurally weak prompts. Local project AGENTS.md and explicitly named project skills still take priority.
---

# Codex DT Video Prompt

Use this skill as the public video-generation orchestrator. Use `default-video-generation` only as the downstream paid execution layer.

## Non-destructive prompt gate

Before reading a corpus, inspecting references for creative additions, or rewriting any text, classify the user's generation prompt:

- Treat it as **complete** when the user marks it as final/complete/ready to send, or when it already provides an executable subject and action, temporal or camera progression, visual/cinematography direction, and sufficient reference bindings for the supplied media.
- Treat it as **incomplete** only when essential generation intent is absent, contradictory, or too thin to submit reliably.
- When uncertain, prefer **complete**. A complete prompt receives only meaning-preserving normalization, never creative rewriting.

For a complete prompt, perform a narrow **semantic-preserving normalization** pass:

1. Preserve the actual meaning: subject identity, actions, causal relations, shot intent, timing/order, composition, style, emotion, continuity, constraints, audio requirements, and intended ending must remain unchanged.
2. Allow only execution-oriented corrections: normalize malformed reference labels such as `@图片1` or `@Image 1` to the active adapter's bare labels; align reference numbers with the actual ordered media; repair broken headings, separators, list structure, punctuation, and unambiguous professional-term mistakes; remove duplicated platform/tool instructions that add no creative meaning.
3. Do not add, remove, intensify, soften, reinterpret, summarize, translate, or reorder creative content. Do not append the default audio sentence, negative constraints, camera ideas, corpus techniques, or new visual details.
4. If a suspected correction is ambiguous or could change meaning, leave it unchanged and surface the issue instead of guessing.
5. Do not run the director or corpus as a source of creative additions. Use the adapter/compiler rules only to normalize labels and submission syntax.
6. Pass missing duration, ratio, resolution, model, and execution mode as structured tool parameters when known; do not inject them into the prompt.
7. Call `default-video-generation` with the normalized prompt and original ordered media. The user's generation request is the authorization to continue; do not add a second prompt-review confirmation unless required by a stronger local policy.

## Priority

- Follow the current workspace or project `AGENTS.md` first.
- Do not trigger this skill when a project-specific video pipeline applies, for example a Codex_CS project skill or another package-level image-to-video workflow.
- Use this skill for general workspaces where the user wants video generation from images, a short text idea, or both.
- Use this skill first whenever the agent needs to supplement, newly write, repair, optimize, or rewrite a video prompt before generation, unless stronger project-specific video pipeline guidance applies.
- If the prompt passes the complete-prompt gate or the user asks to bypass creative optimization, apply only semantic-preserving normalization and hand it to `default-video-generation`.

## Workflow

1. Run the non-destructive prompt gate. Stop the authoring workflow and submit unchanged when the prompt is complete.
2. For an incomplete prompt, read the user's ordered images, requested duration, ratio, style, camera motion, audio preference, and constraints.
3. If images are local raster files and visual understanding is needed, create previews with the configured Codex preview tool first; inspect only previews whose longest edge is at most 1024 px.
4. Use the local `video-director-prompt` skill as the platform-neutral authoring layer. Apply its blocking, first-frame, performance, camera, physics, lighting, audio, continuity, and community-technique guidance in proportion to the task. Keep professional English terms when they improve execution, with Chinese explanations where useful.
4. Before reading `third_party/seedance-forge`, decide whether the prompt is already strong enough to write directly.
   - Skip the corpus when the user has already fixed the subject, ordered references, duration, ratio, and main camera or motion path, and the task is mainly prompt polishing.
   - Read the corpus only when the prompt is under-specified, structurally weak, needs a comparable example, or the user explicitly asks for corpus-assisted drafting.
5. Treat corpus model/version fields as provenance metadata only. Extract portable directing and prompt-structure patterns; never select the generation model from a corpus match.
6. Write one concise Chinese video prompt suitable for the active Dreamina/Seedance adapter. Preserve the user's subject, identity, composition, duration, ratio, and motion preferences.
7. For ordered references, use bare Chinese labels tied strictly to input order: `图片1`, `图片2`, `视频1`, `音频1`, and so on. Do not write mention-chip forms such as `@图片1`, `@Image 1`, `@视频1`, or `@Video 1`.
8. Never reorder references by filename, visual layout, natural-language alias, or inferred importance. The ordered media list that will be passed to `default-video-generation` is authoritative.
9. Apply the local `build-seedance2-prompts` cleaning and reference-binding rules as the platform compiler. Keep model, resolution, reference mode, API fields, upload/tool-call wording, and system-rule prose out of the creative prompt body; collapse repeated requirements.
10. Default generation to Seedance 2.5. Use Seedance 2.0 only when the current user explicitly requests 2.0 or a supported 2.0 variant. Never infer 2.0 from the corpus, third-party folder names, examples, old manifests, capacity issues, or a failed 2.5 attempt, and never automatically fall back from 2.5 to 2.0.
11. Include camera movement, subject action, scene change, style, temporal progression, and constraints only when useful.
12. When the user did not specify audio, add `不生成音乐，仅生成音效。`
13. When the user asked for generation, call `default-video-generation` with the optimized prompt and original ordered media after the prompt is ready. If the user asked only for prompt writing or review, return the prompt without submitting.

## Optional References

For complex image-to-video prompt authoring, read these files from the Codex_DT checkout:

- `docs/codex_authoring_workflow.md`
- `docs/subagent_image_worker.md`
- `.claude/skills/video-director-prompt/SKILL.md`
- `third_party/seedance-forge/references/structure-guide.md`

Do not call Dreamina CLI directly. All paid submission must go through `default-video-generation` and the unified Media Router.
