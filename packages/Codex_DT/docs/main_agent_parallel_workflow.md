# Main-agent sequential workflow

This document describes how the main Codex agent should handle batch image prompt drafting without subagents.

## Main-agent responsibilities

The main agent owns shared coordination:

1. Prepare previews.
2. Initialize manifests.
3. Draft and refine all prompts in the main Agent.
4. Build the review page.
5. Ask the user to confirm prompts.
6. Submit confirmed items to Dreamina CLI.

The main agent should not let subagents submit generation jobs. Paid generation remains centralized after user confirmation.
If the user explicitly asks for auto-generation, for example `自动生成视频` or
`全自动生成视频`, skip the confirmation wait after the review page is built.
The main agent still owns paid generation submission.
The main agent owns prompt quality review and composes the review page for the user.

## Recommended command sequence before delegation

For a normal text-first request, create the batch and image drop folder first:

```powershell
python scripts/start_text_batch.py --name <short-description> --duration 5 --request "<original-user-request>"
```

Show the printed `image_drop_dir_link_target` as a clickable local path and ask the user to place images there. Use it verbatim as the Markdown target; do not insert the raw Windows `image_drop_dir` or a `file://` URI. Stop until the user confirms the files have been added. Then continue:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1 -Batch <batch>
python scripts/init_manifests.py --batch <batch>
```

For text-first batches, `init_manifests.py` reads `.codex-image-private/batches/<batch>/request.json` automatically. The saved Chinese request is copied into `manifest.user_requirements.motion_zh` for every image unless a per-image `--brief` override is passed.

For a brand-new task whose opening user message contains multiple image attachments, first run only:

```powershell
python scripts/bootstrap_dialog_batch.py --name <short-description> --duration 5 --images <image1> [<image2> ...]
```

Then stop the first response and tell the user the printed `bootstrap_batch=...`.
Continue prompt drafting in the main Agent after the user sends a follow-up for that batch.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1
python scripts/init_manifests.py --duration 5
```

The duration is mandatory. If the user provides only images, ask for the target duration before initializing manifests. Ratio is optional: when the user does not provide it, `init_manifests.py` chooses the nearest allowed ratio from the image's original width and height. Supported ratio values are `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, and `9:16`.

Use batch-isolated commands for new work:

```powershell
python scripts/bootstrap_dialog_batch.py --name <short-description> --duration 5 --images <image1> [<image2> ...]
python scripts/start_text_batch.py --name <short-description> --duration 5 --request "<original-user-request>"
python scripts/import_dialog_images.py --name <short-description> --images <image1> [<image2> ...]
python scripts/new_batch.py --name <short-description> --images <image1> [<image2> ...]
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1 -Batch <batch>
python scripts/init_manifests.py --batch <batch>
```

Use `bootstrap_dialog_batch.py` for opening-dialog multi-image attachments in a new Codex task. It intentionally stops before prompt drafting, review finalization, and Dreamina generation.
Use `import_dialog_images.py` when the files came from images dropped into the opening Codex dialog. It waits for every attachment path to be readable and size-stable before copying. Use `new_batch.py` directly only for paths that already exist as stable local files.

Use the `batch=YYYYMMDD-HHMM-<name>` value printed by `new_batch.py` in the
following commands. If you provide `--batch` manually, include the current hour
and minute in the id, for example `20260730-1534-window`.

## Review and generation

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

`finalize_review.py` only builds the review page by default. Use `--validate`
and `--record-results` when you intentionally want diagnostic/bookkeeping output.

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
