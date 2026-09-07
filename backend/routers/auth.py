"""认证与用户管理路由（角色功能）

- POST /api/auth/login    登录
- POST /api/auth/register 注册（默认普通用户）
- GET  /api/auth/me       当前用户信息
- GET  /api/auth/users    用户列表（管理员）
- PUT  /api/auth/users/{user_id}/role  修改角色（管理员）
- DELETE /api/auth/users/{user_id}     删除用户（管理员）
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from models.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    RoleUpdateRequest,
)
from store import users, verify_password
from security import create_token, get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """登录：校验用户名密码，签发 JWT"""
    result = users.get_by_username(body.username)
    if result is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user, password_hash = result
    if not verify_password(body.password, password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(user.userId, user.username, user.role)
    logger.info(f"用户登录: {user.username} ({user.role})")
    return TokenResponse(token=token, user=user)


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest):
    """注册新账号（默认普通用户角色）"""
    if not body.username or not body.password:
        raise HTTPException(status_code=422, detail="用户名和密码不能为空")
    if len(body.username) < 2 or len(body.password) < 6:
        raise HTTPException(
            status_code=422,
            detail="用户名至少 2 位，密码至少 6 位",
        )

    try:
        user = users.create(body.username, body.password, role="user")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    token = create_token(user.userId, user.username, user.role)
    logger.info(f"新用户注册: {user.username}")
    return TokenResponse(token=token, user=user)


@router.get("/me")
async def me(user=Depends(get_current_user)):
    """获取当前登录用户信息"""
    return user.model_dump()


@router.get("/users")
async def list_users(admin=Depends(require_admin)):
    """获取所有用户列表（仅管理员）"""
    return [u.model_dump() for u in users.list_all()]


@router.put("/users/{user_id}/role")
async def update_role(user_id: str, body: RoleUpdateRequest, admin=Depends(require_admin)):
    """修改用户角色（仅管理员）"""
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=422, detail="role 仅支持 admin 或 user")
    if not users.set_role(user_id, body.role):
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin=Depends(require_admin)):
    """删除用户（仅管理员）；不能删除自己"""
    if user_id == admin.userId:
        raise HTTPException(status_code=400, detail="不能删除当前登录的管理员自己")
    if not users.delete(user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True}
