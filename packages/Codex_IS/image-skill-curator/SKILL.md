---
name: image-skill-curator
description: 将用户指定的图片业务 Skill Markdown、工作流蓝图、提示词经验或现有 Skill 包整理为可审计、可验证、可发布的 Codex_IS 标准业务 Skill。用于新增、迁移、修订、去重、审核或入库图片业务 Skill；负责区分平台通用规则与业务局部规则、生成素材契约和路由元数据、保留专业经验、识别冲突、输出审核报告，并仅在用户明确批准后发布。不得生成图片、选择供应商或调用付费执行层。
---

# 图片业务 Skill 入库治理

## 强制流程

1. 读取用户指定的主要来源和明确补充材料，记录来源文件名与 SHA-256。不得把未指定的历史图片或提示词秘密并入。
2. 查询正式库的 `skill_id`、正式名称、别名和意图，判断新增、修订、合并或重复。发现近似包时先报告差异。
3. 把来源事实分类为：contract facts、workflow rules、creative guidance、failure cases、examples、platform rules。
4. 执行反泛化检查。具体槽名、槽数、面板数、布局、时序、镜头池、材质、场景和主体默认属于当前 Skill 局部规则，不得写成全库 schema。
5. 从 `assets/business-skill-template/` 创建候选包。保持 `SKILL.md` 简短；详细知识放在一层 `references/`。frontmatter 只能有 `name` 和 `description`。
6. 生成 `contract.json` 和 `routing.json`。每个素材槽必须有清晰角色；`allowed_slot_ids` 必须与槽顺序一致；未声明素材必须被拒绝。
7. 运行结构、JSON Schema、语义、安全和污染校验，生成 `intake-report.json`。存在阻断问题、来源矛盾或缺失知识时保持 `needs_review`，不得发布。
8. 展示正式名称、触发范围、素材契约、输出契约、局部规则、明确排除的泛化项、验证问题和目标路径。只有用户明确批准入库才发布。
9. 发布时复制到临时目录，移除旧收据，写入包含来源哈希和包哈希的 `intake-receipt.json`，再次完整校验后原子移动到 `business-skills/<skill-id>/`。禁止覆盖已有正式包。
10. 发布后重建注册表。注册表更新失败时撤销新包，不能留下半成功状态。

## 必读资源

- 提取前阅读 `references/image-business-skill-standard.md`。
- 审核时阅读 `references/review-checklist.md`。
- 包结构与占位约定以 `assets/business-skill-template/` 为准。

## 本地命令

```powershell
python image-skill-curator/scripts/scaffold_business_skill.py <skill-id> --output <draft-root>
python image-skill-curator/scripts/audit_skill.py <draft-package> --source <source-file> --report <report-path>
python image-skill-curator/scripts/publish_skill.py <draft-package> --source <source-file> --approved-by user
python image-skill-curator/scripts/upgrade_published_skill.py <published-package> --source <source-file> --approved-by user
```

`--approved-by user` 不能代替当前对话中真实发生的用户批准。

## 边界

- 不生成或编辑图片，不调用 `generate_image` 或批量任务。
- 不选择 provider、模型、分辨率、费用、并发、轮询、下载或重试策略。
- 不把范例图作为隐性知识上传到生成引用链。图片是否允许、数量与用途只由当前 contract 决定。
- 不把 `scene-storyboard-grid` 的双槽、3×3、九格、同一时刻、镜头池、事实账本或提示词模块当作全库默认。
- 不因模板存在字段就臆造业务事实；无法确定时写入阻断问题并停在批准前。
- 新包发布禁止覆盖；正式包修订必须重新审核、重新批准并通过 `upgrade_published_skill.py` 原子升级。
