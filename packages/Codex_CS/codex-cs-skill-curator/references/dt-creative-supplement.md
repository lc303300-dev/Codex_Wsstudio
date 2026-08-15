# Codex_DT 创意补全边界

## 目标

当待入库视频 Skill 缺少提示词范例、正例、反例、边界案例，或缺少可执行创意写法时，可以请求 Codex_DT 生成草稿。该步骤只补全创意表达，不编译契约，不发布 Skill，不提交视频。

## 触发条件

满足任一条件时生成补全请求：

- `references/examples.md` 明确写明原始资料未提供示例；
- 正例、反例或边界案例为空；
- `references/creative-guidance.md` 只有事实分类，缺少可直接指导提示词写作的画面、镜头、动作、声音或连续性方法；
- 用户明确要求补充提示词范例或创意写法。

已有足够示例和创意指导时跳过此步骤，并在入库报告中记录 `status: not_required`。

## 请求约束

请求 Codex_DT 时必须带上约束：

- `preserve_meaning: true`
- `do_not_infer_contract: true`
- `do_not_select_provider: true`
- `do_not_select_model: true`
- `do_not_submit_video: true`
- `language: zh-CN`
- `preserve_professional_english: true`
- `requires_user_review: true`

Codex_DT 可输出：

- 正向提示词范例；
- 反例和原因；
- 边界案例；
- 可选创意指导草稿。

所有补充必须通过 `example-quality-benchmark.md`：完整正例需具备输入条件、素材绑定、全局视觉方向、时间推进、摄影机与主体动作、必要物理结果和结尾条件；反例需包含失败表现、违反规则与修正策略；边界案例需包含触发条件、仍适用规则、停止或降级项和处理方式。优秀 Skill 只提供结构与质量尺度，不得把其题材规则或素材契约迁移到目标 Skill。

Codex_DT 不可输出或改动：

- 必填素材类型、数量、顺序、首尾帧语义或绑定契约；
- provider、模型、分辨率、轮询、下载或付费执行策略；
- 与原始 Skill 实际意义不一致的新题材、新业务规则或新用途；
- 将社区经验升级为硬规则的表述。

## 状态机

`creative_supplement.status` 使用以下值：

- `not_required`：来源已有足够创意内容。
- `creative_supplement_pending`：已生成 DT 请求包，等待真实 DT 输出或人工补充。
- `draft_received`：已收到 DT 草稿，但尚未经过用户确认。
- `user_approved`：用户已确认可纳入正式 references。
- `failed`：DT 补充失败，入库仍可继续，但必须记录原因。

`draft_received` 不等于发布授权。用户确认入库报告前，不得将 DT 草稿作为正式 Skill 的已确认知识。

## 推荐请求包

```json
{
  "operation": "supplement_skill_creative_examples",
  "source_skill_id": "example-video-skill",
  "source_material": {
    "skill_summary": "...",
    "contract_summary": "...",
    "creative_guidance": "...",
    "community_experience": "...",
    "failure_cases": "...",
    "existing_examples": "..."
  },
  "constraints": {
    "preserve_meaning": true,
    "do_not_infer_contract": true,
    "do_not_select_provider": true,
    "do_not_select_model": true,
    "do_not_submit_video": true,
    "language": "zh-CN",
    "preserve_professional_english": true,
    "requires_user_review": true
  },
  "requested_outputs": [
    "positive_examples",
    "negative_examples",
    "boundary_examples",
    "optional_creative_guidance"
  ]
}
```

## 写回规则

只有在用户批准后，才可以把 DT 草稿整理进 `references/examples.md` 或 `references/creative-guidance.md`。写回时必须保留标记：

```markdown
> 来源：Codex_DT 创意补充草稿；状态：user_approved；用途：示例辅助，不定义契约。
```

如 DT 输出与契约冲突，保留冲突记录，不写入正式 references。
