# Main agent parallel workflow

This document describes how the main Codex agent should use subagents for batch image prompt drafting.

## Main-agent responsibilities

The main agent owns shared coordination:

1. Prepare previews.
2. Initialize manifests.
3. Generate task prompt files.
4. Spawn one subagent per image or per small batch.
5. Wait for subagents.
6. Build the review page.
7. Ask the user to confirm prompts.
8. Submit confirmed items to Dreamina CLI.

The main agent should not let subagents submit generation jobs. Paid generation remains centralized after user confirmation.
If the user explicitly asks for auto-generation, for example `自动生成视频` or
`全自动生成视频`, skip the confirmation wait after the review page is built.
The main agent still owns paid generation submission.
The main agent should not inspect source images or re-review every subagent output by default. Its normal job after delegation is to compose the review page so the user can judge the prompt quality.

## Recommended command sequence before delegation

For a normal text-first request, create the batch and image drop folder first:

```powershell
python scripts/start_text_batch.py --name <short-description> --duration 5 --request "<original-user-request>"
```

Show the printed `image_drop_dir_link_target` as a clickable local path and ask the user to place images there. Use it verbatim as the Markdown target; do not insert the raw Windows `image_drop_dir` or a `file://` URI. Stop until the user confirms the files have been added. Then continue:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1 -Batch <batch>
python scripts/init_manifests.py --batch <batch>
python scripts/make_subagent_tasks.py --batch <batch> --status draft
```

For text-first batches, `init_manifests.py` reads `.codex-image-private/batches/<batch>/request.json` automatically. The saved Chinese request is copied into `manifest.user_requirements.motion_zh` for every image unless a per-image `--brief` override is passed.

For a brand-new task whose opening user message contains multiple image attachments, first run only:

```powershell
python scripts/bootstrap_dialog_batch.py --name <short-description> --duration 5 --images <image1> [<image2> ...]
```

Then stop the first response and tell the user the printed `bootstrap_batch=...`.
Do not spawn subagents from the same opening turn. Continue with delegation only
after the user sends a follow-up for that batch.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1
python scripts/init_manifests.py --duration 5
python scripts/make_subagent_tasks.py --status draft
```

The duration is mandatory. If the user provides only images, ask for the target duration before initializing manifests. Ratio is optional: when the user does not provide it, `init_manifests.py` chooses the nearest allowed ratio from the image's original width and height. Supported ratio values are `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, and `9:16`.

The generated task prompts are saved in:

```text
.codex-image-private/batches/<batch>/subagent-tasks/
```

Use batch-isolated commands for new work:

```powershell
python scripts/bootstrap_dialog_batch.py --name <short-description> --duration 5 --images <image1> [<image2> ...]
python scripts/start_text_batch.py --name <short-description> --duration 5 --request "<original-user-request>"
python scripts/import_dialog_images.py --name <short-description> --images <image1> [<image2> ...]
python scripts/new_batch.py --name <short-description> --images <image1> [<image2> ...]
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1 -Batch <batch>
python scripts/init_manifests.py --batch <batch>
python scripts/make_subagent_tasks.py --batch <batch> --status draft
```

Use `bootstrap_dialog_batch.py` for opening-dialog multi-image attachments in a new Codex task. It intentionally stops before `make_subagent_tasks.py`, subagent spawning, review finalization, and Dreamina generation.
Use `import_dialog_images.py` when the files came from images dropped into the opening Codex dialog. It waits for every attachment path to be readable and size-stable before copying. Use `new_batch.py` directly only for paths that already exist as stable local files.

Use the `batch=YYYYMMDD-HHMM-<name>` value printed by `new_batch.py` in the
following commands. If you provide `--batch` manually, include the current hour
and minute in the id, for example `20260730-1534-window`.

## Delegation pattern

Spawn one subagent for each task file. Each subagent receives the task file content as its prompt and should edit only:

```text
manifests/<batch>/<id>.json
prompts/<batch>/<id>.prompt.txt
```

For many images, use small waves to avoid too many concurrent workers. A practical wave size is 3 to 5 images.

Creating files in `.codex-image-private/batches/<batch>/subagent-tasks/` is not delegation. The main agent must use the available subagent mechanism to start workers and wait for them before building the review page.

Optional: for large batches that need progress tracking, record the runtime task id that will own the image:

```powershell
python scripts/make_subagent_tasks.py --batch <batch> --status draft --write-jobs
python scripts/record_image_dispatch.py --batch <batch> --image-id <id> --agent-id <codex-task-id>
```

Optional: if dispatches were recorded and you need completion bookkeeping, record the result:

```powershell
python scripts/record_image_result.py --batch <batch> --image-id <id> --agent-id <codex-task-id>
```

Use `scripts/image_job_status.py --batch <batch>` between waves to see pending, dispatched, and recorded image jobs.
Use `scripts/dispatch_plan.py --batch <batch>` before a wave to list dispatchable task files and the exact `record_image_dispatch.py` commands to run after each subagent is spawned.

## After subagents finish

Run:

```powershell
python scripts/finalize_review.py --batch <batch>
```

For explicit auto-generation requests, run:

```powershell
python scripts/finalize_review.py --batch <batch> --auto-generate
```

Then open or share:

```text
review/<batch>/index.html
```

The review page is Chinese and includes only:

- image preview
- Chinese Dreamina prompt

`finalize_review.py` only builds the review page by default. Use
`--validate`, `--check-subagent-outputs`, and `--record-results` when you
intentionally want the older diagnostic/bookkeeping path. Do not run multiple
`record_image_result.py` commands in parallel against the same batch because
they update the same `.codex-image-private/batches/<batch>/image_jobs.json` file.

## Confirmation and generation

Only after the user approves a prompt, set:

```json
"prompt": {
  "status": "confirmed"
}
```

Then submit:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_seedance_batch.ps1 -Batch <batch> -Yes
```

The script checks Dreamina credit unless `-SkipCreditCheck` is supplied.
In auto-generation mode, `finalize_review.py --auto-generate` marks
`ready_for_review` prompts as `confirmed` and runs the same submission script
with `-Yes`.
