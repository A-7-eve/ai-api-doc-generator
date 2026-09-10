"""Pydantic 数据模型定义"""

from pydantic import BaseModel
from typing import Optional
from enum import Enum


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class ParamMeta(BaseModel):
    """参数元数据"""
    name: str
    type: str
    annotation: Optional[str] = None       # @RequestParam / @PathVariable / @RequestBody
    required: bool = True
    # AI 增强字段
    description: Optional[str] = None
    example: Optional[str] = None


class EndpointMeta(BaseModel):
    """接口元数据"""
    endpointId: Optional[str] = None
    method: HTTPMethod
    path: str
    fullPath: str
    javaMethod: str
    returnType: Optional[str] = None
    comment: Optional[str] = None
    sourceCode: Optional[str] = None
    params: list[ParamMeta] = []
    # AI 增强字段
    description: Optional[str] = None
    requestExample: Optional[str] = None
    responseExample: Optional[str] = None
    edgeCases: list[str] = []
    errorCodes: list[dict] = []


class ControllerMeta(BaseModel):
    """Controller 元数据"""
    controllerId: Optional[str] = None
    className: str
    baseUrl: str
    packageName: Optional[str] = None
    comment: Optional[str] = None
    endpoints: list[EndpointMeta] = []


class DtoFieldMeta(BaseModel):
    """DTO 字段元数据"""
    name: str
    type: str
    annotations: list[str] = []     # @NotNull / @Size 等


class DtoMeta(BaseModel):
    """DTO 类元数据"""
    className: str
    fields: list[DtoFieldMeta] = []


class ProjectMeta(BaseModel):
    """项目元数据"""
    projectId: Optional[str] = None
    projectName: str
    controllers: list[ControllerMeta] = []
    dtos: list[DtoMeta] = []
    parseTime: Optional[str] = None
    # 多语言支持（v2.4）：项目包含的语言列表，如 ["java", "python", "c"]
    languages: list[str] = []
    # 解析引擎信息（v2.4）：{"java": {"engine": "javalang-ast", "version": "1.0", "degraded": false}, ...}
    engineInfo: dict = {}
    # 归属信息（角色功能）
    ownerUserId: Optional[str] = None
    ownerName: Optional[str] = None


class AIEnhancement(BaseModel):
    """AI 增强结果"""
    description: str
    params: list[dict] = []
    requestExample: str = ""
    responseExample: str = ""
    edgeCases: list[str] = []
    errorCodes: list[dict] = []


# ========== 用户与鉴权模型 ==========

class UserMeta(BaseModel):
    """用户元数据（不含密码）"""
    userId: str
    username: str
    role: str = "user"          # "admin" | "user"
    createdAt: Optional[str] = None


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """登录/注册成功响应"""
    token: str
    tokenType: str = "Bearer"
    user: UserMeta


class RoleUpdateRequest(BaseModel):
    """修改角色请求"""
    role: str                   # "admin" | "user"
