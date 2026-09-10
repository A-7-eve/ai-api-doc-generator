"""AI 增强层：调用云端大模型 API，为接口生成描述、示例、边界场景"""

import json
import re
import asyncio
import logging

import httpx

from config import LLM_API_URL, LLM_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_TIMEOUT, MAX_CONCURRENT_AI
from ai.prompts import SYSTEM_PROMPT, build_user_prompt
from models.schemas import EndpointMeta

logger = logging.getLogger(__name__)


def _get_language(endpoint: EndpointMeta) -> str:
    """获取接口来源语言（v2.4 多语言自适应提示词）；dispatcher 未标记时返回空串"""
    try:
        from parser.dispatcher import get_endpoint_language
        return get_endpoint_language(endpoint)
    except Exception:
        return ""

# 并发信号量
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_AI)
    return _semaphore


async def enhance_endpoint(endpoint: EndpointMeta, dto_context: str = "") -> EndpointMeta:
    """对单个接口进行 AI 增强

    Args:
        endpoint: 接口元数据
        dto_context: 相关 DTO 字段定义

    Returns:
        增强后的 EndpointMeta（原地修改并返回）
    """
    if not LLM_API_KEY:
        logger.warning("LLM_API_KEY 未配置，跳过 AI 增强")
        endpoint.description = _fallback_description(endpoint)
        return endpoint

    endpoint_dict = {
        "className": "",
        "baseUrl": "",
        "language": _get_language(endpoint),
        "method": endpoint.method.value,
        "path": endpoint.path,
        "fullPath": endpoint.fullPath,
        "javaMethod": endpoint.javaMethod,
        "params": [p.model_dump() for p in endpoint.params],
        "returnType": endpoint.returnType or "",
        "comment": endpoint.comment or "",
        "sourceCode": endpoint.sourceCode or "",
    }

    user_prompt = build_user_prompt(endpoint_dict, dto_context)

    async with _get_semaphore():
        try:
            result = await _call_llm(user_prompt)
            _merge_enhancement(endpoint, result)
            logger.info(f"AI 增强成功: {endpoint.javaMethod}")
        except Exception as e:
            logger.warning(f"AI 增强失败 ({endpoint.javaMethod}): {e}")
            endpoint.description = _fallback_description(endpoint)

    return endpoint


async def enhance_all(endpoints: list[EndpointMeta], dto_context: str = "") -> list[EndpointMeta]:
    """并发增强所有接口

    Args:
        endpoints: 接口列表
        dto_context: 相关 DTO 字段定义

    Returns:
        增强后的接口列表
    """
    tasks = [enhance_endpoint(ep, dto_context) for ep in endpoints]
    await asyncio.gather(*tasks, return_exceptions=True)
    return endpoints


async def _call_llm(user_prompt: str) -> dict:
    """调用大模型 API

    Returns:
        解析后的 JSON dict
    """
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": LLM_TEMPERATURE,
    }

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(LLM_API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

    # 解析返回的 JSON（可能被包在 ```json ... ``` 里）
    return _parse_llm_response(content)


def _parse_llm_response(content: str) -> dict:
    """解析大模型返回的 JSON，容错处理"""
    # 尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 中的内容
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { ... } 块
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法解析大模型返回的 JSON: {content[:200]}")


def _merge_enhancement(endpoint: EndpointMeta, enhancement: dict):
    """将 AI 增强结果合并到 EndpointMeta"""
    if "description" in enhancement:
        endpoint.description = enhancement["description"]
    if "requestExample" in enhancement:
        endpoint.requestExample = enhancement["requestExample"]
    if "responseExample" in enhancement:
        endpoint.responseExample = enhancement["responseExample"]
    if "edgeCases" in enhancement and isinstance(enhancement["edgeCases"], list):
        endpoint.edgeCases = enhancement["edgeCases"]
    if "errorCodes" in enhancement and isinstance(enhancement["errorCodes"], list):
        endpoint.errorCodes = enhancement["errorCodes"]
    # 合并参数增强
    if "params" in enhancement and isinstance(enhancement["params"], list):
        ai_params = {p["name"]: p for p in enhancement["params"] if "name" in p}
        for param in endpoint.params:
            if param.name in ai_params:
                ai_p = ai_params[param.name]
                if "description" in ai_p:
                    param.description = ai_p["description"]
                if "example" in ai_p:
                    param.example = str(ai_p["example"])
                if "required" in ai_p:
                    param.required = ai_p["required"]


def _fallback_description(endpoint: EndpointMeta) -> str:
    """AI 不可用时的降级描述"""
    method = endpoint.method.value
    path = endpoint.fullPath
    return f"{method} {path} - {endpoint.javaMethod}（AI增强不可用，纯解析结果）"
