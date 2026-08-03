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

- `COMFLY_API_KEY`
- `APIMART_API_KEY`
- `GEMINI_API_KEY`

脚本会把它们写入本机的 `Codex_image/.codex-image-private/.env`，不会提交到 Git。

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

每次开始前先运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-task.ps1
```

## 说明

- `.env.example` 是模板。
- `.codex-image-private/` 是本机私有目录。
- 不要把真实 Key、登录态、缓存、日志、输出文件提交到 Git。
