---
name: build-seedance2-prompts
description: Build, rewrite, diagnose, or validate production-ready prompts specifically for ByteDance Dreamina/Doubao Seedance 2.0 Standard, including text-to-video, image-to-video, first/last-frame animation, multimodal image/video/audio references, dialogue and sound, multi-shot narratives, video editing, extension, and clip transitions. Use whenever the user mentions Seedance 2.0, Seedance2, Dreamina 2.0, Doubao video, @Image/@Video/@Audio references, or asks for a Seedance-ready video prompt; also use when adapting a creative brief, storyboard, script, image, video, audio asset, or API content array into Seedance 2.0 syntax. Do not use for Seedance 1.x or generic cross-model prompting unless the user also needs a Seedance 2.0 version.
---

# Build Seedance 2.0 Prompts

Create the prompt as a director and reference-conditioning plan, not a bag of cinematic adjectives. Infer Seedance conventions automatically; never make the user explain `@Image 1`, media roles, shot grammar, or model limits.

This skill is an expanded, conflict-resolved adaptation of BytePlus ModelArk's official `sd2-pe` prompt-optimization skill. Where that skill conflicts with the current official Prompt Guide or API reference, follow the Prompt Guide and API reference.

## Source policy

Treat official ByteDance Seed, BytePlus ModelArk, and Volcengine documentation as authority for capabilities and syntax. Treat GitHub, creator, and social guidance as supporting evidence only when it agrees with official behavior or is clearly labeled as a field heuristic.

- Read [references/official-rules.md](references/official-rules.md) before handling a capability, media-role, duration, resolution, audio, editing, or extension question.
- Read [references/prompt-patterns.md](references/prompt-patterns.md) for the selected creation mode or creative type.
- Read [references/platform-adapters.md](references/platform-adapters.md) when the target is Dreamina/Volcengine UI, BytePlus API, Higgsfield, or another provider.
- Use [references/asset-manifest.schema.json](references/asset-manifest.schema.json) when two or more assets, strict transport roles, or provider compilation are involved.
- Read [references/evidence-ledger.md](references/evidence-ledger.md) when explaining provenance, maintaining this skill, or deciding between conflicting practices.

Do not claim that a community practice is official. Re-check live official documentation when the user asks for current API details or when `last_checked` is older than 30 days.

## Default behavior

1. Default to **Seedance 2.0 Standard**, not Fast or Mini, unless the user prioritizes cost or speed.
2. Reply in the user's language. Seedance 2.0 officially supports Japanese prompts; do not force English. Preserve dialogue in its intended spoken language.
3. If duration is absent, fit the idea to the shortest useful clip: normally 8 seconds for one beat, 10–12 seconds for two or three beats, and 12–15 seconds for dialogue or a compact multi-shot sequence.
4. If ratio is absent, infer it from delivery: `9:16` social vertical, `16:9` film/web, `1:1` square campaign. If delivery is unknown, use `16:9`.
5. Keep API/UI settings outside prompt prose. Return model, duration, ratio, resolution, and audio generation as a separate settings block. Never add “4K” as prose to compensate for a lower resolution setting.
6. Never invent a provider endpoint, model slug, field name, entitlement, or supported resolution. Use a current official/provider schema when exact submission fields are requested; otherwise label the intent in provider-neutral settings.
   Do not format unverified intent labels as a copy-paste API payload. Call them “control intent” or “provider setting to verify.”
7. Do not generate media or spend credits unless the user explicitly asks for generation. This skill builds and validates prompts.

## Workflow

### 1. Parse the brief without interrogating the user

Extract or infer:

- intended deliverable and audience;
- task mode;
- subject identities and immutable traits;
- action and emotional beat;
- setting, lighting, palette, capture style, and finish;
- camera grammar and cut structure;
- dialogue, voice, ambience, music, and effects;
- references actually supplied and the single job each should perform;
- must-keep and must-change details;
- duration, ratio, resolution, and audio state.

Ask one concise question only when a missing choice would materially change identity, edit direction, or media ordering. Otherwise choose a defensible default and state it briefly after the prompt. This deliberate autonomy overrides the official `sd2-pe` skill's broad requirement to ask about every missing core element.

### 2. Select one control lane and exactly one primary mode

Choose a control lane internally:

- **Vibe-explore** for emotion, story discovery, visual ideation, and generative surprise: name one viewer-facing intention, then translate it into visible carriers—blocking, performance, camera, light, color, sound—instead of shipping an abstract mood word alone.
- **Balanced** by default for most professional creative work: one directorial intention plus only the precision needed to protect the non-negotiables.
- **Precision** for identity/product locks, exact edits, literal dialogue, choreography, UI/text, first/last frames, and client deliverables: make reference roles, invariants, endpoints, and exclusions explicit.

Vibe Creating is an official-origin creative paradigm, not proof that shorter or looser prompting wins every task. Do not use it as a universal benchmark result. Route by required control and evaluate the actual generated clip.

- **Text-to-video**: no media dependency.
- **First-frame image-to-video**: the image is an exact opening frame. Describe motion and change; do not redescribe the still.
- **First-and-last-frame image-to-video**: strict start and end frames. Do not mix API roles `first_frame`/`last_frame` with `reference_image` in the same request.
- **Multimodal reference**: use images for identity, object, scene, composition, style, or approximate frame intent; videos for motion, camera, timing, performance, transition, or effects; audio for voice, timbre, rhythm, music, ambience, or effects.
- **Video edit**: add, remove, or replace a specific element while preserving named invariants.
- **Video extension**: generate before or after a named video and state the continuity bridge.
- **Clip completion/stitching**: define the transition from Video 1 to Video 2, optionally Video 3.

Never silently reinterpret a reference image as a first frame. `reference_image` and `first_frame` are different controls.

For edit and extension tasks, address the source directly: “Strictly edit `@Video 1`” or “Extend `@Video 1` forward/backward.” Do not say only “Reference `@Video 1`,” which can turn a direct operation into ordinary reference generation.

When an edit must preserve source audio, say so in the prompt and choose the provider's preserve-source-audio behavior when verified. Do not turn on fresh audio generation merely because the original clip has audio; if the surface does not expose preservation separately, mark that control as provider-dependent rather than guessing.

Classify creative density by time and space, not merely asset count. Use a compact one-paragraph path when both are simple: one scene, one continuous action, one state display, or one edit. Use a three-part complex path—global setting/bindings, chronological shots, then style/constraints—when events chain, emotional state turns, locations change, or multiple camera setups are required.

### 3. Build an asset map

Number assets by actual upload order within each media type. Internally store stable keys—`image:1`, `video:1`, `audio:1`—then compile them to the active surface. Default Dreamina-style display is:

- `@Image 1`, `@Image 2`, ...
- `@Video 1`, `@Video 2`, ...
- `@Audio 1`, `@Audio 2`, ...

When the user provides an API `content` array, assign numbers from the order of each non-text media type. Keep its URL or asset ID in the separate asset map, not as a subject name in the prompt.

Do not assume the default spelling is universal. Compile from [references/platform-adapters.md](references/platform-adapters.md): for example Dreamina uses `@Image 1`, Volcengine Chinese uses `@图片1`, BytePlus API-facing prose commonly uses `[Image 1]`, Fal uses `@Image1`, and MuAPI uses `@image1`. Preserve a real UI mention chip exactly. The upload slot or API `role` is authoritative; typing a tag alone never changes transport semantics.

For every asset, assign an explicit job such as:

- identity only;
- wardrobe only;
- product geometry/logo only;
- setting/composition only;
- first or last frame;
- body motion only;
- camera movement only;
- editing rhythm only;
- special-effect trajectory only;
- voice/timbre only;
- music/rhythm/ambience only.

Also record what must **not** transfer from each source. A video carrying camera motion should not silently donate its person, wardrobe, palette, or audio. For complex jobs, create an asset manifest with: surface, mode, settings, `modality:index`, compiled tag, source, transport role, primary role, transfers, and must-not-transfer items.

Do not write vague bindings such as “follow the references.” Write “Use the woman in `@Image 1 (Hana)` as Hana; use only the dolly path and cut rhythm from `@Video 1 (camera reference)`; use the low, warm voice timbre from `@Audio 1 (voice reference)`.”

Immediately follow every numbered mention with a noun or alias when it participates in an action: `@Image 1 (Hana) turns toward @Image 2 (the doorway)`. Do not write ambiguous forms such as `@Image 2 position...` or let a label run directly into a number, verb, or spatial term.

When one asset contains multiple subjects, define the intended subject with two or three stable visual traits and give it a short alias. Use that alias consistently. Repeat the media label when ambiguity is possible. Avoid pronouns across multiple characters.

Ask to split long strips, nine-grid collages, and multi-view character sheets into separate files when they can create duplicate-subject ambiguity. Separate clean single-subject images are preferable for character binding.

Never invent an asset or a numbered reference that the user did not provide or explicitly request as a placeholder.

### 4. Compose in Seedance order

Use this internal formula:

`precise subject + concrete action + environment/spatial relation + lighting/color + camera/transition + visual style/capture model + audio + quality/continuity constraints`

For a simple one-shot, write one compact paragraph. For a complex video, write chronological `Shot 1`, `Shot 2`, `Shot 3` blocks. In each shot, order information as:

1. camera movement or cut;
2. subject action and expression;
3. position or spatial change;
4. matching audio.

Use one primary camera movement per shot. A cut may begin a new shot with a different movement; do not stack pan, tilt, dolly, orbit, and zoom simultaneously unless a supplied reference video explicitly carries that combined move.

Describe actions through body part, direction, speed, force, and transition. Prefer coherent physical transitions over stacked verbs. Use high-impact motion only when the concept needs it.

Default to shot order rather than exact `0–3s` timing. Official guidance says strict timing can be unstable. Use timestamps when editing an existing clip, synchronizing a required audio/text cue, or when the user explicitly needs a timed deliverable; treat them as target windows, not guaranteed frame locks. This overrides the official `sd2-pe` skill's unconditional time-slice storyboard rule.

### 5. Write audio and text deliberately

Assign the transfer target whenever audio is referenced: voice identity, vocal texture, speaking style, melody, beat, ambience, or effects. Do not request “same audio” without saying what must match.

For official Dreamina-style prompt notation, use:

- music or score: `(tense low percussion builds)`
- sound effect: `<a metal latch clicks>`
- dialogue: `{Japanese: まだ終わってない}` or natural quoted dialogue when adapting for an API
- on-screen subtitle/text: BytePlus English guide uses `〖Chapter One: Departure〗`; Volcengine Chinese skill uses `【第一章：出発】`. Preserve the active surface's notation.

Keep dialogue in one language per scene except proper nouns. Specify speaker, language, voice qualities, emotion, and delivery. If subtitles are not wanted, explicitly require subtitle-free output; dialogue can otherwise cause unwanted text.

### 6. Add only relevant constraints

Use a short constraint tail, not a generic negative wall. Protect the few things that matter:

- identity, wardrobe, proportions, product geometry, or logo fidelity;
- one instance of each character, with no duplicate/twin effect;
- natural anatomy, contact, motion continuity, and stable faces;
- preservation of untouched video content in edits;
- no unwanted text, subtitles, logos, or watermarks;
- exact target style when realistic references might pull animation toward live action.

Use visual-quality language only when it describes the look—clean detail, natural motion blur, stable exposure—not as a substitute for the resolution setting. Do not automatically append “4K HD.”

Do not forbid text when the user requests a title, logo, subtitle, label, or speech bubble. Do not mix conflicting style, camera, or subject instructions.

### 7. Validate before delivery

Check all of the following:

- every numbered media reference exists and matches upload order;
- every subject has one stable alias and unambiguous binding;
- each reference has a named job;
- prompt mode matches media roles;
- shot count and action density fit 4–15 seconds;
- chronology, camera, body motion, and audio do not conflict;
- the prompt retains every user must-have and does not add unsupported story beats;
- settings are outside prompt prose;
- constraints do not contradict requested text, branding, dialogue, or motion;
- copyrighted characters, unauthorized likenesses, and unlicensed brands are not silently introduced.

For prompts with two or more references, editing, extension, dialogue, or more than two shots, run:

```powershell
python scripts/validate_prompt.py <prompt-file> --images <n> --videos <n> --audios <n> --duration <seconds> --mode <mode> --surface <surface>
```

When an asset manifest exists, let it supply and cross-check the counts, mode, duration, surface syntax, transport roles, transfer jobs, and exclusions:

```powershell
python scripts/validate_prompt.py <prompt-file> --manifest <manifest.json> --strict
```

Fix all errors. Resolve warnings when they apply; validator heuristics are not model guarantees.

### 8. Repair from evidence, not the planned prompt

When the user supplies a generated result, evaluate identity/product fidelity, action physics, camera, chronology, audio, text, and continuity separately. Identify the smallest failed variable and revise that variable first; do not rewrite every successful instruction at once.

For continuation, use the accepted clip's **actual** last visible state—pose, gaze, prop position, camera direction, velocity, lighting, and live audio tail—not merely the ending imagined in the prior prompt. Preserve an accepted state record before writing the next extension.

## Output contract

Lead with the paste-ready artifact. Do not explain Seedance basics before it.

Use this order unless the user asks for prompt-only output:

1. **Seedance 2.0 prompt** — one copy-ready block.
2. **Asset order** — only when media is used; label, upload order, purpose, and platform role.
3. **Settings** — Standard/Fast/Mini, duration, ratio, resolution, audio on/off.
4. **Checks** — only material assumptions, provider caveats, or unresolved risks.

When the user requests “prompt only,” return only the finished prompt, with no headings, tutorial, alternative versions, or follow-up question.

When diagnosing an existing prompt, preserve the creative intent, identify the smallest concrete failures, then return a corrected prompt rather than merely commenting on it.
