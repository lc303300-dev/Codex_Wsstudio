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

脚本会把它们写入本机的 `packages/Codex_image/.codex-image-private/.env`，不会提交到 Git。

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
6. 注册 Codex_CS、批量图片和 Codex_IS 等全局业务 Skills
7. 输出部署结果

同步 Codex 配置时，脚本会把仓库维护的 `config/codex/AGENTS.md` 安装为当前用户的全局
Codex 指令，其中包括 Windows 本地资源硬约束：Markdown 本地链接和图片必须使用绝对
正斜杠路径，禁止原始反斜杠路径和 `file://` URI；工具已返回资源或专用链接目标时必须
直接复用，不能从原始输出路径重新拼接。

同一全局指令还会强制所有图片生成和图片编辑先由用户明确选择比例。支持
`21:9`、`16:9`、`3:2`、`4:3`、`1:1`、`3:4`、`2:3`、`9:16`；未提供比例时，
管线会在调用任何付费 provider 前拒绝任务，不从参考图或 provider 默认值推断。

图片线路仍默认按配置顺序自动回退，不会主动要求普通用户选择。如果用户在当前请求中
明确点名一个受支持且无歧义的线路，统一 `generate_image` 工具会直接使用该线路并跳过
默认顺序；该线路失败时也不会擅自切换到其他线路。

## 如果你想手动执行

先跑基础部署：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deployment\bootstrap-new-machine.ps1
```

再补 Key：

```powershell
.\packages\Codex_image\configure-api-key.ps1 -Pipeline comfly-api
.\packages\Codex_image\configure-api-key.ps1 -Pipeline gpt-api
.\packages\Codex_image\configure-api-key.ps1 -Pipeline gemini-api
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
