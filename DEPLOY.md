# 发布说明

这个项目现在可以作为一个服务发布：FastAPI 同时提供 `/api/*` 和前端页面。

## 本地生产模式验证

```bash
cd /Users/company/股票交易系统3.0
cd 主线龙头交易系统 && npm run build && cd ..
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

打开：

```text
http://127.0.0.1:8000/
```

## Docker 发布

```bash
docker build -t stock-trading-system-3 .
docker run -p 8000:8000 -e TS_TOKEN=你的TushareToken stock-trading-system-3
```

## Render 发布

1. 把仓库推到 GitHub。
2. 在 Render 新建 Blueprint 或 Web Service。
3. 选择 Docker 环境。
4. 设置环境变量 `TS_TOKEN`。
5. 设置 `APP_USERNAME` 和 `APP_PASSWORD`，用于给网页加一层浏览器登录保护。
6. 部署后访问 Render 给出的域名。

## 注意

- 镜像不会包含本地 `trading_system.db`，避免把持仓、成本价等私有数据推到 GitHub 或云端镜像。
- 首次发布后云端会创建空 SQLite 库；需要重新导入持仓或接入持久化数据库。
- 如果要每天自动更新并长期保留结果，需要给线上服务加持久化磁盘，或者把 SQLite 换成云数据库。
- 线上更新数据可以通过进入服务执行：

```bash
python3 run.py --mode trade_day --phase review
```

后续如果要真正长期运行，推荐把数据库迁移到 Postgres，并把交易日调度器作为后台任务运行。
