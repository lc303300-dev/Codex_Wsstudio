# Manifest schema

Use UTF-8 JSON. Resolve relative paths from the manifest directory.

```json
{
  "batch_id": "xian-logo-v1",
  "image_ratio": "9:16",
  "image_resolution": "1K",
  "image_provider": "dreamina-image",
  "output_dir": "./batch-output",
  "concurrency": 10,
  "start_delay_seconds": 1,
  "seconds_per_image": 60,
  "deadline_multiplier": 1.5,
  "prompt_version": "v1",
  "groups": [{
    "id": "SJ01",
    "prompt": "Render the supplied composition while preserving geometry...",
    "reference_images": ["./SJ01.png", "./Logo_CK.png"],
    "original_image": "./SJ01.png",
    "candidates": 5
  }]
}
```

Require `image_ratio` and a non-empty `groups` array. Optional `image_resolution` is a batch-wide explicit `1K`, `2K`, or `4K` selection. When omitted, GPT image routes default to `4K`, Gemini image routes default to `2K`, and Dreamina retains `1K`. Optional `image_provider` is a batch-wide, user-explicit route and must be one of the unified router's supported IDs; omit it to retain the default serial route order. When present, every candidate uses only that route without cross-route fallback. Each group requires a unique `id`, a non-empty `prompt`, and `candidates >= 1`. `batch_id` defaults to a generated ID. `original_image` is optional; otherwise use the first reference image as slot 0. Defaults are 10 workers, 1 second start spacing, 60 seconds per concurrent wave, a 1.5 deadline multiplier, and prompt version `v1`.

Calculate `expected_seconds` as `ceil(total planned candidates / concurrency) * seconds_per_image`. Calculate the default whole-batch `deadline_seconds` as `expected_seconds * deadline_multiplier`, measured from runner start. For example, 40 candidates at concurrency 10 have a 240-second estimate and a 360-second maximum wait. Set `deadline_seconds` only when an explicit whole-batch override is needed.

Accept at most 10 workers. Validate the ratio before creating or submitting jobs. Do not resubmit existing jobs with the same stable job key.
