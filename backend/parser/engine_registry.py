"""解析引擎注册表（v2.4 多语言 + 版本管理核心）。

设计：
- 每种语言注册一个引擎（name/version/languages/parse_func/syntax_versions）
- parse_func 签名统一: (project_path: str) -> ProjectMeta
- syntax_versions 描述该引擎支持的语法版本范围（版本管理需求的落地点）
- 引擎内部自带降级策略（AST 失败 → 正则），degraded 状态记入 ProjectMeta.engineInfo

扩展新语言只需三步：
1. 写 parser/xxx_parser.py（实现 parse_xxx_project）
2. 在 _ENGINES 中注册一条 ParseEngine
3. dispatcher 自动按扩展名分发，无需改动其他代码
"""

import logging
from dataclasses import dataclass, field
from typing import Callable

from models.schemas import ProjectMeta

logger = logging.getLogger(__name__)


@dataclass
class ParseEngine:
    """一个解析引擎的注册信息"""
    name: str                          # 引擎名，如 "javalang-ast"
    version: str                       # 引擎版本
    languages: list[str]               # 负责的语言，如 ["java"]
    extensions: list[str]              # 负责的文件扩展名，如 [".java"]
    parse_func: Callable[[str], ProjectMeta]     # 解析函数
    syntax_versions: str = ""          # 支持的语法版本描述
    degraded: bool = False             # 本次解析是否发生过降级


# ── 各语言引擎实例（延迟导入避免循环依赖）──

def _java_engine() -> ParseEngine:
    from parser.java_parser import parse_project
    return ParseEngine(
        name="javalang-ast",
        version="1.0",
        languages=["java"],
        extensions=[".java"],
        parse_func=parse_project,
        syntax_versions="Java 8~17 语法（Spring MVC 4.x/5.x/6.x 注解体系）；"
                        "AST 失败自动降级 javalang 正则模式",
    )


def _python_engine() -> ParseEngine:
    from parser.python_parser import parse_python_project
    return ParseEngine(
        name="python-ast",
        version="1.0",
        languages=["python"],
        extensions=[".py"],
        parse_func=parse_python_project,
        syntax_versions="Python 3.0~3.12 语法（FastAPI/Flask 装饰器路由）；"
                        "解释器无法解析的新语法自动降级正则模式",
    )


def _c_engine() -> ParseEngine:
    from parser.c_parser import parse_c_project
    return ParseEngine(
        name="c-regex",
        version="1.0",
        languages=["c"],
        extensions=[".c", ".h"],
        parse_func=parse_c_project,
        syntax_versions="ANSI C (C89) / C99 / C11 函数定义风格；"
                        "定位为函数清单（C 无路由注解体系）",
    )


# 扩展名 → 语言 映射（用于 detect_languages）
_EXT_TO_LANG = {
    ".java": "java",
    ".py": "python",
    ".c": "c",
    ".h": "c",
}

# 语言 → 引擎工厂（延迟构建）
_ENGINE_FACTORIES = {
    "java": _java_engine,
    "python": _python_engine,
    "c": _c_engine,
}


def get_engine(language: str) -> ParseEngine | None:
    """按语言名获取引擎实例"""
    factory = _ENGINE_FACTORIES.get(language)
    if factory is None:
        return None
    return factory()


def all_engines() -> list[ParseEngine]:
    """获取全部引擎实例（用于文档展示）"""
    return [factory() for factory in _ENGINE_FACTORIES.values()]


def detect_languages(project_path: str) -> dict[str, int]:
    """扫描项目目录，按扩展名统计各语言的文件数

    返回如 {"java": 27, "python": 5, "c": 2}；
    目录不存在或无已知扩展名文件时返回 {}
    """
    import os
    counts: dict[str, int] = {}
    if not os.path.isdir(project_path):
        return counts
    for root, _dirs, files in os.walk(project_path):
        # 跳过依赖/缓存目录（只判断目录名本身，不判断路径前缀——
        # 否则项目放在 .temp/venv 等目录下时整棵树会被误跳过）
        dir_name = os.path.basename(root)
        if dir_name in ("node_modules", "venv", "__pycache__", ".git", "build", "dist"):
            continue
        for fname in files:
            _stem, ext = os.path.splitext(fname)
            lang = _EXT_TO_LANG.get(ext.lower())
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
    return counts
