# Codex_CS Skill Intent Registry

本目录提供可重建的本地 SQLite/FTS5 trigram 视频 Skill 意图注册表。注册表只负责根据用户“想创作什么”召回 Skill；已有素材不参与主路由。选定 Skill 后，查询结果中的 `material_guidance` 才用于指导用户补充素材。

```powershell
python .\scripts\build_registry.py --rebuild
python .\scripts\lookup_skill.py "制作科幻城市宣传片"
python .\scripts\list_skills.py
python .\scripts\validate_registry.py
```

默认数据库生成在 `packages/Codex_CS/.codex-cs-private/registry/video-skills.db`，不应提交 Git。构建器只收录具备有效发布凭证且包哈希一致的业务 Skill。再次构建时按包哈希增量更新；`--rebuild` 使用临时数据库并原子替换。

未来的 Skill 可在发布前加入 `routing.json`，字段格式见 `schemas/routing.schema.json`。没有该文件的既有 Skill 会从契约名称、描述和 `config/taxonomy.json` 编译基础路由信息。
