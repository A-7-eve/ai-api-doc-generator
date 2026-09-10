"""多语言分发器单元测试（v2.4 任务1+2 核心）

覆盖：
1. 语言检测（detect_languages）
2. 混合语言项目解析合并
3. 纯 Java 项目向后兼容
4. 空项目处理
5. engineInfo 元数据（引擎名/版本/降级标记）
"""

import pytest
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.dispatcher import parse_project_any
from parser.engine_registry import detect_languages, get_engine, all_engines


JAVA_SRC = """\
package com.demo;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping("/{id}")
    public String getUser(@PathVariable Long id) {
        return "user";
    }

    @PostMapping
    public String createUser(@RequestBody String body) {
        return "ok";
    }
}
"""

PYTHON_SRC = """\
from fastapi import APIRouter
router = APIRouter()

@router.get("/orders/{order_id}")
async def get_order(order_id: int):
    \"\"\"查询订单\"\"\"
    return {"id": order_id}
"""

C_SRC = """\
// 读取设备数据
int read_device(int device_id) {
    return 0;
}
"""


def _make_project(td: str, with_java=True, with_python=True, with_c=True):
    """构造混合语言测试项目"""
    proj = os.path.join(td, "mixed-project")
    if with_java:
        d = os.path.join(proj, "src", "main", "java", "com", "demo")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "UserController.java"), "w", encoding="utf-8") as f:
            f.write(JAVA_SRC)
    if with_python:
        d = os.path.join(proj, "api")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "order_api.py"), "w", encoding="utf-8") as f:
            f.write(PYTHON_SRC)
    if with_c:
        d = os.path.join(proj, "native")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "device.c"), "w", encoding="utf-8") as f:
            f.write(C_SRC)
    # 无关文件（不计入语言检测）
    with open(os.path.join(proj, "README.md"), "w", encoding="utf-8") as f:
        f.write("# demo")
    return proj


class TestDetectLanguages:
    def test_detect_mixed(self, tmp_path):
        proj = _make_project(str(tmp_path))
        counts = detect_languages(proj)
        assert counts == {"java": 1, "python": 1, "c": 1}

    def test_detect_empty(self, tmp_path):
        proj = os.path.join(str(tmp_path), "nothing")
        os.makedirs(proj)
        assert detect_languages(proj) == {}

    def test_detect_missing_dir(self, tmp_path):
        assert detect_languages(os.path.join(str(tmp_path), "no-such-dir")) == {}


class TestParseProjectAny:
    def test_mixed_language_merge(self, tmp_path):
        proj = _make_project(str(tmp_path))
        meta = parse_project_any(proj)
        assert set(meta.languages) == {"java", "python", "c"}
        # Java 2 + Python 1 + C 1 = 4
        total = sum(len(c.endpoints) for c in meta.controllers)
        assert total == 4

    def test_engine_info_populated(self, tmp_path):
        proj = _make_project(str(tmp_path))
        meta = parse_project_any(proj)
        info = meta.engineInfo
        assert info.get("detected") is True
        assert info["java"]["engine"] == "javalang-ast"
        assert info["python"]["engine"] == "python-ast"
        assert info["c"]["engine"] == "c-regex"
        assert info["java"]["endpointCount"] == 2
        assert "syntaxVersions" in info["java"]  # 版本管理信息

    def test_java_only_backward_compatible(self, tmp_path):
        proj = _make_project(str(tmp_path), with_python=False, with_c=False)
        meta = parse_project_any(proj)
        assert meta.languages == ["java"]
        assert sum(len(c.endpoints) for c in meta.controllers) == 2

    def test_empty_project(self, tmp_path):
        proj = os.path.join(str(tmp_path), "empty")
        os.makedirs(proj)
        meta = parse_project_any(proj)
        assert meta.controllers == []
        assert meta.engineInfo.get("detected") is False

    def test_project_name(self, tmp_path):
        proj = _make_project(str(tmp_path))
        meta = parse_project_any(proj)
        assert meta.projectName == "mixed-project"


class TestEngineRegistry:
    def test_all_engines_registered(self):
        engines = all_engines()
        langs = {l for e in engines for l in e.languages}
        assert {"java", "python", "c"} <= langs

    def test_get_engine_by_language(self):
        assert get_engine("java") is not None
        assert get_engine("python") is not None
        assert get_engine("c") is not None
        assert get_engine("golang") is None

    def test_engine_syntax_versions_documented(self):
        for eng in all_engines():
            assert eng.syntax_versions, f"{eng.name} 应声明 syntax_versions"
            assert eng.version
            assert eng.extensions
