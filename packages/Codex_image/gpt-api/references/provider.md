# APIMart GPT Image 2

Source: `https://docs.apimart.ai/en/api-reference/images/gpt-image-2/generation.md`.
Chinese documentation: `https://docs.apimart.ai/cn`.

- Submit: `POST https://api.apimart.ai/v1/images/generations`
- Poll: `GET https://api.apimart.ai/v1/tasks/{task_id}?language=en`
- Model: `gpt-image-2`
- Authentication: `Authorization: Bearer <APIMART_API_KEY>`
- Resolution values: `1k`, `2k`, `4k`
- Reference field: `image_urls`, supporting public URLs and full base64 data URIs
- Result URL: `data.result.images[0].url[0]`
- Independence: `official_fallback=false`; do not call another local pipeline
