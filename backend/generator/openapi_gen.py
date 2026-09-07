"""OpenAPI 3.0 文档生成器"""

import json
from models.schemas import ProjectMeta


def generate_openapi(project: ProjectMeta) -> str:
    """生成 OpenAPI 3.0 JSON

    Args:
        project: 项目元数据

    Returns:
        OpenAPI JSON 字符串
    """
    paths = {}

    for controller in project.controllers:
        for ep in controller.endpoints:
            path_key = ep.fullPath or "/"
            method_key = ep.method.value.lower()

            if path_key not in paths:
                paths[path_key] = {}

            # 构建 parameters
            parameters = []
            request_body = None
            for p in ep.params:
                if p.annotation == "@PathVariable":
                    parameters.append({
                        "name": p.name,
                        "in": "path",
                        "required": True,
                        "schema": {"type": _java_type_to_openapi(p.type)},
                        "description": p.description or "",
                    })
                elif p.annotation == "@RequestParam":
                    parameters.append({
                        "name": p.name,
                        "in": "query",
                        "required": p.required,
                        "schema": {"type": _java_type_to_openapi(p.type)},
                        "description": p.description or "",
                    })
                elif p.annotation == "@RequestBody":
                    request_body = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": _safe_json(ep.requestExample)
                            }
                        }
                    }

            # 构建 responses
            responses = {
                "200": {
                    "description": "成功",
                }
            }
            if ep.responseExample:
                responses["200"]["content"] = {
                    "application/json": {
                        "example": _safe_json(ep.responseExample)
                    }
                }

            # 错误码
            for err in ep.errorCodes:
                code = str(err.get("code", "500"))
                if code != "200":
                    responses[code] = {
                        "description": err.get("description", "")
                    }

            operation = {
                "summary": ep.description or ep.javaMethod,
                "operationId": ep.javaMethod,
                "parameters": parameters if parameters else None,
                "responses": responses,
            }

            if request_body:
                operation["requestBody"] = request_body

            # 清理 None 值
            operation = {k: v for k, v in operation.items() if v is not None}

            paths[path_key][method_key] = operation

    openapi_doc = {
        "openapi": "3.0.3",
        "info": {
            "title": f"{project.projectName} 接口文档",
            "version": "1.0.0",
            "description": "由 AI 辅助接口文档自动生成系统生成",
        },
        "paths": paths,
    }

    return json.dumps(openapi_doc, ensure_ascii=False, indent=2)


def _java_type_to_openapi(java_type: str) -> str:
    """Java 类型转 OpenAPI 类型"""
    mapping = {
        "int": "integer",
        "Integer": "integer",
        "long": "integer",
        "Long": "integer",
        "short": "integer",
        "Short": "integer",
        "float": "number",
        "Float": "number",
        "double": "number",
        "Double": "number",
        "String": "string",
        "boolean": "boolean",
        "Boolean": "boolean",
        "char": "string",
        "Character": "string",
    }
    return mapping.get(java_type, "string")


def _safe_json(example: str | None) -> str | dict:
    """安全解析 JSON 示例"""
    if not example:
        return ""
    try:
        return json.loads(example)
    except (json.JSONDecodeError, TypeError):
        return example
