---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '615f7510-5a47-4445-bd09-a922975a06d0'
  PropagateID: '615f7510-5a47-4445-bd09-a922975a06d0'
  ReservedCode1: '3776415d-a852-478a-a004-e24fcb1e6c27'
  ReservedCode2: '3776415d-a852-478a-a004-e24fcb1e6c27'
---

# AI辅助接口文档自动生成系统

> 实训作业项目
> 作者：易方涛
> 日期：2026-08-24（v2.3 更新：2026-09-05，存储层升级 MySQL 8.0）

## 项目简介

解析 Java/SpringBoot 项目代码，用 AI 大模型自动生成接口文档（OpenAPI 3.0 + Markdown），包含接口描述、参数说明、示例数据、边界场景提示。

## 技术栈

- **后端**: Python 3.12 + FastAPI + javalang + httpx + PyJWT + PyMySQL
- **前端**: Vue3 + Element Plus + Axios + Vue Router（4 个独立页面，路由懒加载 + 登录/角色双重守卫）
- **AI**: 云端大模型 API（DeepSeek / 豆包），无 Key 时自动降级纯解析
- **存储**: MySQL 8.0（项目/接口/用户数据持久化，pymysql 驱动，utf8mb4）

## 页面结构（v2.2 新增）

| 页面 | 路由 | 说明 |
|------|------|------|
| 登录/注册页 | /login | 登录与自助注册，未登录访问其他页面自动跳回 |
| 解析工作台 | /workspace | 上传 ZIP/路径/内置示例解析，接口树导航 + 接口详情（含 AI 增强、在线编辑） |
| 项目历史 | /projects | 已解析项目列表，支持按项目名/归属人搜索、删除、跳转导出 |
| 导出中心 | /export/:projectId | 项目文档预览（Markdown/OpenAPI 双 Tab）+ 双格式下载 |
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
│   ├── config.py            # 配置
│   ├── requirements.txt     # 依赖
│   ├── models/              # 数据模型
│   ├── parser/              # Java 代码解析
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
    └── spring-petclinic/     # SpringBoot 示例项目
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

编辑 `backend/config.py`，填入你的 API Key：

```python
LLM_API_KEY = "你的API Key"
```

或设置环境变量：

```bash
set LLM_API_KEY=你的API Key
```

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
| POST | /api/parse | 上传 ZIP 或指定路径解析项目 |
| POST | /api/parse-sample | 快捷解析内置示例项目 |
| GET | /api/project | 项目列表（普通用户仅自己的） |
| GET | /api/project/{id} | 获取项目接口列表 |
| GET | /api/endpoint/{id} | 获取单个接口详情 |
| POST | /api/endpoint/{id}/enhance | 重新 AI 增强 |
| PUT | /api/endpoint/{id} | 编辑接口信息 |
| DELETE | /api/project/{id} | 删除项目 |
| GET | /api/project/{id}/export | 导出文档(openapi/markdown)，文件名由后端下发 |

除 login/register 外，所有接口需携带请求头 `Authorization: Bearer <token>`。

## 测试

```bash
cd backend
python -m pytest tests/ -q
```

共 78 条测试（解析/生成器/AI增强/存储/鉴权），全部通过。

> AI生成