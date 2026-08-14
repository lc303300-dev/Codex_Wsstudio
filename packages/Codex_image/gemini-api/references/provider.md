# Google Gemini Direct Image API

Extracted from the original project route `tools/gemini_image_fallback.py`.

- Endpoint: `POST https://generativelanguage.googleapis.com/v1beta/interactions`
- Model: `gemini-3.1-flash-image`
- Header: `x-goog-api-key: <GEMINI_API_KEY>`
- Input: one text part followed by zero or more base64 image parts
- Output request: image/JPEG, `1K`, configurable aspect ratio
- Private configuration from the project root: `.codex-image-private/.env`
- Independence: do not call Dreamina, Seedance, APIMart, or GPT
