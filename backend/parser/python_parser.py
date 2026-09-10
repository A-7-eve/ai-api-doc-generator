"""Python 代码解析模块：用内置 ast 模块解析 Web 框架路由，提取接口元数据。

支持框架（装饰器路由风格）：
- FastAPI: @app.get("/path") / @router.post("/path") / APIRouter
- Flask:   @app.route("/path", methods=["GET"]) 及快捷 @app.get("/path")

解析策略：
1. 优先使用 ast 精确解析（函数签名、类型注解、docstring 完整提取）
2. ast 解析失败（语法过新/过旧/损坏）时降级为正则兜底（regex_parse_file）

语法版本（任务2 版本管理）：
- ast 模块随 CPython 演进，本引擎在 Python 3.10+ 运行时上可解析 3.0~3.12 语法
- 3.12+ 新语法（如 PEP 695 type 别名）在旧解释器上 ast.parse 会抛 SyntaxError，
  此时自动降级为正则提取，保证"语言版本兼容性"
"""

import os
import ast
import re
import logging
from typing import Optional

from models.schemas import (
    ProjectMeta, ControllerMeta, EndpointMeta, ParamMeta, HTTPMethod,
)

logger = logging.getLogger(__name__)

# 引擎信息（供 engine_registry 汇总）
ENGINE_NAME = "python-ast"
ENGINE_VERSION = "1.0"

# 支持的 HTTP 方法装饰器名（FastAPI / Flask 2.0+ 快捷方式）
METHOD_DECORATORS = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "delete": "DELETE",
    "patch": "PATCH",
}

# Flask @app.route(methods=[...]) 的 methods 参数
_FLASK_METHODS_RE = re.compile(r"methods\s*=\s*\[([^\]]*)\]")


def parse_python_project(project_path: str) -> ProjectMeta:
    """解析整个 Python 项目中的 Web 路由"""
    project_name = os.path.basename(os.path.normpath(project_path))
    controllers: list[ControllerMeta] = []

    for root, _dirs, files in os.walk(project_path):
        # 跳过测试/虚拟环境/缓存目录
        parts = os.path.normpath(root).split(os.sep)
        if any(seg in parts for seg in ("test", "tests", "venv", ".venv", "__pycache__")):
            continue
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            ctrl = parse_python_file(source, fname)
            if ctrl and ctrl.endpoints:
                controllers.append(ctrl)

    return ProjectMeta(projectName=project_name, controllers=controllers)


def parse_python_file(source: str, filename: str = "module.py") -> Optional[ControllerMeta]:
    """解析单个 Python 文件中的路由

    每个 .py 文件视为一个"Controller"（className=模块名），
    文件内的路由函数视为该 Controller 的接口。
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        logger.warning(f"Python ast 解析失败({filename}): {e}，降级正则兜底")
        return _regex_parse_python_file(source, filename)

    endpoints: list[EndpointMeta] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        ep = _parse_route_function(node, source)
        if ep:
            endpoints.append(ep)

    if not endpoints:
        return None

    return ControllerMeta(
        className=filename,
        baseUrl="",
        endpoints=endpoints,
        comment=f"Python 模块 {filename}",
    )


def _parse_route_function(
    node: "ast.FunctionDef | ast.AsyncFunctionDef",
    source: str,
) -> Optional[EndpointMeta]:
    """检查函数是否带路由装饰器，是则提取 EndpointMeta"""
    method: Optional[str] = None
    path = ""
    base_path = ""

    for dec in node.decorator_list:
        # 形态1: @app.get("/x") / @router.post("/x")
        m = _match_method_decorator(dec)
        if m:
            method, path = m
            continue
        # 形态2: @app.route("/x", methods=["GET"])  （Flask）
        m2 = _match_flask_route(dec)
        if m2:
            path, base_path = m2
            # methods 参数稍后从源码正则提取
            method = None

    if not path and not method:
        return None  # 没有路由装饰器，跳过

    # Flask route 的方法从源码提取
    if method is None:
        dec_src = ast.get_source_segment(source, node.decorator_list[0]) or ""
        mm = _FLASK_METHODS_RE.search(dec_src)
        if mm:
            first = mm.group(1).strip().strip("\"'").split(",")[0].strip().strip("\"'")
            method = first.upper() if first else "GET"
        else:
            method = "GET"  # Flask 默认 GET

    full_path = (base_path + path) if base_path else path

    # 提取参数：带类型注解的形参（跳过 self/cls/请求对象）
    params = _extract_params(node)

    # docstring 作为注释
    doc = ast.get_docstring(node)

    return EndpointMeta(
        method=HTTPMethod(method.upper()),
        path=path,
        fullPath=full_path,
        javaMethod=node.name,  # 字段名沿用 javaMethod，实际是函数名
        returnType=_annotation_to_str(node.returns),
        comment=doc,
        sourceCode=ast.get_source_segment(source, node) or "",
        params=params,
    )


def _match_method_decorator(dec) -> Optional[tuple[str, str]]:
    """匹配 @xxx.get("/path") 形态的装饰器，返回 (HTTP方法, 路径)"""
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr not in METHOD_DECORATORS:
        return None
    # 取第一个字符串参数作为路径
    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
        return METHOD_DECORATORS[func.attr], dec.args[0].value
    return METHOD_DECORATORS[func.attr], ""


def _match_flask_route(dec) -> Optional[tuple[str, str]]:
    """匹配 @xxx.route("/path", ...) 形态，返回 (路径, 基础路径占位"")"""
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    if not isinstance(func, ast.Attribute) or func.attr != "route":
        return None
    if dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
        return dec.args[0].value, ""
    return None


def _extract_params(node) -> list[ParamMeta]:
    """提取函数参数（带注解的才记录，跳过内置对象）"""
    skip_names = {"self", "cls", "request", "db", "session", "background_tasks", "user"}
    params: list[ParamMeta] = []
    all_args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
    # 每个位置参数的默认值（无默认值时为 None）；kwonly 默认值单独处理
    defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + list(node.args.defaults)
    arg_default_map = dict(zip(node.args.args, defaults))

    for arg in all_args:
        if arg.arg in skip_names:
            continue
        # 判断是否是路径参数：FastAPI 路径中含 {name}；无注解的简单参数视为 query
        ann = _annotation_to_str(arg.annotation)
        if not ann:
            continue
        default = arg_default_map.get(arg) if arg in node.args.args else node.args.kw_defaults[
            node.args.kwonlyargs.index(arg)
        ]
        # pydantic BaseModel 子类参数 → 请求体
        is_body = ann.lower() in ("body", "payload") or ann.endswith("Schema") or ann.endswith("Create") or ann.endswith("Update")
        params.append(
            ParamMeta(
                name=arg.arg,
                type=ann,
                annotation="@RequestBody" if is_body else "@RequestParam",
                required=default is None,
            )
        )
    return params


def _annotation_to_str(annotation) -> Optional[str]:
    """类型注解转字符串"""
    if annotation is None:
        return None
    try:
        return ast.unparse(annotation)
    except Exception:
        return None


# ── 正则兜底（ast 失败时）──

_PY_ROUTE_RE = re.compile(
    r'@\w+\.(get|post|put|delete|patch|route)\s*\(\s*["\']([^"\']*)["\']',
    re.MULTILINE,
)

_PY_FUNC_RE = re.compile(
    r'def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*[\w\[\],\s\.]+)?:',
    re.MULTILINE,
)


def _regex_parse_python_file(source: str, filename: str) -> Optional[ControllerMeta]:
    """正则兜底：提取 @app.get("/x") def fn(...): 结构"""
    endpoints: list[EndpointMeta] = []
    lines = source.split("\n")

    for i, line in enumerate(lines):
        m = _PY_ROUTE_RE.search(line)
        if not m:
            continue
        dec_name, path = m.group(1).lower(), m.group(2)
        method = METHOD_DECORATORS.get(dec_name, "GET")

        # 向后找 def（装饰器后 1~3 行内）
        for j in range(i + 1, min(i + 4, len(lines))):
            fm = _PY_FUNC_RE.search(lines[j])
            if fm:
                fname, arg_str = fm.group(1), fm.group(2)
                params = [
                    ParamMeta(name=a.strip().split(":")[0].strip(), type="Any",
                              annotation="@RequestParam", required=True)
                    for a in arg_str.split(",") if a.strip() and ":" in a
                ]
                endpoints.append(
                    EndpointMeta(
                        method=HTTPMethod(method.upper()),
                        path=path,
                        fullPath=path,
                        javaMethod=fname,
                        comment=None,
                        sourceCode="",
                        params=params,
                    )
                )
                break

    if not endpoints:
        return None
    return ControllerMeta(
        className=filename,
        baseUrl="",
        endpoints=endpoints,
        comment=f"Python 模块 {filename}（正则兜底解析）",
    )
