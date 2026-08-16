---
name: image-skill-router
description: 从 Codex_IS 正式图片业务 Skill 库按用户创作目标匹配能力，并编排 Skill 名称、画幅比例、场景数、每组候选数、契约素材槽、提示词版本、付费批次确认和统一图片执行。用于九宫格分镜、图片业务 Skill 查找、多参考合成、产品组图、建筑分镜、角色一致性或其他应由受治理图片业务 Skill 承接的请求；不得根据用户已有文件反向决定创作目标。
---

# 图片业务 Skill 路由

## 强制流程

1. 从用户目标中提取用途、主体、输出结构、风格和一致性要求。先按正式名称或别名查询，再按意图查询本地注册表。不得把用户已有素材当作选择 Skill 的主要依据。
2. 展示命中的正式 Skill 名称并取得明确确认。候选接近时最多展示三个；没有可靠匹配时说明当前正式库不覆盖，不得临时扩展某个 Skill 的素材契约。
3. 在创建项目之前确认正式 Skill 名称、支持的画幅比例、场景数量、每个场景的候选数量。即使用户明确点名 Skill，也不得跳过比例和数量确认。
4. 读取所选 `contract.json`，调用项目管线动态创建其中声明的素材槽。拒绝任何未声明图片，不得临时添加风格图、范例图或镜头参考图。
5. 将管线返回的 `source_dir_link_target` 直接作为本地 Markdown 链接目标交给用户。Windows 目标必须是绝对正斜杠路径，不能从 `source_dir` 手工重建。
6. 用户投放素材后，先按工作区图片安全规则创建预览进行观察；发送到图片执行层前校正方向，并把最长边超过 1920 px 的副本等比缩小到项目私有目录，绝不覆盖原图。
7. 锁定素材后加载业务 Skill 的 `SKILL.md`，并按它的指示读取所需 references。由业务 Skill编写提示词 V1；Router 不取代业务 Skill 作者。
8. 完整展示提示词并等待确认。任何修改生成新版本并使旧确认失效；任何素材替换清空确认并回到素材锁定与提示词编写阶段。
9. 确认后按总任务量分流：一个场景且一个候选使用统一 `generate_image`；多个场景或候选先取得明确付费批次确认，再使用全局 `batch-image-generation`。
10. 记录成功、失败或放弃项，不自动重试、不进行审美排名，也不把部分成功伪装为完整成功。

## 本地命令

```powershell
python skill-registry/scripts/registry.py build
python skill-registry/scripts/registry.py lookup "<用户创作目标>"
python project-pipeline/scripts/project_pipeline.py create --skill-id <skill-id> --display-name "<正式名称>" --ratio <比例> --candidate-count <每场景候选数> --scene-count <场景数> --skill-confirmed
python project-pipeline/scripts/project_pipeline.py lock-materials <project-id>
python project-pipeline/scripts/project_pipeline.py set-prompt <project-id> --file <prompt-file>
python project-pipeline/scripts/project_pipeline.py confirm-prompt <project-id>
python project-pipeline/scripts/project_pipeline.py confirm-paid-batch <project-id>
python project-pipeline/scripts/project_pipeline.py start-generation <project-id> --dry-run
```

仅当源图本身无需任何生成或编辑即可成为最终参考时，才使用 `lock-materials <project-id> --use-source`。`--dry-run` 只验证状态和写入清单，不调用付费工具。正式提交仍由当前会话可用的统一工具完成，项目脚本不调用供应商。

## 决策边界

- 业务 Skill 只理解意图、约束引用角色、编写提示词并等待确认，不选择供应商、模型、价格、并发、轮询、下载或重试策略。
- 只在用户当前明确指定且统一工具支持时传 `image_provider`；否则使用统一路由的默认顺序。
- 提示词正文不得包含供应商名、实际模型、分辨率、费用、并发、下载路径或内部工作流说明。
- 观察原图必须通过最长边不超过 1024 px 的预览。不得从一张底图推断不可见背面或被遮挡结构。
- 批量调度由 `batch-image-generation` 的确定性调度器负责，不能用生成子 Agent 替代。

