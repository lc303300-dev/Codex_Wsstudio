IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "minLength": 1},
        "images": {"type": "array", "items": {"type": "string"}, "default": []},
        "image_ratio": {"type": "string", "enum": ["21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"]},
        "image_resolution": {
            "type": "string",
            "enum": ["1K", "2K", "4K"],
            "description": "Optional explicit resolution. When omitted, GPT image routes default to 4K and Gemini image routes default to 2K.",
        },
        "image_provider": {
            "type": "string",
            "description": "Optional user-explicit image route. Omit to use the default serial fallback order.",
            "enum": ["comfly-gemini-lite", "comfly-gpt-image-2", "dreamina-image"],
        },
    },
    "required": ["prompt", "image_ratio"],
    "additionalProperties": False,
}

VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "minLength": 1},
        "images": {"type": "array", "items": {"type": "string"}, "default": []},
        "videos": {"type": "array", "items": {"type": "string"}, "default": []},
        "audios": {"type": "array", "items": {"type": "string"}, "default": []},
        "video_duration": {"type": ["string", "integer"], "description": "Duration in seconds. Accepts 5, '5', '5s', or '5秒'; the router normalizes it to a plain integer for the CLI."},
        "video_ratio": {"type": "string", "enum": ["1:1", "3:4", "16:9", "4:3", "9:16", "21:9"]},
        "video_model": {"type": "string", "enum": ["seedance2.0mini", "seedance2.0fast_vip", "seedance2.0_vip", "seedance2.5"]},
        "video_model_selection_source": {"type": "string", "enum": ["user_explicit"]},
        "video_execution_mode": {"type": "string", "enum": ["production", "test_submit_only"], "default": "production"},
        "video_resolution": {"type": "string", "enum": ["480p", "720p", "1080p", "4k"]},
        "video_confirmation_model": {"type": "string", "enum": ["seedance2.0mini", "seedance2.0fast_vip", "seedance2.0_vip", "seedance2.5"]},
        "video_confirmation_resolution": {"type": "string", "enum": ["480p", "720p", "1080p", "4k"]},
        "video_confirmation_duration": {"type": ["string", "integer"], "description": "Confirmed duration in seconds; accepts the same normalized forms as video_duration."},
        "video_prompt_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$", "description": "SHA-256 of the exact reviewed prompt; required for production_submit_only."},
        "video_test_confirmation": {"type": "string", "enum": ["confirmed"], "description": "Explicit authorization for the internal reversible test submission channel."},
        "video_count": {"type": "integer", "minimum": 1, "maximum": 6, "default": 1, "description": "Number of independent videos to submit concurrently; each consumes credits."},
        "video_group": {"type": "string", "minLength": 1, "maxLength": 20, "description": "Dreamina group base name. The router prepends the local submission date as YYYY_MM_DD-; the date prefix does not count toward this 20-character limit."},
    },
    "required": ["prompt"],
    "additionalProperties": False,
}

GIF_SCHEMA = {
    "type": "object",
    "properties": {
        "input_dir": {"type": "string", "minLength": 1},
        "output_dir": {"type": "string"},
        "max_size_mb": {"type": "number", "exclusiveMinimum": 0, "default": 10},
        "recursive": {"type": "boolean", "default": False},
        "overwrite": {"type": "boolean", "default": False},
        "max_duration_sec": {"type": "number", "minimum": 0, "default": 0},
        "min_fps": {"type": "integer", "minimum": 1, "default": 1},
    },
    "required": ["input_dir"],
    "additionalProperties": False,
}

BATCH_IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "manifest": {"type": "string", "minLength": 1},
        "router_path": {"type": "string"},
        "dry_run": {"type": "boolean", "default": False},
        "paid_confirmation": {"type": "string", "enum": ["confirmed"]},
    },
    "required": ["manifest"],
    "additionalProperties": False,
}

DT_PREVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "batch": {"type": "string"},
        "input_directory": {"type": "string", "default": "inputs"},
        "output_directory": {"type": "string", "default": "previews"},
        "preview_tool": {"type": "string"},
        "max_long_edge": {"type": "integer", "minimum": 1, "maximum": 1024, "default": 1024},
    },
    "additionalProperties": False,
}

DT_START_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "duration": {"type": "integer", "minimum": 4, "maximum": 30},
        "request": {"type": "string", "minLength": 1},
        "ratio": {"type": "string", "enum": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]},
        "auto_generate": {"type": "boolean", "default": False},
        "model_version": {"type": "string", "enum": ["seedance2.5", "seedance2.0_vip", "seedance2.0fast_vip", "seedance2.0mini"]},
    },
    "required": ["name", "duration", "request"],
    "additionalProperties": False,
}

DT_VALIDATE_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "batch": {"type": "string"},
        "manifests": {"type": "string"},
        "tmp": {"type": "string"},
    },
    "additionalProperties": False,
}

FLOW_ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "minLength": 1},
        "capability": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5},
    },
    "required": ["query"],
    "additionalProperties": False,
}

TOOL_SCOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "need": {"type": "string", "minLength": 1},
        "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        "sources": {"type": "string"},
    },
    "required": ["need"],
    "additionalProperties": False,
}
