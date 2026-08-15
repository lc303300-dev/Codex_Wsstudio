IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "minLength": 1},
        "images": {"type": "array", "items": {"type": "string"}, "default": []},
        "image_ratio": {"type": "string", "enum": ["21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"]},
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
        "video_duration": {"type": "string", "pattern": "^(?:[4-9]|[1-2][0-9]|30)$"},
        "video_ratio": {"type": "string", "enum": ["1:1", "3:4", "16:9", "4:3", "9:16", "21:9"]},
        "video_model": {"type": "string", "enum": ["seedance2.0mini", "seedance2.0fast_vip", "seedance2.0_vip", "seedance2.5"]},
        "video_model_selection_source": {"type": "string", "enum": ["user_explicit"]},
        "video_execution_mode": {"type": "string", "enum": ["production", "test_submit_only"], "default": "production"},
        "video_resolution": {"type": "string", "enum": ["480p", "720p", "1080p", "4k"]},
    },
    "required": ["prompt"],
    "additionalProperties": False,
}
