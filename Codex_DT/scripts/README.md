# Scripts

These scripts are intentionally thin wrappers around existing tools:

- `deploy_project.ps1` is the deployment entrypoint for `帮我部署这个项目`. It creates the runtime skeleton, writes `config/pipeline.local.json` for machine-local paths, validates required tools/resources, and checks Dreamina `user_credit` without submitting paid generation.
- `prepare_previews.ps1` uses the global Codex preview converter.
- `bootstrap_dialog_batch.py` is the first-turn entrypoint for multiple images dropped into a new Codex task. It imports the files, optionally prepares previews/manifests when duration is known, and stops before visual work, subagents, or paid generation.
- `start_text_batch.py` is the normal text-first entrypoint. It records the user's Chinese video request in `.codex-image-private/batches/<batch>/request.json`, creates an empty `inputs/<batch>/` drop folder, and prints the next commands to run after the user places images there.
- `import_dialog_images.py` imports images dropped into the opening Codex dialog by waiting until each attachment path is readable and size-stable, then delegating to `new_batch.py`.
- `new_batch.py` creates isolated batch folders and copies stable source images. By default it also waits briefly for image paths to become readable and size-stable before copying.
- `init_manifests.py` creates draft manifests from generated preview records. With `--batch`, it automatically reads private batch request metadata when present, so duration, ratio, and the original user brief do not need to be repeated.
- `search_forge.py` reads `seedance-forge` CSV and returns complete corpus matches.
- `update_forge_matches.py` writes `seedance-forge` matches back into manifests.
- `make_subagent_tasks.py` creates one bounded task prompt per image for Codex subagents. Add `--write-jobs` only when optional dispatch/result bookkeeping is needed.
- `image_job_status.py` prints optional per-image subagent dispatch/result state for one batch.
- `dispatch_plan.py` prints dispatchable task files and optional dispatch-recording commands for the next subagent wave.
- `record_image_dispatch.py` optionally records the Codex task id assigned to one image job. It is safe to re-run for the same image and agent id.
- `record_image_result.py` optionally records a completed image job. It uses a lock and can recover a missing dispatch when explicitly passed `--recover-missing-dispatch`.
- `review_subagent_outputs.py` optionally checks subagent deliverables for diagnostics.
- `build_review.py` creates a Chinese confirmation HTML page.
- `finalize_review.py` builds the review page and prints final status for one batch. Use `--auto-generate` for explicit auto-generation requests that should skip user confirmation, submit immediately, and wait until submitted videos are downloaded.
- `validate_batch.py` calls the mqrox Seedance 2.0 validator.
- `run_seedance_batch.ps1` calls the local Dreamina/Seedance CLI only for confirmed items.
- `wait_seedance_batch.py` polls submitted Dreamina tasks from `.codex-image-private/batches/<batch>/tasks.jsonl` with `query_result --download_dir` until every submitted item has an `.mp4` in `outputs/<batch>/videos/`, then prints absolute video paths.
- `pipeline_status.py` prints a compact state summary for the current workspace.

The visual recognition step is not implemented as a script because Codex vision is an agent tool, not a local Python/PowerShell API. Subagents inspect generated previews and write manifests; the main agent normally only prepares previews, delegates work, and builds the review page.
