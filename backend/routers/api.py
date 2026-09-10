"""API 路由定义（已接入角色鉴权）

- 所有接口需登录（Bearer Token）
- 普通用户：解析/查看/导出/编辑自己的项目
- 管理员：以上全部 + 查看所有人项目 + 删除项目
- v2.4：多语言解析（dispatcher 分发）+ 文档在线编辑（doc 端点）
"""

import os
import uuid
import shutil
import zipfile
import tempfile
import asyncio
import logging
import urllib.parse

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, PlainTextResponse

from models.schemas import ProjectMeta, EndpointMeta
from parser.dispatcher import parse_project_any
from ai.enhancer import enhance_all, enhance_endpoint
from generator.openapi_gen import generate_openapi
from generator.markdown_gen import generate_markdown
from store import projects, endpoints, docs
from config import SAMPLE_PROJECT_PATH
from security import get_current_user, require_admin, check_project_owner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api-doc-generator"])


@router.post("/parse")
async def parse(
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    user=Depends(get_current_user),
):
    """上传并解析项目（需登录，项目归属当前用户）"""
    # 参数校验：file 和 path 二选一
    if file is None and not path:
        raise HTTPException(
            status_code=422,
            detail="请提供 file(上传ZIP) 或 path(本地路径)，二选一",
        )
    if file is not None and path:
        raise HTTPException(
            status_code=400,
            detail="file 和 path 只能二选一",
        )

    # 确定 project_path
    if path:
        project_path = path
        if not os.path.isdir(project_path):
            raise HTTPException(status_code=404, detail=f"路径不存在: {path}")
    else:
        # 上传 ZIP，解压到临时目录
        project_path = await _save_and_extract_zip(file)

    project_name = os.path.basename(os.path.normpath(project_path))
    project = await _parse_and_store(project_path, project_name, user)
    return project.model_dump()


async def _parse_and_store(project_path: str, project_name: str, user) -> ProjectMeta:
    """解析项目并入库（/parse 与 /parse-sample 公共逻辑）"""
    try:
        project = parse_project_any(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {e}")

    if not project.controllers and not project.engineInfo.get("detected", True):
        raise HTTPException(
            status_code=422,
            detail="未发现可解析的源码文件（支持 Java/Python/C 项目）",
        )

    project.projectId = str(uuid.uuid4())
    project.projectName = project_name
    project.ownerUserId = user.userId
    project.ownerName = user.username

    for ctrl in project.controllers:
        ctrl.controllerId = str(uuid.uuid4())
        for ep in ctrl.endpoints:
            ep.endpointId = str(uuid.uuid4())
            endpoints.set_with_project(ep.endpointId, ep, project.projectId)

    projects[project.projectId] = project

    all_endpoints = [
        ep for ctrl in project.controllers for ep in ctrl.endpoints
    ]
    await enhance_all(all_endpoints)

    for ep in all_endpoints:
        endpoints.set_with_project(ep.endpointId, ep, project.projectId)
    projects[project.projectId] = project

    return project


@router.get("/project")
async def list_projects(user=Depends(get_current_user)):
    """获取已解析的项目列表（普通用户仅自己的，管理员全部）"""
    if user.role == "admin":
        return [p.model_dump() for p in projects.list_all()]
    return [
        p.model_dump()
        for p in projects.list_all()
        if not p.ownerUserId or p.ownerUserId == user.userId
    ]


@router.get("/project/{project_id}")
async def get_project(project_id: str, user=Depends(get_current_user)):
    """获取项目接口列表"""
    project = projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_project_owner(project, user)
    return project.model_dump()


@router.get("/endpoint/{endpoint_id}")
async def get_endpoint(endpoint_id: str, user=Depends(get_current_user)):
    """获取单个接口详情"""
    ep = endpoints.get(endpoint_id)
    if not ep:
        raise HTTPException(status_code=404, detail="接口不存在")
    _check_endpoint_owner(endpoint_id, user)
    return ep.model_dump()


@router.post("/endpoint/{endpoint_id}/enhance")
async def re_enhance_endpoint(endpoint_id: str, user=Depends(get_current_user)):
    """重新生成单个接口的 AI 增强"""
    ep = endpoints.get(endpoint_id)
    if not ep:
        raise HTTPException(status_code=404, detail="接口不存在")
    _check_endpoint_owner(endpoint_id, user)

    await enhance_endpoint(ep)
    endpoints[endpoint_id] = ep  # 更新持久化
    return ep.model_dump()


@router.put("/endpoint/{endpoint_id}")
async def update_endpoint(endpoint_id: str, body: dict, user=Depends(get_current_user)):
    """编辑接口信息"""
    ep = endpoints.get(endpoint_id)
    if not ep:
        raise HTTPException(status_code=404, detail="接口不存在")
    _check_endpoint_owner(endpoint_id, user)

    if "description" in body:
        ep.description = body["description"]
    if "edgeCases" in body and isinstance(body["edgeCases"], list):
        ep.edgeCases = body["edgeCases"]
    if "params" in body and isinstance(body["params"], list):
        for p_update in body["params"]:
            for p in ep.params:
                if p.name == p_update.get("name"):
                    if "description" in p_update:
                        p.description = p_update["description"]
                    if "example" in p_update:
                        p.example = p_update["example"]

    endpoints[endpoint_id] = ep  # 更新持久化
    return {"success": True}


@router.delete("/project/{project_id}")
async def delete_project(project_id: str, user=Depends(get_current_user)):
    """删除项目及其所有接口（需项目归属，管理员可删任何项目）"""
    project = projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_project_owner(project, user)
    if not projects.delete(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    logger.info(f"用户 {user.username} 删除项目 {project_id}")
    return {"success": True}


@router.get("/project/{project_id}/export")
async def export_project(
    project_id: str,
    format: str = "openapi",
    user=Depends(get_current_user),
):
    """导出文档：后端直接返回文件流并设置文件名（修复下载文件名丢失问题）

    v2.4：若存在用户编辑版（docs 表），优先返回编辑版，与在线预览一致
    """
    project = projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_project_owner(project, user)

    if format == "openapi":
        content = docs.get(project_id, "openapi") or generate_openapi(project)
        filename = f"{project.projectName}_openapi.json"
        media_type = "application/json"
    elif format == "markdown":
        content = docs.get(project_id, "markdown") or generate_markdown(project)
        filename = f"{project.projectName}_api_doc.md"
        media_type = "text/markdown"
    else:
        raise HTTPException(
            status_code=422,
            detail="format 参数仅支持 openapi 或 markdown",
        )

    # RFC 5987：filename 处理 ASCII 回退，filename* 处理中文等非 ASCII 文件名
    ascii_name = filename.encode("ascii", errors="ignore").decode() or "export"
    quoted_name = urllib.parse.quote(filename)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{quoted_name}"
        )
    }
    return PlainTextResponse(content=content, media_type=media_type, headers=headers)


# ========== v2.4 文档在线编辑 ==========


@router.get("/project/{project_id}/doc")
async def get_doc(
    project_id: str,
    format: str = "markdown",
    user=Depends(get_current_user),
):
    """获取文档内容：优先返回用户编辑版，无则现场生成

    返回 {content, edited}：edited=True 表示当前内容来自用户编辑版
    """
    project = projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_project_owner(project, user)

    if format not in ("openapi", "markdown"):
        raise HTTPException(status_code=422, detail="format 仅支持 openapi 或 markdown")

    edited_content = docs.get(project_id, format)
    if edited_content is not None:
        return {"content": edited_content, "edited": True}

    generated = (
        generate_openapi(project) if format == "openapi" else generate_markdown(project)
    )
    return {"content": generated, "edited": False}


@router.put("/project/{project_id}/doc")
async def save_doc(
    project_id: str,
    body: dict,
    user=Depends(get_current_user),
):
    """保存文档编辑版 body: {format, content}"""
    project = projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_project_owner(project, user)

    fmt = body.get("format", "")
    content = body.get("content")
    if fmt not in ("openapi", "markdown"):
        raise HTTPException(status_code=422, detail="format 仅支持 openapi 或 markdown")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=422, detail="content 不能为空")

    docs.set(project_id, fmt, content)
    logger.info(f"用户 {user.username} 保存文档编辑版: {project_id} ({fmt})")
    return {"success": True, "edited": True}


@router.post("/project/{project_id}/doc/reset")
async def reset_doc(
    project_id: str,
    body: dict,
    user=Depends(get_current_user),
):
    """清除编辑版，恢复生成器现场生成版 body: {format}"""
    project = projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_project_owner(project, user)

    fmt = body.get("format", "")
    if fmt not in ("openapi", "markdown"):
        raise HTTPException(status_code=422, detail="format 仅支持 openapi 或 markdown")

    had_edited = docs.reset(project_id, fmt)
    if had_edited:
        logger.info(f"用户 {user.username} 重置文档: {project_id} ({fmt})")

    # 返回重置后的生成版内容，前端直接刷新预览
    project = projects.get(project_id)
    generated = (
        generate_openapi(project) if fmt == "openapi" else generate_markdown(project)
    )
    return {"success": True, "edited": False, "content": generated}


def _check_endpoint_owner(endpoint_id: str, user):
    """接口级归属校验：管理员放行，普通用户只能访问自己项目的接口"""
    if user.role == "admin":
        return
    project_id = endpoints.get_project_id(endpoint_id)
    if not project_id:
        return
    project = projects.get(project_id)
    if project:
        check_project_owner(project, user)


async def _save_and_extract_zip(file: UploadFile) -> str:
    """保存上传的 ZIP 文件并解压到临时目录"""
    tmp_dir = tempfile.mkdtemp(prefix="aiapidoc_")
    zip_path = os.path.join(tmp_dir, file.filename or "project.zip")

    with open(zip_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 解压
    extract_dir = os.path.join(tmp_dir, "project")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    # 如果解压后只有一个目录，则进入该目录
    entries = os.listdir(extract_dir)
    if len(entries) == 1:
        single = os.path.join(extract_dir, entries[0])
        if os.path.isdir(single):
            return single

    return extract_dir


@router.post("/parse-sample")
async def parse_sample(user=Depends(get_current_user)):
    """快捷接口：直接解析内置的 spring-petclinic 示例项目（需登录）"""
    if not os.path.isdir(SAMPLE_PROJECT_PATH):
        raise HTTPException(
            status_code=404,
            detail=f"示例项目不存在: {SAMPLE_PROJECT_PATH}",
        )

    project_name = os.path.basename(os.path.normpath(SAMPLE_PROJECT_PATH))
    project = await _parse_and_store(SAMPLE_PROJECT_PATH, project_name, user)
    return project.model_dump()
