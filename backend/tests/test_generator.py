"""文档生成器单元测试

覆盖：
1. OpenAPI 生成：路径、方法、参数、响应
2. Markdown 生成：标题、参数表、示例、边界场景
"""

import json
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator.openapi_gen import generate_openapi
from generator.markdown_gen import generate_markdown
from models.schemas import (
    ProjectMeta, ControllerMeta, EndpointMeta, ParamMeta, HTTPMethod,
)


def _make_project() -> ProjectMeta:
    """构造测试项目"""
    ep = EndpointMeta(
        endpointId="ep-001",
        method=HTTPMethod.POST,
        path="/users",
        fullPath="/api/users",
        javaMethod="createUser",
        returnType="User",
        params=[
            ParamMeta(name="user", type="User", annotation="@RequestBody", required=True),
        ],
        description="创建用户",
        requestExample='{"name": "张三", "email": "zhangsan@example.com"}',
        responseExample='{"id": 1, "name": "张三"}',
        edgeCases=["邮箱格式不合法", "用户名重复"],
        errorCodes=[{"code": "400", "description": "参数校验失败"}],
    )
    ctrl = ControllerMeta(
        controllerId="ctrl-001",
        className="UserController",
        baseUrl="/api",
        endpoints=[ep],
    )
    return ProjectMeta(
        projectId="proj-001",
        projectName="test-project",
        controllers=[ctrl],
    )


class TestOpenApiGenerator:

    def test_openapi_structure(self):
        project = _make_project()
        result = json.loads(generate_openapi(project))
        assert result["openapi"] == "3.0.3"
        assert "info" in result
        assert "paths" in result

    def test_openapi_path_and_method(self):
        project = _make_project()
        result = json.loads(generate_openapi(project))
        assert "/api/users" in result["paths"]
        assert "post" in result["paths"]["/api/users"]

    def test_openapi_summary(self):
        project = _make_project()
        result = json.loads(generate_openapi(project))
        op = result["paths"]["/api/users"]["post"]
        assert op["summary"] == "创建用户"

    def test_openapi_request_body(self):
        project = _make_project()
        result = json.loads(generate_openapi(project))
        op = result["paths"]["/api/users"]["post"]
        assert "requestBody" in op
        assert "application/json" in op["requestBody"]["content"]

    def test_openapi_response_example(self):
        project = _make_project()
        result = json.loads(generate_openapi(project))
        op = result["paths"]["/api/users"]["post"]
        assert "200" in op["responses"]
        assert "application/json" in op["responses"]["200"]["content"]

    def test_openapi_error_codes(self):
        project = _make_project()
        result = json.loads(generate_openapi(project))
        op = result["paths"]["/api/users"]["post"]
        assert "400" in op["responses"]

    def test_openapi_java_type_mapping(self):
        """Java 类型应正确映射到 OpenAPI 类型"""
        from generator.openapi_gen import _java_type_to_openapi
        assert _java_type_to_openapi("int") == "integer"
        assert _java_type_to_openapi("Long") == "integer"
        assert _java_type_to_openapi("String") == "string"
        assert _java_type_to_openapi("Boolean") == "boolean"
        assert _java_type_to_openapi("Double") == "number"


class TestMarkdownGenerator:

    def test_markdown_title(self):
        project = _make_project()
        md = generate_markdown(project)
        assert "# test-project 接口文档" in md

    def test_markdown_controller_header(self):
        project = _make_project()
        md = generate_markdown(project)
        assert "## UserController" in md

    def test_markdown_endpoint_path(self):
        project = _make_project()
        md = generate_markdown(project)
        assert "POST /api/users" in md

    def test_markdown_param_table(self):
        project = _make_project()
        md = generate_markdown(project)
        assert "| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |" in md
        assert "user" in md

    def test_markdown_request_example(self):
        project = _make_project()
        md = generate_markdown(project)
        assert "请求示例" in md
        assert "张三" in md

    def test_markdown_edge_cases(self):
        project = _make_project()
        md = generate_markdown(project)
        assert "边界场景" in md
        assert "邮箱格式不合法" in md

    def test_markdown_error_codes(self):
        project = _make_project()
        md = generate_markdown(project)
        assert "错误码" in md
        assert "400" in md
