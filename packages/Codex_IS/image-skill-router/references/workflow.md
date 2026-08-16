# Router 状态与确认失效

```text
awaiting_skill_confirmation
→ awaiting_ratio_and_count
→ awaiting_materials
→ materials_ready
→ awaiting_prompt_confirmation
→ ready_for_generation
  或 awaiting_paid_batch_confirmation → ready_for_batch_generation
→ generating
→ completed | partially_completed | failed
```

- 修改或替换任一最终素材：归档现有提示词，清空提示词确认和批量付费确认。
- 修改提示词：旧版本标记为 `superseded`，清空提示词确认和批量付费确认。
- 正式 Skill 包哈希或发布收据变化：阻止后续动作，要求重建注册表并重新建立可信项目状态。
- 最终提交必须同时匹配确认的提示词哈希和素材集合哈希。

