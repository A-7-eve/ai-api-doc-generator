"""JWT 鉴权与权限控制（角色功能）

- create_token / get_current_user：JWT 签发与解析
- require_admin：管理员专用依赖
- 项目归属校验：普通用户只能操作自己的项目
"""

import os
import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from store import users

logger = logging.getLogger(__name__)

# 密钥：优先读环境变量，否则使用默认值（教学项目，可接受）
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "aiapidoc-secret-key-2026-fdu8s2k1m9v4")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

_bearer = HTTPBearer(auto_error=False)


def create_token(user_id: str, username: str, role: str) -> str:
    """签发 JWT"""
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> "UserMeta":
    """FastAPI 依赖：从 Authorization: Bearer <token> 解析当前用户

    未登录或 token 无效时抛 401。
    """
    from models.schemas import UserMeta

    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的登录凭证")

    user_id = payload.get("sub")
    user = users.get(user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在或已被删除")
    return user


def require_admin(user=Depends(get_current_user)):
    """FastAPI 依赖：仅管理员可访问"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def check_project_owner(project, user):
    """校验项目归属：管理员放行，普通用户仅限自己的项目"""
    if user.role == "admin":
        return
    if project.ownerUserId and project.ownerUserId != user.userId:
        raise HTTPException(status_code=403, detail="无权访问他人的项目")
