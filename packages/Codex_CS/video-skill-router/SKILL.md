---
name: video-skill-router
description: 根据用户想制作的视频主题、用途、主体、风格和叙事方式，从 Codex_CS 正式业务 Skill 库定位合适的 Skill，并编排从用户确认 Skill、画幅比例和时长，到项目素材槽、生图选择、CS 首版提示词、修订确认和视频生成的完整短流程。用于用户表示想使用 Skill 制作视频、寻找适合的视频 Skill，或提出可由业务 Skill 承接的视频创作意图时。不得根据用户已有素材反向决定创作目标。
---

# 视频业务 Skill 路由

## 强制流程

按以下顺序执行，不得跳过确认节点，也不得把 Codex_DT 作为首版提示词的默认作者。

1. 从用户描述中提取用途、核心主体、视觉风格、叙事结构和镜头偏好。
2. 优先执行精确名称或别名查询；否则使用本地意图注册表召回候选。不以用户已有素材作为选择 Skill 的主要依据。
3. 唯一高置信命中也必须向用户展示正式 Skill 名称并取得明确确认；候选接近时展示最多三个候选及命中原因；无可靠匹配时回退到通用 Codex_DT。
4. 在创建项目之前，一次性确认以下三项：
   - Skill 正式名称；
   - 画幅比例；
   - 视频时长。
5. 用户确认三项设置后，加载所选 Skill 的 `contract.json`，由每个槽的 `count_rule` 根据时长计算 `planned_count`，再调用 `project-pipeline` 创建项目目录和按 contract 素材槽划分的目录。不得用全库统一的“每 N 秒一张”替代 Skill 自己的节奏规则。
6. 向用户输出每个素材槽的绝对可点击目录链接，说明槽位用途、计划数量、规则是硬性还是推荐、顺序要求；不得只给相对路径或纯文本路径。链接目标必须直接使用管线返回的 `source_dir_link_target`，不得使用 `source_dir` 手工拼接。Windows 路径必须保持正斜杠（例如 `D:/workspace/materials`），不得把反斜杠路径写入 Markdown 链接，也不得改写为 `file://` URI；路径含空格时用尖括号包围整个目标。
7. 询问用户是否需要进入图片生成阶段，并等待用户把源图放入相应素材槽：
   - `generate`：使用统一 `generate_image` 生成或编辑图片，把结果回填并锁定为该槽的最终图片；
   - `user_supplied`：不调用生图，校验后直接把用户放入槽内的图片锁定为最终图片。
8. 所有必选槽均有最终图片后，加载所选业务 Skill 的 `SKILL.md` 与它要求的 references，由该 CS Skill 根据最终图片、比例和时长直接生成首版视频提示词。
9. 向用户展示当前提示词并只要求一次简单确认：回复确认则立即调用统一 `generate_video`；直接提出修改意见则进入第 10 步。
10. 任何提示词修改都自动交给 Codex_DT，用户无需选择是否使用 DT：
    - 明确、局部或参数型修改：直接按意见修订，不检索提示词语料库；
    - 模糊、审美型、创意型或整体重构：检索最多 3 个高相关案例，只提取可迁移结构后修订；
    - 每次修订都必须携带当前提示词、用户意见、CS Skill 强制规则、素材绑定及顺序、比例、时长和不可改变项；不得覆盖用户未要求改变的业务约束。
11. 每个新版本都使旧确认失效，重新展示并等待用户确认；确认后调用统一 `generate_video`。不生成额外审核报告，不执行 CS、DT 之间的往返审批。

## 项目状态

主流程至少记录以下状态；具体文件结构和命令接口以 `project-pipeline` 实现为准：

```text
awaiting_skill_confirmation
→ awaiting_video_settings
→ project_initialized
→ awaiting_image_stage_choice
→ collecting_source_images
→ generating_images 或 using_user_images
→ final_images_ready
→ authoring_cs_prompt
→ awaiting_prompt_confirmation
→ revising_with_dt（仅用户要求修改时）
→ awaiting_prompt_confirmation
→ generating_video
→ completed
```

每版提示词至少记录版本号、作者 `cs_skill | dt_assisted`、用户反馈、状态和内容哈希；最终提交必须绑定已确认提示词版本与最终素材集合。

## 本地命令

在 `packages/Codex_CS` 中查询 Skill：

```powershell
python skill-registry/scripts/lookup_skill.py "<用户创作意图>"
```

查询入口会在检索前验证注册表与正式 Skill 凭证；如返回 `registry_issues` 或非零退出码，先运行：

```powershell
python skill-registry/scripts/build_registry.py
```

用户确认 Skill、比例和时长后，使用 `project-pipeline` 提供的项目创建命令。不得自行另建不受管线管理的目录。项目命令返回素材槽绝对路径后，把这些路径作为可点击链接交给用户。

```powershell
python project-pipeline/scripts/project_pipeline.py create --skill-id <skill-id> --display-name "<正式名称>" --ratio <画幅比例> --duration <秒数> --skill-confirmed
```

读取 JSON 输出中的 `project_id`、`project_dir` 和 `material_directories`。其中 `planned_count` 已由用户时长和该 Skill 的槽位节奏规则计算。对每个素材槽都把 `source_dir_link_target` 作为用户投放源图的绝对可点击链接目标；`source_dir` 只表示文件系统路径，禁止直接插入 Markdown。`final_dir` 只用于统一生图结果回填或管线锁定最终图片；如确需展示其链接，同样使用 `final_dir_link_target`。

用户选择图片阶段后运行：

```powershell
python project-pipeline/scripts/project_pipeline.py choose-image-stage <project-id> --mode user_supplied
python project-pipeline/scripts/project_pipeline.py choose-image-stage <project-id> --mode generate
```

用户完成源图投放后先扫描：

```powershell
python project-pipeline/scripts/project_pipeline.py scan <project-id>
```

- `user_supplied`：扫描通过后运行 `lock-final <project-id> --use-source`，把源图复制并锁定为最终图片。
- `generate`：通过统一 `generate_image` 处理 `source_dir` 内的源图，将结果写入对应 `final_dir`；随后运行 `lock-final <project-id>`。不得用 `--use-source` 代替生图结果。

首版 CS 提示词、DT 修订和用户确认分别写回项目：

```powershell
python project-pipeline/scripts/project_pipeline.py set-cs-prompt <project-id> --file <prompt-file>
python project-pipeline/scripts/project_pipeline.py request-revision <project-id> --feedback "<用户意见>"
python project-pipeline/scripts/project_pipeline.py set-dt-revision <project-id> --file <prompt-file>
python project-pipeline/scripts/project_pipeline.py confirm-prompt <project-id>
python project-pipeline/scripts/project_pipeline.py start-generation <project-id>
```

统一视频生成成功后运行 `complete <project-id> --external-result "<结果引用>"`；仅查看当前项目时运行 `show <project-id>`。所有命令均返回 JSON，不得自行篡改项目状态文件。

## 交互约定

首次提示词固定使用：

> 提示词已生成。回复“确认”开始生成视频；如需修改，直接说明修改内容。

修订后固定使用：

> 已按你的意见更新提示词。回复“确认”开始生成视频，或继续说明需要修改的内容。

用户只表示不满意而没有修改方向时，只问一个简短问题，例如：

> 你最希望修改哪一部分：画面内容、动作运镜，还是整体风格？

## 决策边界

- 用户明确指定 Skill 名称、ID 或别名时可直接定位，但仍须确认正式名称、比例和时长。
- 查询阶段只使用已编译索引，不读取所有 Skill 正文。
- CS Skill 拥有首版提示词生成主权；Codex_DT 只负责用户提出修改后的受约束修订，或无可靠业务 Skill 时的通用创作。
- 不让用户选择内部作者，不暴露不必要的 CS/DT 编排细节。
- 不选择或暴露 provider、实际模型、分辨率、轮询和下载策略。
- 普通生图只调用统一 `generate_image`；普通视频生成只调用统一 `generate_video`。
- 不直接调用 Dreamina CLI 或任何 provider 专用适配器。
