# Comfly OpenAI-Compatible Image API

- Base URL: `https://ai.comfly.org/v1`
- Authentication: `Authorization: Bearer <COMFLY_API_KEY>`
- Text-to-image: `POST /images/generations`
- Image editing: `POST /images/edits`
- Generation body: UTF-8 JSON with `Content-Type: application/json; charset=utf-8`
- Edit body: multipart form data; repeat the `image` file field and include `model`, `prompt`, `n`, `size`, and `response_format=url`
- Result URL: `data[0].url`; an empty `b64_json` is not a failure when the URL is usable
- Download headers: browser `User-Agent`, image-oriented `Accept`, and `Referer: https://ai.comfly.org/`
- Private configuration from the project root: `.codex-image-private/.env`
- `gemini-3.1-flash-image-preview` uses the 1K output class only. Accept `1K` or the documented 1K aspect-ratio sizes, and reject `2K`/`4K`.

## Model Routing

Use only this fixed, serial priority:

1. `gemini-3.1-flash-image-preview`
2. `gpt-image-2-all`
3. `gpt-image-2`

Advance only after an API failure, missing URL, download failure, non-image response, or empty output. Stop after the first success. Do not invoke another local pipeline or provider.

## Logging

Record each attempt, model, endpoint, operation, image count, response status, request or task ID when available, image URL, download status, failure stage, and final model. Store only a redacted prompt marker, its character count, and SHA-256 digest. Never record API keys, Authorization values, multipart image bodies, Base64 images, full prompts, or unfiltered provider error bodies.
