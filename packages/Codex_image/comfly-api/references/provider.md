# Comfly OpenAI-Compatible Image API

- Base URL: `https://ai.comfly.org/v1`
- Authentication: `Authorization: Bearer <COMFLY_API_KEY>`
- Text-to-image: `POST /images/generations`
- Image editing: `POST /images/edits`
- Generation body: UTF-8 JSON with `Content-Type: application/json; charset=utf-8`
- Edit body: multipart form data; repeat the `image` file field and include `model`, `prompt`, `n`, `size`, and `response_format=url`. Gemini requests also include their provider-specific `resolution` field; GPT Image 2 requests do not.
- Result URL: `data[0].url`; an empty `b64_json` is not a failure when the URL is usable
- Download headers: browser `User-Agent`, image-oriented `Accept`, and `Referer: https://ai.comfly.org/`
- Private configuration from the project root: `.codex-image-private/.env`
- Gemini uses `gemini-3.1-flash-image-preview` for 1K, `gemini-3.1-flash-image-preview-2k` for 2K, and `gemini-3.1-flash-image-preview-4k` for 4K.
- GPT Image 2 receives a concrete pixel `size`, not an aspect-ratio token or a `resolution` field. For example, 9:16 maps to `720x1280`, `1152x2048`, and `2160x3840` for the public 1K, 2K, and 4K choices.

## Model Routing

Available explicit models are:

1. `gemini-3.1-flash-image-preview`
2. `gemini-3.1-flash-image-preview-2k`
3. `gemini-3.1-flash-image-preview-4k`
4. `gpt-image-2`

Submit exactly the explicitly selected model. Do not invoke another local pipeline or provider.

## Logging

Record each attempt, model, endpoint, operation, image count, response status, request or task ID when available, image URL, download status, failure stage, and final model. Store only a redacted prompt marker, its character count, and SHA-256 digest. Never record API keys, Authorization values, multipart image bodies, Base64 images, full prompts, or unfiltered provider error bodies.
