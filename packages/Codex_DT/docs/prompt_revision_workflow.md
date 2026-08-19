# Codex Flow 首稿后的 DT 提示词修订

当 Codex Flow Skill 已经生成第一版完整视频提示词时，DT 不重新取得创作主权。只有用户要求修改时，DT 才接收当前提示词、用户反馈和锁定上下文，生成下一版候选提示词。

正常交互保持简短：用户确认首稿后直接生成视频；用户提出修改后自动进入 DT 修订，再把新版提示词交给用户确认。不要求用户选择是否调用 DT，也不生成独立审核报告。

## 修订请求

先运行确定性规划器：

```powershell
python scripts/classify_revision.py --input revision-input.json --out revision-request.json
```

输入必须包含：

- `current_prompt`：Codex Flow Skill 输出的当前提示词。
- `user_feedback`：用户本轮修改意见。
- `locked_context.contract_rules`：Codex Flow 工作流上下文和强制创作规则。
- `locked_context.material_order`：最终素材的权威顺序及角色。
- `locked_context.ratio`：已确认画幅。
- `locked_context.duration_seconds`：已确认时长。

规划器只分类并输出修订约束，不调用语料库、不改写提示词，也不生成媒体。

## 三级策略

| 分类 | 典型反馈 | 语料库策略 |
|---|---|---|
| `explicit_local` | “第二镜不要环绕，改成低机位推进”或“改为 8 秒” | 不检索，`should_search_corpus=false` |
| `ambiguous_creative` | “不够震撼”“更有电影感” | 可检索，最多 3 条 |
| `structural_rewrite` | “重构整段叙事”“重新编排全部镜头” | 可检索，最多 3 条 |

语料检索只是为开放式创意或结构重构提供可迁移方法。不得复制案例提示词，不得从案例的模型版本选择实际生成模型。

## 修订不变量

DT 修订必须遵守以下规则：

1. 用户没有要求修改的内容保持不变。
2. `contract_rules` 不可修改、弱化或重新解释。
3. `material_order` 是素材绑定的唯一权威顺序，禁止重排。
4. 比例和时长保持不变；只有用户明确修改项目设置时，才把新值交给上游项目状态更新，不能暗中写入提示词。
5. 修订结果必须回显与请求相同的 `locked_context_sha256`，使调用方可以拒绝基于旧契约生成的结果。
6. 每次修订后提示词恢复为待用户确认状态；DT 不提交视频。

修订结果应符合 `schemas/prompt-revision-result.schema.json`。`corpus_usage.matches` 最多 3 条；`explicit_local` 必须为空。
