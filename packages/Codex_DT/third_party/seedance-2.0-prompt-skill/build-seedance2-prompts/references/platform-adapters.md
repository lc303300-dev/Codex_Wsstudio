# Seedance 2.0 platform adapters

`last_checked: 2026-07-14`

Prompt labels and upload controls are different layers. Adapt both; never assume typing `@Image 1` changes an API media role.

## Contents

- Canonical internal representation
- Surface tag compiler
- Codex_DT/default-video-generation local surface
- Dreamina/Volcengine UI
- BytePlus ModelArk API
- Higgsfield
- Other providers

## Canonical internal representation

Build every job from this neutral asset map before adapting it. The stable key is `modality:index`; the displayed tag is compiled later:

| Stable key and alias | Default display | Source | Semantic job | Strict transport role |
|---|---|---|---|---|
| `image:1`, Hana | `@Image 1 (Hana)` | file/URL/asset ID | identity and wardrobe only | `reference_image` |
| `image:2`, opening frame | `@Image 2 (opening frame)` | file/URL/asset ID | exact opening composition | `first_frame` |
| `video:1`, camera reference | `@Video 1 (camera reference)` | file/URL/job ID | camera path and cut rhythm only | `reference_video` |
| `audio:1`, voice reference | `@Audio 1 (voice reference)` | file/URL/job ID | voice timbre only | `reference_audio` |

Keep opaque IDs and URLs out of the authored subject language. Preserve them in the map or request payload.

## Surface tag compiler

Do not store a provider spelling as model knowledge. Compile each `modality:index` key to the active surface and preserve a mention chip exactly when the user supplies one.

| Surface profile | Image 1 | Video 1 | Audio 1 | Binding authority |
|---|---|---|---|---|
| `dreamina` | `@Image 1` | `@Video 1` | `@Audio 1` | uploaded item / UI mention chip |
| `volcengine-zh` | `@图片1` | `@视频1` | `@音频1` | uploaded item / UI mention chip |
| `byteplus-api` | `[Image 1]` | `[Video 1]` | `[Audio 1]` | `content` order plus `role` |
| `fal` | `@Image1` | `@Video1` | `@Audio1` | current provider schema |
| `jimeng-zh` | `@图片1` | `@视频1` | `@音频1` | uploaded item / mention chip |
| `muapi` | `@image1` | `@video1` | `@audio1` | current provider schema |
| `higgsfield` | `@Image 1` | `@Video 1` | `@Audio 1` | saved job media roles |
| `generic` | preserve supplied token; otherwise `@Image 1` | preserve supplied token; otherwise `@Video 1` | preserve supplied token; otherwise `@Audio 1` | provider must be confirmed |

The Fal and MuAPI rows describe observed provider-facing conventions, not a ByteDance universal standard. Re-check them at submission time. Use [asset-manifest.schema.json](asset-manifest.schema.json) to keep the source, semantic job, transfer exclusions, and transport role separate from the compiled prompt tag.

Minimal manifest example:

```json
{
  "surface": "dreamina",
  "model_variant": "standard",
  "mode": "multimodal",
  "duration": 8,
  "ratio": "16:9",
  "resolution": "1080p",
  "generate_audio": true,
  "assets": [
    {
      "modality": "image",
      "index": 1,
      "tag": "@Image 1",
      "alias": "Hana",
      "source": "hana.png",
      "transport_role": "reference_image",
      "primary_role": "identity",
      "transfers": ["face", "hair", "wardrobe"],
      "must_not_transfer": ["background", "pose"]
    },
    {
      "modality": "video",
      "index": 1,
      "tag": "@Video 1",
      "alias": "camera reference",
      "source": "dolly.mp4",
      "transport_role": "reference_video",
      "primary_role": "camera",
      "transfers": ["dolly path", "cut rhythm"],
      "must_not_transfer": ["person", "wardrobe", "palette", "audio"]
    }
  ]
}
```

## Codex_DT/default-video-generation local surface

Codex_Wsstudio's local `default-video-generation` path defaults to Seedance 2.5, 480P, all-around reference mode, duration 4-30 seconds, and up to 50 total reference content items. These values are generation settings, not prompt prose.

For CLI-facing Codex_DT prompts, compile ordered references to bare Chinese labels tied to upload order:

| Stable key | Prompt label |
|---|---|
| `image:1` | `图片1` |
| `video:1` | `视频1` |
| `audio:1` | `音频1` |

Do not type Web UI mention-chip forms such as `@Image 1`, `@图片1`, `@Video 1`, or `@视频1` into the local CLI-facing prompt. Do not write `Seedance 2.5`, `480P`, `all-around reference mode`, API fields, upload arguments, or tool-call instructions into the prompt body. Keep them in settings or the asset manifest.

## Dreamina/Volcengine UI

- Upload media in deliberate order by type.
- Insert or write ordered mentions as `@Image 1`, `@Video 1`, and `@Audio 1`.
- Immediately add a noun/alias: `@Image 1 (Hana)`.
- State one explicit transfer job per mention.
- UI mention syntax does not make a general image an exact first frame. Select the platform's first/last-frame mode when strict anchoring is needed.
- Use Dreamina-style audio/text notation when useful: music `()`, effects `<>`, dialogue `{}`, text/subtitles `〖〗`.

If the UI visibly renders a mention chip with different spacing/capitalization, preserve the UI token and add the alias after it.

## BytePlus ModelArk API

### Reference generation

The API `content` array performs the real binding. A prompt may say `@Image 1` or `[Image 1]`, but the media object's order and `role` determine what the model receives.

Conceptual request shape:

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "Use [Image 1] (Hana) for identity only and [Video 1] for camera path only..."
    },
    {
      "type": "image_url",
      "image_url": { "url": "<image-url-or-asset-id>" },
      "role": "reference_image"
    },
    {
      "type": "video_url",
      "video_url": { "url": "<video-url>" },
      "role": "reference_video"
    },
    {
      "type": "audio_url",
      "audio_url": { "url": "<audio-url>" },
      "role": "reference_audio"
    }
  ],
  "generate_audio": true,
  "ratio": "16:9",
  "resolution": "720p",
  "duration": 8,
  "watermark": false
}
```

Number each media type in its own appearance order. The first image is Image 1 even if a video appears before it in the combined array.

### Exact first/last frames

- exact opening: one `image_url` with `role: "first_frame"`;
- exact opening and ending: two images with roles `first_frame` and `last_frame`;
- do not mix these strict roles with `reference_image` in the same API scenario;
- if first/last ratios differ, the first image controls and the last can be cropped;
- multimodal prose can request an approximate first/last composition, but it is not strict transport-level anchoring.

### Settings

- keep duration, ratio, resolution, audio, watermark, and return-last-frame settings outside prompt text;
- dialogue in ordinary double quotes is the safest API-facing form;
- do not pass unsupported Seedance 2.0 controls such as `seed` or `camera_fixed`;
- use Standard model for 1080p/4K requests and verify current entitlement/provider support before submission.

## Higgsfield

For prompt-only work, retain canonical `@Image N`/`@Video N`/`@Audio N` labels plus the asset map. When generation is requested, use the installed `$higgsfield-generate` skill for current CLI discovery and cost-aware submission.

Current local integration notes:

- `--start-image` means exact first-frame animation;
- `--end-image` means last-frame intent where supported;
- `--video` and `--audio` supply video/audio references;
- a generic `--image` should mean reference image, but local official CLI `0.2.3` was observed coercing a Seedance 2.0 image to a saved `start_image` role in at least one flow;
- therefore verify the saved job's media roles before calling a Higgsfield result true OmniReference/reference-element conditioning;
- do not silently use `--start-image` merely because an image was attached.

This CLI behavior is drift-prone. Re-check the installed model schema and saved job parameters at generation time.

## Other providers

Before adapting a prompt for OpenRouter, fal, Segmind, APIMart, a hosted Seedance site, or another gateway:

1. Confirm that the route is truly Seedance 2.0 Standard rather than 1.x, Fast, Mini, or a branded imitation.
2. Inspect its actual media slots and request schema.
3. Map canonical jobs to transport roles; do not infer role from the label alone.
4. Confirm image/video/audio limits, duration, resolution, ratio, audio generation, edit, and extension support.
5. Preserve ordered readable labels in the prompt even if the provider does not expose mention chips.
6. If the provider only accepts one image, prioritize the asset that carries the non-negotiable identity/product/first-frame requirement and move secondary style/layout needs into prose.
7. Mark any unsupported capability instead of pretending that prompt wording can recreate it.

Third-party availability, pricing, and role behavior change quickly. Use official provider documentation or a live schema check for current claims.
