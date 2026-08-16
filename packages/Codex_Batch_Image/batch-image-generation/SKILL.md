---
name: batch-image-generation
description: Orchestrate timed, concurrent, grouped still-image generation through the unified generate_image/Media Router execution layer, then create numbered contact sheets for human review. Use for batch image generation, multiple groups or candidates, requests such as “每组生成5张”, “生成40个候选”, “10路并发生图”, batch redraws, deadline-bounded generation, or review/selection boards. Do not use for a single ordinary image request.
---

# Batch Image Generation

Run deterministic batch scheduling without using child Agents for paid image submissions. Keep `generate_image` and the unified Media Router as the only execution layer; never call provider-specific adapters.

## Workflow

1. Require the user to explicitly choose one supported ratio before submission: `21:9`, `16:9`, `3:2`, `4:3`, `1:1`, `3:4`, `2:3`, or `9:16`.
2. Confirm the batch is intentional because each candidate may consume credits. Skip this confirmation for `-DryRun`; confirm before the first real run.
3. Build a JSON manifest from [references/manifest-schema.md](references/manifest-schema.md). Preserve reference-image order. Do not proactively ask for a route; if the user explicitly names one supported, unambiguous image route, set the batch-wide `image_provider` so every candidate goes directly to that route.
4. Run `scripts/run_batch.py` through the package entry point. Default to 10 in-flight tasks and at least 1 second between real submission starts. Estimate one minute per concurrent wave, then set the maximum generation-stage wait to 1.5 times that estimate.
5. At the deadline, stop dispatching, terminate local waits, and mark all unfinished tasks `abandoned`. Never query, reconcile, retry, or silently resubmit abandoned tasks.
6. Collect only successful images already landed before the deadline.
7. Create one contact sheet per group. Put the group’s original/reference image first, followed by numbered candidate slots. Preserve blank slots for missing results.
8. Return the contact sheets for human review. Do not perform automatic visual QA, dimension checks, scoring, ranking, or candidate rejection.

## Commands

From `packages/Codex_Batch_Image`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run-batch-image-generation.ps1 -Manifest <manifest.json>
```

Preview the plan without paid submissions by adding `-DryRun`.

## Operating Rules

- Treat the stage deadline as wall-clock time beginning when the runner starts.
- Calculate the estimate as `ceil(planned candidate count / concurrency) * 60 seconds`, then calculate the default whole-batch deadline as `estimate * 1.5`. For example, 40 candidates at concurrency 10 have a 4-minute estimate and a 6-minute deadline. An explicit positive `deadline_seconds` in the manifest overrides the calculated deadline.
- Set `original_image` explicitly whenever a group has multiple references so a material/style reference cannot become review slot 0 by accident.
- Keep job identity stable as `batch_id:group_id:candidate_index:prompt_version`. SQLite uniqueness prevents duplicate submission.
- A single failure must not block unrelated jobs.
- Do not automatically retry `failed` or `abandoned` jobs. A补图 request creates a new batch ID.
- Keep prompts out of logs. Record only prompt length and SHA-256 metadata.
- Existing adapter concurrency limits remain authoritative. Ten batch workers may wait on Media Router capacity.
- Use child Agents only for bounded diagnosis or ambiguous input mapping, never as the generation scheduler.

## Outputs

Write `batch-state.sqlite3`, `summary.json`, collected images under `results/<group>/`, and review boards under `review/`. Report partial completion plainly; missing candidates are expected after failures or the hard deadline.
