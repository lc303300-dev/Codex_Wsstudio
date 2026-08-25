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
        "video_count": {"type": "integer", "minimum": 1, "maximum": 10, "default": 1, "description": "Number of independent videos to submit concurrently; each consumes credits."},
        "video_group": {"type": "string", "minLength": 1, "maxLength": 20, "description": "Dreamina group base name. The router prepends the local submission date as YYYY_MM_DD-; the date prefix does not count toward this 20-character limit."},
    },
    "required": ["prompt"],
    "additionalProperties": False,
}
