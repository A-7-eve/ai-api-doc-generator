---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '344e595f-1c07-489c-a2f9-dc7d75795aa2'
  PropagateID: '344e595f-1c07-489c-a2f9-dc7d75795aa2'
  ReservedCode1: 'd4807f3a-d08f-4e58-bc22-437ebb1c0ade'
  ReservedCode2: 'd4807f3a-d08f-4e58-bc22-437ebb1c0ade'
---

# AI辅助接口文档自动生成系统

> 实训作业项目
> 作者：易方涛
> 日期：2026-08-24（v2.4 更新：2026-09-10，多语言解析 + 版本管理 + 文档在线编辑 + DeepSeek 接入）

## 项目简介

解析 Java/SpringBoot、Python（FastAPI/Flask）、C 多语言项目代码，用 AI 大模型自动生成接口文档（OpenAPI 3.0 + Markdown），支持在线编辑后导出，包含接口描述、参数说明、示例数据、边界场景提示。

## 技术栈

- **后端**: Python 3.12 + FastAPI + javalang + httpx + PyJWT + PyMySQL
- **前端**: Vue3 + Element Plus + Axios + Vue Router（5 个独立页面，路由懒加载 + 登录/角色双重守卫）
- **AI**: DeepSeek（deepseek-chat，已接入），无 Key 时自动降级纯解析
- **存储**: MySQL 8.0（项目/接口/文档/用户数据持久化，pymysql 驱动，utf8mb4）

## v2.4 新增功能

1. **多语言解析**：新增 Python（FastAPI/Flask 装饰器路由，ast 引擎）与 C（函数清单，正则引擎）解析引擎，上传混合语言项目自动识别并合并解析
2. **版本管理**：引擎注册表（engine_registry）集中管理各语言引擎与语法版本范围，AST 解析失败自动降级正则模式并记入 engineInfo
3. **文档在线编辑**：导出中心预览区可直接编辑 Markdown/OpenAPI 文档，保存后导出与在线一致，支持一键重置回生成版
4. **DeepSeek 接入**：Key 从 backend/.env 读取（不入仓库），AI 增强真实生效（描述/参数说明/示例/边界场景/错误码）

## 页面结构（v2.2 新增）

| 页面 | 路由 | 说明 |
|------|------|------|
| 登录/注册页 | /login | 登录与自助注册，未登录访问其他页面自动跳回 |
| 解析工作台 | /workspace | 上传 ZIP/路径/内置示例解析，接口树导航 + 接口详情（含 AI 增强、在线编辑），多语言项目显示语言标签 |
| 项目历史 | /projects | 已解析项目列表，支持按项目名/归属人搜索、删除、跳转导出 |
| 导出中心 | /export/:projectId | 文档在线编辑（v2.4）+ Markdown/OpenAPI 双 Tab 预览 + 保存/重置 + 双格式下载 |
| 用户管理（管理员） | /users | 用户列表、角色调整、删除用户，普通用户访问被路由守卫拦截 |

## 用户与角色（v2.1 新增）

系统包含登录鉴权与角色权限：

| 角色 | 权限 |
|------|------|
| 普通用户 | 解析项目、查看接口、导出文档、编辑接口描述（仅限自己的项目） |
| 管理员 | 以上全部 + 查看所有人项目 + 删除项目 + 用户管理（角色调整/删除） |

- 默认管理员账号：`admin / admin123`（首次启动自动创建）
- 新用户可在登录页自助注册（默认普通用户）
- 登录态使用 JWT（有效期 24 小时），过期自动跳回登录页
- 兼容历史数据：v2.1 之前解析的项目无归属人，所有登录用户可见

## 目录结构

```
AI辅助接口文档自动生成/
├── docs/                    # 项目文档
├── backend/                  # Python FastAPI 后端
│   ├── main.py              # 入口
│   ├── config.py            # 配置（Key 从 .env 读取）
│   ├── .env                 # API Key 私有文件（不入仓库）
│   ├── requirements.txt     # 依赖
│   ├── models/              # 数据模型
│   ├── parser/              # 多语言解析引擎
│   │   ├── java_parser.py       # Java/SpringBoot（javalang AST）
│   │   ├── python_parser.py     # Python/FastAPI/Flask（内置 ast）
│   │   ├── c_parser.py          # C 函数清单（正则）
│   │   ├── engine_registry.py   # 引擎注册表（版本管理）
│   │   └── dispatcher.py        # 多语言分发器
│   ├── ai/                  # AI 增强层
│   ├── generator/           # 文档生成
│   └── routers/             # API 路由
├── frontend/                # Vue3 前端
│   └── src/
│       ├── views/           # 5 个页面视图（登录/工作台/项目历史/导出中心/用户管理）
│       ├── components/      # 通用组件（接口树/接口详情）
│       ├── router/          # 路由与守卫
│       └── api/             # Axios 封装
└── sample-project/          # 被解析的示例项目
    ├── spring-petclinic/     # SpringBoot 示例（17 接口）
    ├── flask-demo/           # Python 示例（FastAPI+Flask，11 接口）
    └── c-demo/               # C 示例（6 函数）
```

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置 MySQL（v2.3 起默认 MySQL 8.0）

后端启动时会自动建库建表（默认连接 `127.0.0.1:3306`，用户 `root`），只需保证本机 MySQL 8.0 已启动。如需自定义连接，设置环境变量：

```bash
set APIDOC_DB_HOST=127.0.0.1
set APIDOC_DB_PORT=3306
set APIDOC_DB_USER=root
set APIDOC_DB_PASSWORD=你的密码
set APIDOC_DB_NAME=apidoc
```

### 3. 配置大模型 API Key

创建 `backend/.env` 文件（已被 .gitignore 排除，不会提交到仓库）：

```
LLM_API_KEY=sk-你的DeepSeekKey
```

或设置环境变量：

```bash
set LLM_API_KEY=你的API Key
```

未配置 Key 时系统自动降级为纯解析模式，功能不受影响（仅无 AI 增强）。

### 4. 启动后端

```bash
cd backend
python main.py
```

服务启动在 http://localhost:8000，API 文档在 http://localhost:8000/docs

### 5. 测试解析

```bash
# 解析内置的 spring-petclinic 示例项目
curl -X POST http://localhost:8000/api/parse-sample
```

## API 接口

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | /api/auth/login | 登录（返回 JWT） |
| POST | /api/auth/register | 注册新用户 |
| GET | /api/auth/me | 当前用户信息 |
| GET | /api/auth/users | 用户列表（管理员） |
| PUT | /api/auth/users/{id}/role | 修改用户角色（管理员） |
| DELETE | /api/auth/users/{id} | 删除用户（管理员） |
| POST | /api/parse | 上传 ZIP 或指定路径解析项目（Java/Python/C 自动识别） |
| POST | /api/parse-sample | 快捷解析内置示例项目 |
| GET | /api/project | 项目列表（普通用户仅自己的） |
| GET | /api/project/{id} | 获取项目接口列表（含 languages/engineInfo） |
| GET | /api/endpoint/{id} | 获取单个接口详情 |
| POST | /api/endpoint/{id}/enhance | 重新 AI 增强 |
| PUT | /api/endpoint/{id} | 编辑接口信息 |
| DELETE | /api/project/{id} | 删除项目 |
| GET | /api/project/{id}/doc | 获取文档内容（优先编辑版） |
| PUT | /api/project/{id}/doc | 保存文档编辑版 |
| POST | /api/project/{id}/doc/reset | 重置文档为生成版 |
| GET | /api/project/{id}/export | 导出文档(openapi/markdown)，与在线编辑一致 |

除 login/register 外，所有接口需携带请求头 `Authorization: Bearer <token>`。

## 测试

```bash
cd backend
python -m pytest tests/ -q
```

共 119 条测试（Java/Python/C 解析/分发器/生成器/AI增强/存储/鉴权），全部通过。

> AI生成