---
name: video-skill-router
description: 根据用户想制作的视频主题、用途、主体、风格和叙事方式，从 Codex_CS 正式业务 Skill 库快速定位最合适的 Skill；选定后读取其素材契约，指导用户逐项准备所需图片、视频、音频和必要说明。用于用户表示想使用 Skill 制作视频、寻找适合的视频 Skill，或提出可由业务 Skill 承接的视频创作意图时。不得根据用户已有素材反向决定创作目标。
---

# 视频业务 Skill 路由

## 工作流

1. 从用户描述中提取想制作的视频用途、核心主体、视觉风格、叙事结构和镜头偏好。
2. 优先执行精确名称或别名查询；否则使用本地意图注册表召回候选。
3. 不以用户当前已经拥有的素材作为选择 Skill 的主要依据。素材只在选定 Skill 后用于判断已满足和缺失的契约项。
4. 高置信度唯一命中时选定该 Skill；候选接近时展示最多三个候选及命中原因；无可靠匹配时回退到通用 Codex_DT。
5. 选定后只加载该 Skill 的 `contract.json`，生成中文素材准备清单。
6. 逐轮记录已收到的素材槽数量，只询问仍缺失或数量不合法的项目。
7. 必选素材全部满足后，再加载该 Skill 的 `SKILL.md` 和任务需要的 references，交给 Codex_DT 创作提示词。

## 本地命令

在 Codex_CS checkout 中运行：

```powershell
python skill-registry/scripts/lookup_skill.py "<用户创作意图>" --json
python material-collection/material_collection.py business-skills/<skill-id>/contract.json
```

注册表不存在或过期时，先运行：

```powershell
python skill-registry/scripts/build_registry.py
```

## 决策边界

- 用户明确指定 Skill 名称、ID 或别名时直接定位。
- 不得仅因为用户碰巧上传了某类素材而改变其创作目标。
- 不读取所有 Skill 正文进行路由；查询阶段只使用已编译索引。
- 不选择 provider、实际模型、分辨率、轮询或下载策略。
- 不提交视频生成；付费执行继续由 Codex_DT 下游统一媒体路由负责。
