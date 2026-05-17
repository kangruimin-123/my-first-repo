# 主线龙头交易系统 3.0

个人 A 股主线龙头交易辅助系统，包含后端策略引擎、FastAPI 接口、React 前端、交易日三段式调度和 Docker 发布配置。

## 功能范围

- 股票池、自选池、持仓池
- 主线识别、角色识别、核心策略信号
- 连板潜力、机会雷达、风险雷达
- 今日操作台、持仓建议、盘中监控
- 单服务发布：FastAPI 同时提供 `/api/*` 和前端页面

## 本地运行

```bash
python3 run.py --mode daily
cd 主线龙头交易系统 && npm run dev
python3 -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

生产模式只需要一个服务：

```bash
cd 主线龙头交易系统 && npm run build && cd ..
python3 -m uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

打开：

```text
http://127.0.0.1:8000/
```

## 发布

项目已准备 Docker 和 Render 配置：

- `Dockerfile`
- `render.yaml`
- `DEPLOY.md`

GitHub 用作代码仓库；Render/Railway/VPS 负责真正运行服务。

## 原仓库说明

本仓库原先也沉淀了 BDC AI Runtime 相关工程文档，包括 `app/`、`config/`、`docs/`、`tasks/`、`scripts/` 等目录。它们作为历史资料保留，不影响股票交易系统运行。
