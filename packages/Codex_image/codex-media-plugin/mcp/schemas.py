IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "minLength": 1},
        "images": {"type": "array", "items": {"type": "string"}, "default": []},
    },
    "required": ["prompt"],
    "additionalProperties": False,
}

VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "minLength": 1},
        "images": {"type": "array", "items": {"type": "string"}, "default": []},
        "videos": {"type": "array", "items": {"type": "string"}, "default": []},
        "audios": {"type": "array", "items": {"type": "string"}, "default": []},
    },
    "required": ["prompt"],
    "additionalProperties": False,
}
