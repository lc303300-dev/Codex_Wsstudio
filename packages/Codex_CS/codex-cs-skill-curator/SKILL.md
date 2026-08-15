---
name: codex-cs-skill-curator
description: 将用户在对话中上传或指定的单个视频 Skill Markdown、旧版 Skill 包、社区经验文档或提示词资料，整理为可审计、可验证、可发布的 Codex_CS 标准业务 Skill。用于新增、迁移、修订、合并、去重或入库视频 Skill；负责保留原始专业经验与社区经验、生成确定性素材契约、识别冲突和歧义、输出审核报告，并在用户明确确认后发布。不得用于实际生成图片或视频。
---

# Codex_CS 视频 Skill 入库治理

把每次入库视为一次受控编译：原始资料是不可修改的来源，标准 Skill 包是编译产物，发布凭证决定它能否进入正式 Skill 库。

## 先读取的规范

开始任何入库、迁移或更新前，完整阅读：

- `references/video-skill-package-standard.md`：标准包和字段规范。
- `references/intake-classification-guide.md`：如何区分契约、创意经验、社区经验、失败案例与示例。
- `references/review-checklist.md`：发布前必须展示给用户的审核项目。
- `references/legacy-library-findings.md`：本模板从现有 Codex_CS Skill 库提炼出的结构问题与设计依据。
- `references/dt-creative-supplement.md`：缺少提示词范例或创意草稿时，如何请求 Codex_DT 进行受限补充。
- `references/example-quality-benchmark.md`：用正式库优秀范例提炼的完整正例、反例、边界案例和可执行性审核尺度；只借鉴结构，不迁移题材规则或推断契约。

使用 `assets/business-skill-template/` 作为唯一业务 Skill 模板。不要从某个已有业务 Skill 复制结构，因为旧 Skill 可能含有历史格式或错误契约。

## 入库工作流

### 1. 接收并封存来源

接收用户上传的 `.md`、Skill 目录或相关资料。识别编码后按 UTF-8 读取，但不修改原文件。记录每个来源的文件名、SHA-256 和检测到的编码。

先运行只读预检：

```powershell
python scripts/inspect_skill_source.py <uploaded-skill.md>
```

预检只报告来源事实和风险线索，不生成或猜测最终素材契约。

将来源视为证据，不视为已经正确的执行契约。剥离 `START OF FILE`、聊天包装、终端输出和导出标记时，只修改暂存副本。

### 2. 检查重复与边界

比较现有正式库中的 `skill_id`、显示名称、来源哈希和内容相似性。区分：

- 完全重复：停止创建新 Skill，建议更新或复用现有包。
- 高度重叠：说明差异，要求用户决定合并还是独立发布。
- 新能力：继续入库。

隔离并报告本机路径、凭据、CLI 命令、provider 选择、真实模型选择、轮询下载以及项目专属名称。这些内容不得进入执行契约。

### 3. 提取知识并分类

依据分类指南逐条整理，不丢弃有价值信息：

- 确定性的素材类型、数量、顺序、角色和必选性写入 `contract.json`。
- 每次执行都需要遵守的简短流程写入 `SKILL.md`。
- 用户会怎样描述这类创作意图、常用别名、主体、风格、叙事模式和排除意图写入 `routing.json`；不得用用户已有素材反向定义意图。
- 专业创意方法写入 `references/creative-guidance.md`。
- 社区经验原意写入 `references/community-experience.md`，并标记证据等级与适用条件。
- 失败表现、原因和规避方法写入 `references/failure-cases.md`。
- 正例、反例和边界案例写入 `references/examples.md`；示例不得参与契约推导。

模型版本、平台名称和历史命令只可作为来源背景保留，必须明确写成“历史来源信息，不决定当前执行模型”。

### 4. 生成确定性契约

从模板生成 `contract.json`。只填写来源能够确定的事实，不猜测：

- 至少声明一项 image、video 或 audio 参考素材。
- 禁止 `text2video`。
- 用 `min_count`、`max_count` 表达数量；未知上限使用 `null`，不要虚构数字。
- 用稳定英文小写 `id` 标识素材槽，用中文说明其业务含义。
- 明确素材是否有序、是否需要视觉观察及其绑定用途。
- 用户明确指令的优先级必须为最高。
- 不在契约中选择 provider、模型、分辨率或轮询策略。

如果素材必选性、数量、顺序、首尾帧含义、转场强制性或规则冲突无法从来源确定，将状态设为 `needs_review` 并向用户提出最少的必要问题，不静默推断。

### 5. 创建标准包

优先运行：

```powershell
python scripts/scaffold_business_skill.py --skill-id <skill-id> --display-name "<中文名称>" --description "<触发描述>" --output <staging-root>
```

完善生成的所有文件，并删除其中的 `CURATOR-REQUIRED` 标记。`SKILL.md` 保持简洁；详细经验通过直接链接的一层 `references/` 文件渐进加载。

同时完善 `routing.json`。路由信息只用于在上百个正式 Skill 中快速定位用户想使用的业务能力；Skill 选定后，向用户索取什么素材仍完全由 `contract.json` 决定。

### 6. 创意补全检查

如果来源缺少提示词范例、正反例、边界案例，或 `references/creative-guidance.md` 只有结构化事实而缺少可执行创作方法，按 `references/dt-creative-supplement.md` 生成 Codex_DT 创意补充请求包：

```powershell
python scripts/prepare_dt_supplement.py <staging-skill-directory> --output <dt-request.json>
```

Codex_DT 只可补充提示词范例、正例、反例、边界案例和可选创意指导草稿。不得推断素材契约，不得选择 provider、模型、分辨率、轮询或付费执行，不得改变原始 Skill 的实际意义。DT 输出必须标记为草稿，并在用户确认入库报告后才能写入正式 references。

如果当前环境没有真实 Codex_DT 文本补充接口，入库流程继续推进，但报告中的 `creative_supplement.status` 必须保持 `creative_supplement_pending` 或 `failed`，并记录原因。

收到 Codex_DT 草稿后，先使用接收器验证并放入待审核区：

```powershell
python scripts/receive_dt_supplement.py <staging-skill-directory> <dt-draft.json>
```

接收器只把状态更新为 `draft_received`，不得修改正式 references。用户明确批准草稿后才运行：

```powershell
python scripts/approve_dt_supplement.py <staging-skill-directory> --approved-by user
```

批准脚本把已验证草稿整理进 references，并把补全状态设为 `user_approved`；它仍不发布 Skill。

### 7. 确定性验证

运行：

```powershell
python scripts/validate_skill_package.py <staging-skill-directory>
```

验证失败时只修复当前入库任务，不修改正式库中的其他 Skill。验证器负责结构、命名、契约、引用、污染、禁用模式和包一致性；它不评价艺术质量。

### 8. 展示入库报告

向用户展示：

- Skill 名称与 `skill_id`；
- 来源文件及哈希；
- 素材槽、类型、数量和必选性；
- 创意经验、社区经验、失败案例和示例的保留数量；
- 被隔离的旧规则；
- Codex_DT 创意补充状态、草稿来源和是否需要用户审核；
- 与现有 Skill 的重复或冲突；
- 所有仍需用户决定的歧义；
- 确定性验证结果。

同时按 `assets/intake-report.template.json` 生成机器可读的 `intake-report.json`。任何 `blocking_questions`、`contract_conflicts` 或 `validation_issues` 未清零时，状态必须保持 `needs_review`。

任何 DT 生成草稿未被用户确认时，状态不得超过 `ready_for_approval`，不得自动发布。

此时状态只能是 `needs_review` 或 `ready_for_approval`，不得自动发布。

### 9. 用户确认后发布

只有用户明确确认当前审核报告后，才运行发布脚本。发布命令必须同时提供原始来源文件：

```powershell
python scripts/publish_skill.py <staging-skill-directory> --library-root <business-skills> --source <original.md> --approved-by user
```

发布脚本重新验证、生成来源和包哈希、写入 `intake-receipt.json`，再原子发布。已存在的 `skill_id` 默认拒绝覆盖；更新现有 Skill 必须使用单独的版本升级流程。

正式库发布成功后，发布脚本增量更新本地 SQLite/FTS5 意图注册表。索引只收录凭证有效且包哈希未变化的 Skill。

更新已存在的正式 Skill 时，不得删除目录或绕过凭证直接覆盖。审核报告和创意补全均满足发布条件后运行：

```powershell
python scripts/upgrade_published_skill.py <staging-skill-directory> --library-root <business-skills> --source <original.md> --approved-by user
```

升级脚本验证旧凭证、来源哈希和新审核报告，使用可恢复的原子替换更新正式包；注册表更新失败时恢复旧版本。

正式运行时使用以下发现器读取 Skill 库：

```powershell
python scripts/discover_published_skills.py <business-skills>
```

发现器只返回发布凭证有效且包哈希未变化的目录；手工放入的 Markdown、未审核目录和发布后被篡改的包均不会成为可用 Skill。

## 不得执行

- 不生成图片或视频。
- 不提交任何付费任务。
- 不打开或理解参考媒体内容来猜测契约。
- 不把示例人物、城市、项目、品牌或镜头数量写成通用硬规则。
- 不因原文提到某个模型版本就改变实际生成模型。
- 不删除或改写原始来源文件。
- 不在用户确认前写入正式 `business-skills/`。
- 不把 Codex_DT 生成草稿当作已确认事实或契约来源。
