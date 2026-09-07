"""FastAPI 入口"""

import sys
import os
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from routers import api, auth  # noqa: E402
import config  # noqa: E402
from config import HOST, PORT  # noqa: E402
from store import projects, users  # noqa: E402

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI辅助接口文档自动生成系统",
    description="解析 Java/SpringBoot 项目代码，用 AI 生成接口文档（含用户角色权限）",
    version="2.1.0",
)

# CORS（允许前端跨域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（路由本身已有 /api 前缀）
app.include_router(auth.router)
app.include_router(api.router)


@app.get("/")
async def root():
    """根路径：系统说明"""
    return {
        "system": "AI辅助接口文档自动生成系统",
        "version": "2.1.0",
        "docs": "/docs",
        "endpoints": {
            "登录": "POST /api/auth/login",
            "注册": "POST /api/auth/register",
            "当前用户": "GET /api/auth/me",
            "用户列表(管理员)": "GET /api/auth/users",
            "解析项目(上传ZIP)": "POST /api/parse",
            "解析项目(本地路径)": "POST /api/parse",
            "解析内置示例": "POST /api/parse-sample",
            "获取项目列表": "GET /api/project",
            "获取项目详情": "GET /api/project/{projectId}",
            "获取接口详情": "GET /api/endpoint/{endpointId}",
            "重新AI增强": "POST /api/endpoint/{endpointId}/enhance",
            "编辑接口": "PUT /api/endpoint/{endpointId}",
            "删除项目": "DELETE /api/project/{projectId}",
            "导出文档": "GET /api/project/{projectId}/export?format=openapi|markdown",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    existing = len(projects.list_all())
    user_count = len(users.list_all())
    logger.info(f"启动服务: http://{HOST}:{PORT}")
    logger.info(f"API 文档: http://{HOST}:{PORT}/docs")
    logger.info(f"MySQL 存储({config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}): "
                f"已有 {existing} 个历史项目, {user_count} 个用户")
    logger.info("默认管理员账号: admin / admin123")
    uvicorn.run(app, host=HOST, port=PORT)
