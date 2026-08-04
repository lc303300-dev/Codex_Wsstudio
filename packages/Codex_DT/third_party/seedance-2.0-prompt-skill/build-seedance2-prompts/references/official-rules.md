# Seedance 2.0 official rules

`last_checked: 2026-07-14`

## Contents

- Source hierarchy
- Official model and request limits
- Media roles and reference notation
- Prompt construction rules
- Audio and text grammar
- Known failure modes
- Conflicts resolved in this skill

## Source hierarchy

Use these in descending order of authority for prompt behavior:

1. [Volcengine Seedance 2.0 prompt guide](https://www.volcengine.com/docs/82379/2222480?lang=zh) and [BytePlus prompt guide](https://docs.byteplus.com/en/docs/ModelArk/2222480), current 2026-07-07 editions.
2. [Volcengine Seedance 2.0 tutorial](https://www.volcengine.com/docs/82379/2291680?lang=zh) and [BytePlus tutorial](https://docs.byteplus.com/en/docs/ModelArk/2291680), current 2026-07-07 editions. Both distribute an official `sd2-pe` prompt-optimization skill, but the Chinese package is substantially more complete.
3. [Create a video generation task API](https://docs.byteplus.com/en/docs/ModelArk/1520757), updated 2026-06-29.
4. [ByteDance Seedance 2.0 model card](https://seed.bytedance.com/en/seedance2_0).

The primary official skill snapshot used for this fork was served by Volcengine at:

`https://arkdoc.tos-cn-beijing.volces.com/files/video-generation/SKILL.md`

Verified SHA-256 on 2026-07-14:

`8836cdb2bc4f7d8a329c4ecd33cca19efdcfc71afdd927e8defe6e1f9a2e2b3c`

The shorter English BytePlus snapshot was served at:

`https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/1a98a5a8685547568ed9ef257ceabe85~tplv-goo7wpa0wc-image.image`

Both declare the name `sd2-pe`. The Chinese package adds task routing, simple and complex paths, audio mapping, reference-person limits, exact-timing cautions, and failure handling. Neither downloaded file contains an explicit license grant, so this skill paraphrases and independently implements the rules instead of copying the official text verbatim.

## Official model and request limits

### Model selection

- Standard model ID: `dreamina-seedance-2-0-260128`.
- Fast model ID: `dreamina-seedance-2-0-fast-260128`.
- Standard and Fast have the same major creation modes. Official guidance recommends Standard for highest quality and Fast when cost/speed matter more.
- Do not silently substitute Mini or a Seedance 1.x model.

### Supported creation modes

- text-to-video;
- first-frame image-to-video;
- first-and-last-frame image-to-video;
- multimodal reference generation;
- video add/remove/replace editing;
- forward/backward video extension;
- two- or three-clip transition completion;
- synchronized audio-video generation;
- return-last-frame continuation workflows.

### Multimodal input limits

- reference images: 0–9;
- reference videos: 0–3;
- reference audios: 0–3;
- text is optional in multimodal mode;
- audio-only input is invalid: at least one image or video must accompany reference audio;
- the official guide advises against filling every slot because too many assets weaken priority and can create style or identity conflicts.
- BytePlus documents individual reference video/audio durations of 2–15 seconds and a combined reference duration ceiling of 15 seconds for the relevant multimodal flows; re-check the active surface.
- The official skill's practical starting bundle is usually four or five assets: one or two clean character images, one scene image, one motion/camera video, and one audio reference. This is a recommendation, not a required count.

### Output controls

- duration: integer 4–15 seconds, or provider-supported intelligent selection where documented;
- ratio: `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, and `adaptive` in supported API scenarios;
- resolution: Standard supports `480p`, `720p`, `1080p`, and current API documentation lists `4k`; Fast does not support the highest tiers;
- Seedance 2.0 does not support the API `seed` control;
- Seedance 2.0 does not currently support `camera_fixed` as an API control;
- prompt language: English plus official Seedance 2.0 support for Japanese, Indonesian, Spanish, and Portuguese;
- recommended prompt length: under 1000 words. Concision is still preferred because long prompts scatter attention.

Put these values in provider controls or API fields. “4K,” “10 seconds,” or “fixed camera” in prompt prose is not a substitute for an actual supported setting.

### Input-image constraints on BytePlus API

- formats include JPEG, PNG, WEBP, BMP, TIFF, GIF, HEIC, and HEIF for Seedance 2.0;
- aspect ratio must be within the documented input range;
- each dimension must be within the documented pixel range;
- a single image must be below 30 MB and the whole request body below 64 MB;
- match first/last-frame image ratios to the target output or use `adaptive` to reduce crop/jump problems.

These are BytePlus transport limits, not prompt grammar. Re-check provider-specific limits elsewhere.

## Media roles and reference notation

### API roles are authoritative

In BytePlus API requests, the media object role controls the mode:

- exact first frame: `first_frame`;
- exact last frame: `last_frame`;
- general image reference: `reference_image`;
- video reference/edit/extension input: `reference_video`;
- audio reference: `reference_audio`.

First/last-frame mode and multimodal-reference mode are mutually exclusive API scenarios. In multimodal reference mode, prose can request an approximate opening or ending composition, but strict equality requires `first_frame`/`last_frame` roles.

### Canonical labels

The official UI/guide uses ordered labels such as:

- `@Image 1`;
- `@Video 1`;
- `@Audio 1`.

Official API samples also use textual forms such as `[Image 1]` and `[Video 1]`. These labels describe media in the prompt; the API `content` array order and `role` fields create the actual attachment mapping.

Never use an opaque `asset-xxx` ID as the subject name. Keep IDs/URLs in the request or asset map and use readable ordered labels in the prompt.

### Binding subjects

- Define a subject from a media item with two or three stable identifying features and a short alias.
- When multiple subjects appear in one asset, state which one is intended.
- Use the same alias every time; avoid pronouns when two or more characters are active.
- Repeat a media label when omission is possible.
- Immediately follow an `@Image N`/`@Video N` mention with a noun or alias: `@Image 1 (Hana)`.
- Prefer separate single-subject images. Long strips, nine-grid collages, and three-view montages can be interpreted as duplicate subjects.
- Official troubleshooting reports reduced stability with more than four referenced people. Group or stage larger casts.

### Give every reference a job

Images can transfer subject identity, object detail, layout, sequence, composition, logo, style, or scene. Videos can transfer body motion, performance, camera movement, pacing, transition, or special-effect trajectory. Audio can transfer voice/timbre, speaking style, dialogue content, melody, rhythm, ambience, or effects.

State exactly what transfers and, when needed, what does not. “Reference Video 1” is weaker than “Use only the lateral tracking path and cut rhythm from `@Video 1 (camera reference)`; retain the new character and location.”

## Prompt construction rules

### Core formula

Official advanced formula:

`precise subject + action details + scene/environment + lighting/color + camera movement + visual style + image quality + constraints`

This skill adds audio as an explicit ninth concern when sound is enabled or referenced.

### Complex-video sequencing

Official guidance says space and time are modeled separately. For complex videos, use a chronological storyboard:

- `Shot 1`, `Shot 2`, `Shot 3` in event order;
- within each shot: camera/cut, subject action and expression, spatial change, then audio;
- use one principal camera movement per shot unless a reference video supplies a deliberate compound move;
- avoid strict `0–3s` slices by default. The official Prompt Guide warns precise timing is unstable and can cause abnormal output;
- use timestamps for edit locations, required audio/text synchronization, or explicitly timed deliverables, and treat them as targets rather than frame guarantees.

### Action descriptions

- name body parts and direction;
- state degree, speed, or force where it matters;
- describe the transition/inertia between actions;
- slow, gentle, coherent motions are more stable than a chain of explosive movements;
- retain large dynamics when the concept requires them, preferably with a reference video that demonstrates motion or camera language.

### Style and constraints

- choose one coherent art/capture model instead of stacking incompatible style names;
- if realistic reference media may pull an animated target toward live action, restate the target style explicitly;
- constraint words are officially recommended for unwanted subtitles, logos, watermarks, distortion, duplicates, and continuity failures;
- constraints reduce risk but do not guarantee absence.

## Audio and text grammar

### Audio generation

- `generate_audio=true` produces synchronized voice, effects, and music when supported;
- current API documentation says generated audio is mono;
- API documentation recommends double quotes around dialogue;
- a referenced audio needs an explicit target: timbre, voice texture, melody, beat, ambience, effects, or content;
- match the requested line's tone and expression to the reference voice for stronger restoration;
- keep dialogue language consistent within a scene, apart from proper nouns.

### Dreamina-style symbols

- music: `(fast percussion builds)`;
- sound effect: `<a door latch clicks>`;
- dialogue: `{Japanese: 行こう}`;
- subtitle/on-screen text: BytePlus English examples use `〖Chapter One: Departure〗`; the Volcengine Chinese official skill uses `【第一章：启程】`.

Use the notation expected by the active UI and preserve an existing token exactly. Adapt dialogue to ordinary JSON-safe quoted text in an API prompt when appropriate.

### Generated text

For slogans, titles, subtitles, or speech bubbles, specify:

`exact text + timing/order + position + entrance/appearance behavior + color/type style`

Use common characters and avoid rare symbols when exact legibility matters. Text output is probabilistic; use post-production for legally or commercially critical typography.

## Known failure modes

### Unwanted subtitles

- explicitly request subtitle-free/no on-screen text;
- remove irrelevant text from reference media before generation;
- official troubleshooting says landscape generation has a lower subtitle probability than portrait, but it is not a guarantee.

### Unwanted logo or watermark

- explicitly prohibit logos/watermarks when no branded text is wanted;
- do not combine this with a request to preserve a supplied logo.

### Duplicate or twin characters

- bind each role to a separate clean reference and stable alias;
- prohibit duplicate/twin instances and require one corresponding character per frame;
- avoid multi-view montages that show the same person multiple times;
- simplify the prompt and reduce the number of referenced people.

### Style drift

- explicitly lock the target style;
- when control is strict, pre-convert the reference asset to the target style before video generation.

### Special effects do not match

- use a reference video to define motion logic and trajectory instead of relying on prose alone.

### Extension degradation or jump cuts

- avoid repeatedly extending an already extended output;
- use high-quality references and preserve only necessary segments;
- align or trim joins in post when required; official troubleshooting notes prompt-only repair is not guaranteed.

### Frame stretching/jumps

- align input and output aspect ratios or use the provider's adaptive ratio;
- strict first/last frame inputs may be cropped if their ratios differ.

### Portrait input restrictions

BytePlus ModelArk may reject direct uploads containing real human faces unless they are trusted same-account outputs, preset digital characters, or authorized real-person assets. This is platform policy, not a universal Seedance model limitation. Do not promise that an unauthorized portrait will be accepted.

## Conflicts resolved in this skill

| Conflict | Official `sd2-pe` behavior | Resolution here |
|---|---|---|
| Timing | Requires time slices such as `0–3s` | Default to `Shot 1/2/3`; use time windows only for edits/sync/explicit need |
| Resolution | Automatically appends “4K HD” | Keep resolution in settings/API; use quality prose only for visual finish |
| Audio mapping | Maps images/videos but omits robust audio mapping | Number and bind `@Audio N` with an explicit transfer job |
| First/last frame | Declares intent in prose | Require `first_frame`/`last_frame` roles for strict API matching |
| Missing details | Requires broad user confirmation | Infer low-risk creative defaults; ask only when identity/order/edit intent would materially change |
| Output explanation | Always returns optimization/principles | Lead with the production prompt; explain only when requested or diagnosing |
