---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '197ed230-b435-40aa-9e51-27a8864455ac'
  PropagateID: '197ed230-b435-40aa-9e51-27a8864455ac'
  ReservedCode1: '0ae571fc-c9d9-4959-97bf-735f8226d494'
  ReservedCode2: '0ae571fc-c9d9-4959-97bf-735f8226d494'
---

# Docker 一键部署（v2.5）

本系统支持 **Docker Compose 一键部署**：一行命令启动 MySQL + 后端 + 前端三件套，适用于演示、交付、迁移到其他电脑等场景。**不需要在本机安装 Python/Node/MySQL。**

## 1. 环境要求

| 组件 | 版本要求 | 说明 |
|---|---|---|
| Docker | 20.10+ | Windows 用 Docker Desktop，或 WSL2 内安装 docker-ce |
| Docker Compose | v2 以上 | `docker compose version` 可查 |

> 本机（Windows + WSL2 Ubuntu-24.04）已装 Docker 29.5.3 / Compose v5.1.4，直接可用。

## 二、快速开始

```bash
# 1. 在项目根目录准备环境变量（可选，默认 deepseek + 密码 123456）
cp .env.example .env
#    编辑 .env：填 LLM_API_KEY（DeepSeek）或 TELEAI_API_KEY（星辰）

# 2. 构建并启动（首次构建约 3-5 分钟，取决于网络）
docker compose up -d --build

# 3. 访问系统
#    前端：  http://localhost:8080
#    后端：  http://localhost:8000  （未直接暴露，需取消 compose 端口注释）
#    API文档：http://localhost:8000/docs

# 4. 默认账号（数据库首次启动自动创建）
#    管理员：admin / admin123
#    普通用户：tester01 / test123456
```

## 三、架构

```
宿主机                         Docker 内部网络（bridge）
┌──────────┐  :8080  ┌───────────────────────────────────┐
│ 浏览器    │ ──────▶ │ web (nginx) 静态前端               │
└──────────┘         │   │                                │
                     │   │ /api 反代                      │
                     │   ▼                                │
                     │ backend (uvicorn :8000)            │
                     │   │ 连接 mysql:3306                │
                     │   ▼                                │
                     │ db (MySQL 8.0)  ◀── 宿主 :3307     │
                     └───────────────────────────────────┘
```

要点：
- **前端**：vite 构建产物 → nginx 托管，`/api` 反向代理到 backend（同源，无跨域）
- **后端**：FastAPI + uvicorn，容器内读环境变量连接 db 容器
- **数据库**：MySQL 8.0，宿主映射 **3307**（避开本机 3306 冲突），数据存在 Docker 卷 `apidoc-mysql`，`down` 不丢数据

## 四、配置说明

### 4.1 环境变量（根目录 .env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `APIDOC_DB_PASSWORD` | `123456` | MySQL root 密码 |
| `APIDOC_DB_NAME` | `apidoc` | 数据库名 |
| `LLM_PROVIDER` | `deepseek` | 大模型供应商：`deepseek` / `teleai` |
| `LLM_API_KEY` | 空 | DeepSeek Key（provider=deepseek） |
| `TELEAI_API_KEY` | 空 | 星辰大模型 Key（provider=teleai） |

> Key 为空时 AI 增强自动降级为纯解析（本地生成描述），不影响系统使用。

### 4.2 端口

| 服务 | 宿主端口 | 说明 |
|---|---|---|
| web | 8080 | 前端入口 |
| db | 3307 | 仅调试用（可选） |
| backend | 不暴露 | 仅容器内网 |

> 改端口：编辑 `docker-compose.yml` 中 `ports` 映射即可。

## 五、常用运维命令

```bash
docker compose ps                  # 查看三容器状态
docker compose logs -f backend     # 实时看后端日志
docker compose restart backend     # 重启后端（改代码后需 rebuild）
docker compose up -d --build       # 代码变更后重新构建

docker compose down                # 停止（数据保留）
docker compose down -v             # 停止并删除数据库数据（不可恢复！）
docker exec -it apidoc-db mysql -uroot -p123456 apidoc   # 进 MySQL 命令行
```

## 六、常见问题

**Q: 8080 端口被占用？**
改 `docker-compose.yml` 里 `web.ports` 为 `"8081:80"`，访问 `http://localhost:8081`。

**Q: 后端连不上数据库？**
看启动顺序：backend 依赖 db 的健康检查（`service_healthy`），db 未就绪前 backend 不会启动。若 MySQL 首次初始化较慢，多等 1-2 分钟。

**Q: 上传大 ZIP 失败？**
nginx 已设 `client_max_body_size 100m`，更大需改 `docker/nginx.conf` 后 `docker compose up -d --build web`。

**Q: 改动了 backend 代码？**
```bash
docker compose up -d --build backend
```

**Q: 本地（非 Docker）模式还能用吗？**
完全兼容。Docker 化是纯增量，原有 `python main.py` + `npm run dev` 流程不受影响。

> AI生成