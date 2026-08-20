from __future__ import annotations

SUPPORTED_IMAGE_RATIOS = {"21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"}


class ImageSpec:
    def __init__(self, task: str, brief: str, image_ratio: str | None, assets: list[dict], constraints: dict):
        self.schema = "codex-flow-image-spec/v1"
        self.task = task
        self.brief = brief
        self.image_ratio = image_ratio
        self.assets = assets
        self.constraints = constraints

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "task": self.task,
            "brief": self.brief,
            "image_ratio": self.image_ratio,
            "assets": self.assets,
            "constraints": self.constraints,
        }


def generic_image_spec(brief: str, image_ratio: str | None = None, *, has_target_image: bool = False, has_style_reference: bool = False) -> ImageSpec:
    if not brief.strip():
        raise ValueError("brief is required")
    if image_ratio is not None and image_ratio not in SUPPORTED_IMAGE_RATIOS:
        raise ValueError("unsupported image ratio")
    assets = []
    constraints = {"must_preserve": [], "must_not_transfer": []}
    task = "generate"
    if has_target_image:
        assets.append({"id": "target", "role": "preserve_content_and_composition"})
        task = "edit"
    if has_style_reference:
        assets.append({"id": "style_reference", "role": "transfer_visual_language_only"})
        constraints = {
            "must_preserve": ["target identity", "target composition", "target spatial relationships"],
            "must_not_transfer": ["style reference subject", "style reference composition", "style reference text"],
        }
        task = "reference_style_redraw" if has_target_image else "style_reference_generate"
    return ImageSpec(task, brief.strip(), image_ratio, assets, constraints)
