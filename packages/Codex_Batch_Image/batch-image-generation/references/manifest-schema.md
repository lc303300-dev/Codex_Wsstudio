# Manifest schema

Use UTF-8 JSON. Resolve relative paths from the manifest directory.

```json
{
  "batch_id": "xian-logo-v1",
  "image_ratio": "9:16",
  "output_dir": "./batch-output",
  "concurrency": 10,
  "start_delay_seconds": 1,
  "deadline_seconds": 480,
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

Require `image_ratio` and a non-empty `groups` array. Each group requires a unique `id`, a non-empty `prompt`, and `candidates >= 1`. `batch_id` defaults to a generated ID. `original_image` is optional; otherwise use the first reference image as slot 0. Defaults are 10 workers, 1 second start spacing, 480 seconds deadline, and prompt version `v1`.

Accept at most 10 workers. Validate the ratio before creating or submitting jobs. Do not resubmit existing jobs with the same stable job key.
