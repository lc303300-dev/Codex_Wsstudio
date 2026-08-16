# Codex_IS operating rules

- Treat every published business Skill contract as the sole authority for accepted material slots, order, counts, roles, and output structure.
- Keep business Skills provider-neutral. They author prompts and stop for confirmation; they never choose a provider, submit paid work, poll, retry, or download.
- Require an explicit supported image ratio before project creation or image execution.
- Route one candidate through unified `generate_image`; route multiple scenes or candidates through the global `batch-image-generation` Skill after explicit paid-batch confirmation.
- Keep user materials, normalized provider inputs, project state, registries, logs, and results under `.codex-is-private/` or an explicit external result directory.
- Never inspect an original local raster directly. Create and inspect only a preview with longest edge at most 1024 px. Normalize EXIF orientation and resize provider inputs whose longest edge exceeds 1920 px without overwriting originals.
- Do not record full prompt content in operational logs. Record prompt version, author, length, and SHA-256; prompt bodies belong only in the project `prompts/` directory.

