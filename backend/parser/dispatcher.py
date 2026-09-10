"""多语言解析分发器（v2.4）。

parse_project_any(project_path)：
- 扫描项目目录识别语言组合
- 按语言逐引擎解析，合并各引擎的 ProjectMeta
- 单一语言时行为与原 parse_project 完全一致（向后兼容）
- 混合语言项目：controllers 合并、languages 标注、engineInfo 记录每语言引擎与降级状态
- 未知语言文件（如 .go/.rs）不参与解析，记入 engineInfo.unsupported
"""

import logging
from typing import Optional

from models.schemas import ProjectMeta
from parser.engine_registry import detect_languages, get_engine

logger = logging.getLogger(__name__)

# endpoint 对象 id → 语言标记（同一 ProjectMeta 生命周期内有效）
_LANG_TAGS: dict[int, str] = {}


def get_endpoint_language(endpoint) -> str:
    """查询 endpoint 的来源语言（供 AI 增强层自适应），未知返回空串"""
    return _LANG_TAGS.get(id(endpoint), "")


def parse_project_any(project_path: str) -> ProjectMeta:
    """解析任意语言组合的项目，自动分发到对应引擎"""
    import os

    project_name = os.path.basename(os.path.normpath(project_path))
    lang_counts = detect_languages(project_path)

    if not lang_counts:
        # 没有可识别的源码文件：返回空 ProjectMeta（api 层会给出提示）
        logger.warning(f"项目 {project_path} 未发现可解析的源码文件")
        return ProjectMeta(
            projectName=project_name,
            controllers=[],
            languages=[],
            engineInfo={"detected": False},
        )

    merged = ProjectMeta(projectName=project_name)
    languages: list[str] = []
    engine_info: dict = {"detected": True}

    for lang, count in lang_counts.items():
        engine = get_engine(lang)
        if engine is None:
            engine_info[lang] = {"engine": None, "error": "未注册解析引擎"}
            continue
        try:
            sub_meta = engine.parse_func(project_path)
        except Exception as e:
            # 单语言解析失败不阻断其他语言
            logger.error(f"{lang} 引擎解析失败: {e}")
            engine_info[lang] = {
                "engine": engine.name, "version": engine.version,
                "fileCount": count, "error": str(e),
            }
            continue

        # 语言标记（供 AI 增强层自适应提示词；pydantic 模型不允许动态属性，
        # 用对象 id 作 key 缓存，由 enhancer 消费）
        for ctrl in sub_meta.controllers:
            for ep in ctrl.endpoints:
                _LANG_TAGS[id(ep)] = lang

        merged.controllers.extend(sub_meta.controllers)
        merged.dtos.extend(sub_meta.dtos)
        languages.append(lang)
        engine_info[lang] = {
            "engine": engine.name,
            "version": engine.version,
            "fileCount": count,
            "syntaxVersions": engine.syntax_versions,
            "controllerCount": len(sub_meta.controllers),
            "endpointCount": sum(len(c.endpoints) for c in sub_meta.controllers),
        }
        # 降级检测：Python/C 引擎在 Controller 注释中标记"正则兜底"
        degraded = any(
            c.comment and "正则兜底" in c.comment
            for c in sub_meta.controllers
        )
        engine_info[lang]["degraded"] = degraded

    merged.languages = languages
    merged.engineInfo = engine_info
    return merged
