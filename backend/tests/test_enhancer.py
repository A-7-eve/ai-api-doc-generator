"""AI 增强层单元测试

覆盖：
1. 降级逻辑：无 API Key 时应使用 fallback 描述
2. LLM 响应解析：正常 JSON / ```json 包裹 / 带多余文本
3. 增强结果合并：字段正确合并到 EndpointMeta
4. 并发增强：多接口并发不出错
"""

import pytest
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.enhancer import (
    enhance_endpoint,
    enhance_all,
    _parse_llm_response,
    _merge_enhancement,
    _fallback_description,
)
from models.schemas import EndpointMeta, ParamMeta, HTTPMethod


def _make_endpoint() -> EndpointMeta:
    return EndpointMeta(
        endpointId="ep-test",
        method=HTTPMethod.GET,
        path="/users/{id}",
        fullPath="/api/users/{id}",
        javaMethod="getUser",
        returnType="User",
        params=[
            ParamMeta(name="id", type="Long", annotation="@PathVariable", required=True),
        ],
    )


class TestFallbackDescription:

    def test_fallback_contains_method_and_path(self):
        ep = _make_endpoint()
        desc = _fallback_description(ep)
        assert "GET" in desc
        assert "/api/users/{id}" in desc
        assert "getUser" in desc

    def test_fallback_mentions_unavailable(self):
        ep = _make_endpoint()
        desc = _fallback_description(ep)
        assert "AI增强不可用" in desc or "纯解析" in desc


class TestEnhanceNoApiKey:

    def test_enhance_without_api_key(self, monkeypatch):
        """无 API Key 时应降级为 fallback 描述"""
        monkeypatch.setattr("ai.enhancer.LLM_API_KEY", "")

        ep = _make_endpoint()
        result = asyncio.run(enhance_endpoint(ep))

        assert result.description is not None
        assert "AI增强不可用" in result.description or "纯解析" in result.description

    def test_enhance_all_without_api_key(self, monkeypatch):
        """无 API Key 时并发增强应全部降级"""
        monkeypatch.setattr("ai.enhancer.LLM_API_KEY", "")

        eps = [_make_endpoint() for _ in range(3)]
        results = asyncio.run(enhance_all(eps))

        for ep in results:
            assert ep.description is not None
            assert "AI增强不可用" in ep.description or "纯解析" in ep.description


class TestParseLlmResponse:

    def test_parse_plain_json(self):
        """直接 JSON 字符串"""
        resp = '{"description": "获取用户信息"}'
        result = _parse_llm_response(resp)
        assert result["description"] == "获取用户信息"

    def test_parse_markdown_wrapped_json(self):
        """被 ```json 包裹的 JSON"""
        resp = '```json\n{"description": "获取用户信息"}\n```'
        result = _parse_llm_response(resp)
        assert result["description"] == "获取用户信息"

    def test_parse_code_block_without_lang(self):
        """被 ``` 包裹但没有指定语言"""
        resp = '```\n{"description": "获取用户信息"}\n```'
        result = _parse_llm_response(resp)
        assert result["description"] == "获取用户信息"

    def test_parse_json_with_prefix_text(self):
        """JSON 前有多余文本，应提取 JSON 块"""
        resp = '好的，这是结果：\n{"description": "获取用户信息"}'
        result = _parse_llm_response(resp)
        assert result["description"] == "获取用户信息"

    def test_parse_invalid_json_raises(self):
        """完全无法解析时应抛出 ValueError"""
        resp = "这不是 JSON"
        with pytest.raises(ValueError):
            _parse_llm_response(resp)


class TestMergeEnhancement:

    def test_merge_description(self):
        ep = _make_endpoint()
        enhancement = {"description": "根据ID获取用户详情"}
        _merge_enhancement(ep, enhancement)
        assert ep.description == "根据ID获取用户详情"

    def test_merge_params(self):
        ep = _make_endpoint()
        enhancement = {
            "params": [
                {"name": "id", "description": "用户唯一标识", "example": "12345", "required": True}
            ]
        }
        _merge_enhancement(ep, enhancement)
        assert ep.params[0].description == "用户唯一标识"
        assert ep.params[0].example == "12345"

    def test_merge_edge_cases(self):
        ep = _make_endpoint()
        enhancement = {"edgeCases": ["用户不存在", "ID格式错误"]}
        _merge_enhancement(ep, enhancement)
        assert len(ep.edgeCases) == 2
        assert "用户不存在" in ep.edgeCases

    def test_merge_error_codes(self):
        ep = _make_endpoint()
        enhancement = {"errorCodes": [{"code": "404", "description": "用户不存在"}]}
        _merge_enhancement(ep, enhancement)
        assert len(ep.errorCodes) == 1
        assert ep.errorCodes[0]["code"] == "404"

    def test_merge_request_response_examples(self):
        ep = _make_endpoint()
        enhancement = {
            "requestExample": '{"id": 1}',
            "responseExample": '{"name": "张三"}',
        }
        _merge_enhancement(ep, enhancement)
        assert ep.requestExample == '{"id": 1}'
        assert ep.responseExample == '{"name": "张三"}'
