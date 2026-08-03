# 新电脑一键部署模板

适合第一次在新电脑上部署 `Codex_Wsstudio`。

## 你需要准备

- Git
- Python 3.11+
- PowerShell 7 或 Windows PowerShell
- 可选: Node.js LTS
- GitHub 仓库访问权限
- 你要使用的 API Key

## 你可能要填写的 Key

- `COMFLY_API_KEY` - [ai.comfly.org](https://ai.comfly.org/)
- `APIMART_API_KEY` - [apimart.ai/zh](https://apimart.ai/zh)
- `GEMINI_API_KEY` - [aistudio.google.com](https://aistudio.google.com/)

Dreamina/Jimeng 也建议提前登录：

- [jimeng.jianying.com](https://jimeng.jianying.com/)

脚本会把它们写入本机的 `Codex_image/.codex-image-private/.env`，不会提交到 Git。

复制填写模板：

```text
COMFLY_API_KEY=
APIMART_API_KEY=
GEMINI_API_KEY=
```

除了 API Key 和 Jimeng 预登录，其它配置都由脚本自动处理。不要手工复制旧电脑里的 `AGENTS.md`、`config.toml` 或机器本地路径。

## 一键部署

在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\new-machine-deploy.ps1
```

脚本会自动：

1. 检查基础环境
2. 只询问缺失的 Key
3. 保存本机 Key
4. 同步 Codex 配置
5. 安装媒体工具和 Dreamina/Seedance 依赖
6. 输出部署结果

## 如果你想手动执行

先跑基础部署：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-new-machine.ps1
```

再补 Key：

```powershell
.\Codex_image\configure-api-key.ps1 -Pipeline comfly-api
.\Codex_image\configure-api-key.ps1 -Pipeline gpt-api
.\Codex_image\configure-api-key.ps1 -Pipeline gemini-api
```

最后再跑一次基础部署。

## 部署后怎么启动

准备在这个仓库中写入文件前运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-task.ps1
```

这项检查只适用于当前路径或明确指定的目标路径位于本 Git 仓库内的情况。
纯聊天、公开网络或 GitHub 搜索、只读任务、Codex 自动生成的 projectless
临时目录，以及其他仓库，都不要运行或搜索此脚本。如果用户明确要求修改
本仓库但根目录脚本缺失，应先报告异常并停止写入。

## 说明

- `.env.example` 是模板。
- `.codex-image-private/` 是本机私有目录。
- 不要把真实 Key、登录态、缓存、日志、输出文件提交到 Git。
