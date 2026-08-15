# Codex_CS Skill 视频项目运行时

本目录提供 provider-neutral 的项目状态桥接，不调用生图或视频付费接口。运行数据默认写入
`packages/Codex_CS/.codex-cs-private/projects/`。

## 最短流程

```powershell
python .\project-pipeline\scripts\project_pipeline.py create --skill-id giant-3d-logo-landmark-video --display-name "巨型3D Logo 地标巡游视频" --ratio 9:16 --duration 15 --skill-confirmed
python .\project-pipeline\scripts\project_pipeline.py choose-image-stage <project-id> --mode user_supplied
python .\project-pipeline\scripts\project_pipeline.py lock-final <project-id> --use-source
python .\project-pipeline\scripts\project_pipeline.py set-cs-prompt <project-id> --file <prompt.txt>
python .\project-pipeline\scripts\project_pipeline.py confirm-prompt <project-id>
python .\project-pipeline\scripts\project_pipeline.py start-generation <project-id>
```

时长范围为 4–30 秒。`start-generation` 输出可直接交给统一 `generate_video` 的 `generation.submission_payload`。`generate` 模式还会输出 `image_generation_tasks`，供统一 `generate_image` 写入各槽位的 `final/` 目录。

创建项目时读取每个契约槽的 `count_rule`，根据用户时长写入 `planned_count`。`required` 规则在锁定素材时要求数量完全一致；`recommended` 规则显示建议数量，但仍以槽位 `min_count` / `max_count` 作为硬边界。

`create` 输出每个素材槽的绝对 `source_dir` 和 `final_dir`。用户提供的原始图片放入
`source_dir`；选择不生图时使用 `lock-final --use-source` 将其提升为最终素材。选择自动生图时，
外部统一图片路由把结果写入对应 `final_dir`，再运行 `lock-final`。

首次提示词只能由 `set-cs-prompt` 记录。用户要求修改时依次运行：

```powershell
python .\project-pipeline\scripts\project_pipeline.py request-revision <project-id> --feedback "用户修改意见"
python .\project-pipeline\scripts\project_pipeline.py set-dt-revision <project-id> --file <revised-prompt.txt>
```

`confirm-prompt` 保存提示词和素材哈希；`start-generation` 再次核验哈希，防止提交用户未确认的版本。
