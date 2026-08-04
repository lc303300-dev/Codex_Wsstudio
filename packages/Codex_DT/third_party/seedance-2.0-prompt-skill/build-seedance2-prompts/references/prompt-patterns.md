# Seedance 2.0 prompt patterns

Use placeholders as structural guides, not copy-paste filler. Remove every unused clause. Keep one clear creative thesis per generation.

## Contents

- Mode selection
- Universal prompt skeleton
- Mode-specific patterns
- Creative direction modules
- Constraint modules
- Density heuristics

## Mode selection

| User intent | Primary mode | Media role |
|---|---|---|
| Describe a new clip with no assets | Text-to-video | none |
| Animate the attached still exactly from its opening composition | First-frame I2V | `first_frame` |
| Travel exactly from supplied opening to supplied ending frame | First/last I2V | `first_frame`, `last_frame` |
| Preserve identity/product/style while inventing a new shot | Multimodal reference | `reference_image` |
| Borrow motion, camera, pacing, performance, transition, or effect | Multimodal reference | `reference_video` |
| Borrow voice, music, rhythm, ambience, or effects | Multimodal reference | `reference_audio` plus image/video |
| Change something inside an existing clip | Video edit | `reference_video` |
| Continue before/after an existing clip | Video extension | `reference_video` |
| Generate a bridge between clips | Clip completion | 2–3 `reference_video` items |

## Universal prompt skeleton

```text
[Asset binding, only when media exists. Define aliases and the exact job of each reference.]

[Single shot or Shot 1/2/3 in chronological order. For each shot: camera/cut -> subject action/expression -> spatial change -> audio.]

[Overall environment, lighting/color, visual/capture style, continuity and only relevant constraints.]
```

The final prompt does not need these headings unless they improve parsing. Complex prompts benefit from `Shot N`; simple prompts usually do not.

## Mode-specific patterns

### 1. Text-to-video, one shot

```text
[Precise subject with 2–3 stable traits] [performs one concrete action with direction, speed, and physical transition] in [specific environment and spatial relationship]. [One camera framing and one movement]. [Lighting, palette, and one coherent capture/art style]. [Matching ambience/effect/dialogue]. [Short continuity constraints].
```

Example shape:

```text
A weathered ceramicist in a charcoal apron slowly rotates a wet clay bowl, then steadies its rim with both thumbs as the wheel decelerates. Medium close-up at eye level; the camera makes one slow lateral slide, keeping the hands and clay in focus. Soft overcast window light, muted earth tones, observational documentary photography. <the wheel hums and wet clay softly scrapes>. Hands, bowl geometry, and apron remain consistent; natural finger contact and motion.
```

### 2. Complex multi-shot narrative

```text
[Define characters/assets once.]

Shot 1: [Opening framing/movement]. [Character action + expression]. [Position/environment]. [Audio].
Shot 2: Cut to [new framing/movement]. [Cause-and-effect action]. [Spatial change]. [Audio].
Shot 3: Cut to [payoff framing/movement]. [Resolution action/expression]. [Final composition]. [Audio].

[One overall style/lighting statement]. [Identity, continuity, and unwanted-output constraints].
```

Make every cut earn a story beat. Do not repeat the same action from three angles unless the user explicitly wants coverage.

### 3. Exact first-frame image-to-video

```text
Use @Image 1 (exact opening frame) as the strict first frame. From that composition, [subject alias] begins [specific motion]; [secondary object/environment motion] responds naturally. [One camera movement or fixed composition described in prose]. [Lighting/exposure behavior]. Preserve all unmentioned appearance, layout, wardrobe, product, and background details from the opening frame. [Audio]. [Motion/anatomy constraints].
```

Do not redescribe every visible detail. Describe what changes, what moves, and what must stay fixed.

### 4. Exact first-and-last-frame image-to-video

```text
Begin exactly from @Image 1 (first frame) and end exactly on @Image 2 (last frame). [Subject alias] transitions from [opening state] to [ending state] through [one physically coherent action path]. [Camera behavior that can plausibly connect both compositions]. [Environment response and audio]. Preserve [identity/wardrobe/object geometry]. No intermediate duplication, teleporting, or discontinuous pose change.
```

Use actual `first_frame` and `last_frame` roles. If the two images have different ratios, warn about crop or ask the provider to adapt.

### 5. Multimodal character, scene, motion, and audio reference

```text
Use @Image 1 (Hana) only for Hana's identity and wardrobe. Use @Image 2 (station interior) for the location, layout, and cool fluorescent palette. Use only the shoulder-level tracking path and restrained cut rhythm from @Video 1 (camera reference); do not copy its people or setting. Use the low, breathy female timbre from @Audio 1 (voice reference) for Hana's line.

Shot 1: [camera/cut]. @Image 1 (Hana) [action/expression] in @Image 2 (station interior). [spatial change]. [audio/dialogue].
Shot 2: [camera/cut]. [consequent action]. [new position]. [audio].

[Style and lighting]. Hana's face, hairstyle, wardrobe, and proportions remain consistent; only one Hana appears in frame. Natural contact, motion, and lip synchronization; no unwanted subtitles or watermark.
```

When several images show the same subject, define that set once: “Use the woman across `@Image 1`, `@Image 2`, and `@Image 3` as Hana; preserve the shared facial and wardrobe traits.”

### 6. Dialogue scene

```text
[Character/asset bindings and voice assignments.]

Shot 1: [speaker framing and one subtle camera movement]. [Speaker] [expression and small physical action], then says in Japanese with [voice qualities and emotion] {line}. [Listener reaction and room ambience].
Shot 2: Cut to [listener framing]. [Listener] [reaction], then replies in Japanese with [delivery] {line}. [Audio transition].

Keep the dialogue in Japanese, with distinct voices and natural turn-taking. Preserve speaker identity and eyelines. Natural lip synchronization and room tone. Keep the video subtitle-free unless subtitles were requested.
```

Keep lines short enough to fit the clip. Spoken words consume screen time; cut visual actions before cutting essential dialogue.

### 7. Motion, camera, or effect reference

```text
Use [only the named property] from @Video 1 ([role]): [precise transfer description]. Do not copy [people/setting/branding/content that must not transfer]. Apply it to @Image 1 ([new subject]) in [new scene]. [Shot action]. Preserve the new subject and environment; keep the referenced [motion/camera/effect] trajectory and timing coherent.
```

Examples of precise jobs:

- body motion: footwork, weight transfer, hand path, acceleration;
- performance: facial beat, pause, gaze, gesture timing;
- camera: height, path, focal behavior, shake, reframing;
- editing: cut rhythm and transition order;
- effects: formation path, particle direction, growth/dissolve sequence.

### 8. Product or advertising clip

```text
Use @Image 1 (product) only for exact product shape, materials, label, logo placement, and color. Use @Image 2 (environment) for the set and composition. [Optional camera/audio reference jobs.]

Shot 1: [clean reveal framing and one movement]. [Product interaction with physically correct hand/object contact]. [Lighting response on material]. [Audio].
Shot 2: Cut to [macro/detail framing]. [One benefit-revealing action]. [Audio/voiceover].
Shot 3: [final hero composition]. [Exact approved slogan/text behavior if requested].

Preserve product geometry, packaging proportions, label spelling, and logo position. No invented claims, extra products, duplicate packaging, unrelated text, or watermark.
```

For legally critical package copy, use post-production rather than trusting generated text.

### 9. Add, remove, or replace inside a video

```text
Edit @Video 1 (source video).

Add: At [target time/window] in [screen/world position], add [specific element and interaction]. Preserve [named original elements, camera, motion, lighting, and audio].

Remove: Remove [precisely identified element] from @Video 1. Reconstruct the revealed background consistently. Keep all other people, objects, camera movement, timing, lighting, and audio unchanged.

Replace: Replace [source element] in @Video 1 with @Image 1 (replacement object/subject). Preserve the original size relationship, contact, motion path, camera movement, lighting direction, reflections, occlusion, and timing. Keep every other element unchanged.
```

Use timestamps here because they locate an edit. State invariants explicitly; “everything else unchanged” alone is weaker than naming the crucial elements.

If source audio must remain untouched, say `preserve the original audio exactly` and use a verified source-audio preservation control. Do not set new audio generation to on by default for an edit. Never invent a provider endpoint or request field; keep the setting provider-neutral until the live schema is checked.

### 10. Extend a video

```text
Generate the content [after/before] @Video 1 (source clip). Continue from its [last/first] moment with matching character identity, pose, motion direction, camera height/path, lighting, color, environment, and room tone. [Describe the new action and emotional progression]. [Describe the continuity bridge]. [End state if needed].
```

If the output should include the original content, say so explicitly. Avoid repeated extension chains when quality is already degrading.

### 11. Complete a transition between clips

```text
@Video 1 (opening clip). As [last visible action/object] reaches [transition trigger], [specific physical/visual transition] carries the motion into @Video 2 (ending clip). Preserve the direction of movement, camera momentum, lighting logic, and audio rhythm through the join. [Optional continuation toward @Video 3].
```

Maximum supported reference videos and total input duration depend on provider; BytePlus documents up to three videos and official completion examples within a 15-second total input window.

### 12. Generated titles, subtitles, or speech bubbles

```text
[Exact text] appears [order/timing] at [position] using [entrance behavior], [color], and [type/graphic style]. It remains [duration/condition] and disappears [behavior]. [If subtitles:] synchronize each line with the corresponding speaker and audio pacing.
```

Do not also add “no text/subtitles.” Use ordinary characters and short copy.

## Creative direction modules

Choose one module and tailor it. Do not stack all of them.

### Photoreal narrative

State lens/framing only when it changes the storytelling. Describe natural exposure, plausible depth of field, restrained grade, real contact, weight, inertia, and environmental sound. Avoid the empty word “cinematic” unless its concrete meaning follows.

### Smartphone/UGC realism

Use imperfect handheld body-driven movement, modest autofocus/exposure response, natural reframing, practical sound, and unpolished composition. Do not mix this with stabilized crane, flawless commercial lighting, and glossy film grammar unless the contrast is intentional.

### Animation

Lock the exact animation family, line/texture behavior, color treatment, and motion language. Restate the target style when reference media is realistic. Avoid mixing 2D cel, painterly stop motion, glossy 3D, and live action in one style clause.

### Product macro

Prioritize material response, surface detail, product geometry, contact, reflections, and clean background separation. Use one controlled camera move and a clear hero ending.

### Action/VFX

Use a reference video for complex choreography, camera, or effect trajectory where possible. Describe cause-and-effect, body mechanics, screen direction, contact, recovery, and environment response. Reduce simultaneous independent actions.

### Quiet documentary

Use longer observation, subtle micro-actions, one restrained movement, natural ambience, and imperfect human timing. Avoid unnecessary cuts and exaggerated emotional instruction.

## Constraint modules

Select only what applies.

### Character continuity

```text
[Alias]'s facial features, hairstyle, wardrobe, accessories, body proportions, and age remain consistent. Only one corresponding [Alias] appears in the same frame; no duplicate or twin effect.
```

### Product continuity

```text
Product geometry, cap/closure, material, label spelling, logo placement, color, and proportions remain unchanged; no duplicate package or invented branding.
```

### Motion stability

```text
Natural anatomy, weight, contact, occlusion, and motion continuity; no limb fusion, clipping, teleporting, stutter, or flicker.
```

### Clean frame

```text
No unwanted text, subtitles, logo, watermark, border, or interface overlay.
```

Do not use Clean frame when branded or on-screen text is requested.

### Edit preservation

```text
Keep all unmentioned subjects, objects, camera movement, timing, lighting, reflections, background, and audio unchanged.
```

## Density heuristics

These are field heuristics, not official hard limits:

- 4–6 seconds: one shot or one transition beat;
- 7–9 seconds: one rich shot or two simple shots;
- 10–12 seconds: two or three clear beats;
- 13–15 seconds: up to three or four compact shots, or a short dialogue exchange;
- one principal action and one principal camera movement per shot;
- if every reference, action, style, and constraint is “equally important,” the prompt has no priority. Remove or stage lower-priority ideas.
