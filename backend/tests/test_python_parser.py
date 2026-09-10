"""Python 代码解析器单元测试（v2.4 多语言支持）

覆盖：
1. FastAPI 装饰器路由（@app.get/@router.post 等）
2. Flask 路由（@app.route methods 提取 / 缺省 GET）
3. 参数提取（类型注解 → ParamMeta）
4. docstring → comment
5. 语法错误降级正则兜底
6. 目录级解析（跳过 tests/venv 目录）
"""

import pytest
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.python_parser import (
    parse_python_project,
    parse_python_file,
    ENGINE_NAME,
    ENGINE_VERSION,
)


# ── 测试数据 ──

FASTAPI_SRC = """\
from fastapi import FastAPI
app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, verbose: bool = False):
    \"\"\"获取用户详情\"\"\"
    return {"id": user_id}

@app.post("/users")
async def create_user(user: UserCreate):
    \"\"\"创建用户\"\"\"
    return {"ok": True}
"""

FLASK_SRC = """\
from flask import Flask
app = Flask(__name__)

@app.route("/hello", methods=["POST"])
def hello():
    return "hi"

@app.route("/items/<int:item_id>")
def get_item(item_id):
    return str(item_id)
"""

PLAIN_SRC = """\
def add(a, b):
    return a + b
"""

BAD_SYNTAX_SRC = """\
@app.get("/bad/path"  # 缺右括号 → SyntaxError
def bad_fn(x):
    pass
"""


# ── FastAPI 解析 ──

class TestFastAPI:
    def test_parse_fastapi_controller(self):
        ctrl = parse_python_file(FASTAPI_SRC, "user_api.py")
        assert ctrl is not None
        assert ctrl.className == "user_api.py"
        assert len(ctrl.endpoints) == 2

    def test_get_endpoint(self):
        ctrl = parse_python_file(FASTAPI_SRC, "user_api.py")
        e1 = ctrl.endpoints[0]
        assert e1.method.value == "GET"
        assert e1.path == "/users/{user_id}"
        assert e1.javaMethod == "get_user"
        assert e1.comment == "获取用户详情"

    def test_post_endpoint(self):
        ctrl = parse_python_file(FASTAPI_SRC, "user_api.py")
        e2 = ctrl.endpoints[1]
        assert e2.method.value == "POST"
        assert e2.javaMethod == "create_user"

    def test_params_extracted(self):
        ctrl = parse_python_file(FASTAPI_SRC, "user_api.py")
        e1 = ctrl.endpoints[0]
        p_names = [p.name for p in e1.params]
        assert "user_id" in p_names
        p = next(p for p in e1.params if p.name == "user_id")
        assert p.type == "int"
        assert p.required is True  # 无默认值

    def test_default_param_not_required(self):
        ctrl = parse_python_file(FASTAPI_SRC, "user_api.py")
        e1 = ctrl.endpoints[0]
        verbose = next(p for p in e1.params if p.name == "verbose")
        assert verbose.required is False  # 有默认值

    def test_return_type(self):
        ctrl = parse_python_file(FASTAPI_SRC, "user_api.py")
        e1 = ctrl.endpoints[0]
        # get_user 无返回注解 → None；create_order 有注解时才提取
        assert e1.returnType is None or "dict" in e1.returnType


# ── Flask 解析 ──

class TestFlask:
    def test_parse_flask_controller(self):
        ctrl = parse_python_file(FLASK_SRC, "flask_app.py")
        assert ctrl is not None
        assert len(ctrl.endpoints) == 2

    def test_flask_methods_extracted(self):
        ctrl = parse_python_file(FLASK_SRC, "flask_app.py")
        h1 = ctrl.endpoints[0]
        assert h1.method.value == "POST"  # methods=["POST"]

    def test_flask_default_get(self):
        ctrl = parse_python_file(FLASK_SRC, "flask_app.py")
        h2 = ctrl.endpoints[1]
        assert h2.method.value == "GET"   # 无 methods 默认 GET

    def test_flask_converter_path(self):
        ctrl = parse_python_file(FLASK_SRC, "flask_app.py")
        h2 = ctrl.endpoints[1]
        assert h2.path == "/items/<int:item_id>"


# ── 降级与边界 ──

class TestDegradation:
    def test_plain_file_returns_none(self):
        assert parse_python_file(PLAIN_SRC, "plain.py") is None

    def test_syntax_error_falls_back_to_regex(self):
        ctrl = parse_python_file(BAD_SYNTAX_SRC, "bad.py")
        assert ctrl is not None
        assert len(ctrl.endpoints) == 1
        b1 = ctrl.endpoints[0]
        assert b1.path == "/bad/path"
        assert b1.javaMethod == "bad_fn"
        assert "正则兜底" in (ctrl.comment or "")


# ── 目录级解析 ──

class TestProjectParse:
    def test_project_skips_test_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            proj = os.path.join(td, "demo-py")
            os.makedirs(os.path.join(proj, "routes"))
            os.makedirs(os.path.join(proj, "tests"))
            with open(os.path.join(proj, "routes", "api.py"), "w", encoding="utf-8") as f:
                f.write(FASTAPI_SRC)
            with open(os.path.join(proj, "tests", "test_api.py"), "w", encoding="utf-8") as f:
                f.write(FASTAPI_SRC)  # tests 目录内容应被跳过
            with open(os.path.join(proj, "tools.py"), "w", encoding="utf-8") as f:
                f.write(PLAIN_SRC)

            meta = parse_python_project(proj)
            assert meta.projectName == "demo-py"
            # 只有 routes/api.py 生成 Controller
            assert len(meta.controllers) == 1
            assert meta.controllers[0].className == "api.py"

    def test_engine_info(self):
        assert ENGINE_NAME == "python-ast"
        assert ENGINE_VERSION == "1.0"
