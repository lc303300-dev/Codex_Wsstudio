---
name: generic-image
description: 将未命中已注册 Skill 的图片需求编排为模型无关的 ImageSpec，并按需检索社区图像案例后交给统一图片路由。
---

# 通用图片编排

仅在 Codex Flow 快查未高置信命中任何已注册图片 Skill 时使用。

1. 提取用户的主体、场景、构图、文字、风格、约束和参考素材角色。
2. 使用 `platform/image_spec.py` 的 `generic_image_spec` 形成模型无关的 ImageSpec。
3. 当路由结果标记社区语料为 recommended 时，先从统一 Registry 所选原型读取结构化模板；再用 `platform/style_library.py cases` 读取至多五个带来源的案例。只提炼可泛化的结构与约束，不复制案例成品内容。
4. 目标图与风格图同时存在时，将目标图设为 `preserve_content_and_composition`，将风格图设为 `transfer_visual_language_only`。明确禁止迁移风格图的主体、构图和文字。
5. 进入付费生成前，要求用户明确选择支持的图片比例。随后只调用统一 `generate_image`；不得选择提供商、模型、密钥或私有执行参数。

ImageSpec 是编排中间层，不是任何模型的原始输入格式。统一图片路由负责将最终提示词和参考图片编译给当前选中的图片后端。
