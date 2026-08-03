# Workspace Deployment Triggers

When the user is clearly asking to set up, install, deploy, update deployment, or bootstrap this repository, treat the request as a one-click deployment request and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\new-machine-deploy.ps1
```

Treat these as deployment triggers when they refer to this repository:

- `初始化`
- `部署`
- `更新部署`
- `安装`
- `一键部署`
- `初始化部署`
- `新电脑部署`

Before starting a deployment, if the required API keys are not already present in `Codex_image/.codex-image-private/.env`, ask the user to provide them as a copy-fill checklist and include clickable official links:

- `COMFLY_API_KEY` - [ai.comfly.org](https://ai.comfly.org/)
- `APIMART_API_KEY` - [apimart.ai/zh](https://apimart.ai/zh)
- `GEMINI_API_KEY` - [aistudio.google.com](https://aistudio.google.com/)

If the user asks for the older step-by-step flow instead, use `bootstrap-new-machine.ps1` and the existing manual deployment docs.

Keep this root instruction aligned with `README.md`, `DEPLOYMENT.md`, and `NEW_MACHINE_DEPLOYMENT_TEMPLATE.md`.
