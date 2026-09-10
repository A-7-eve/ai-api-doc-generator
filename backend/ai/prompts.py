"""AI 增强层 Prompt 模板（v2.4 通用化：适配 Java/Python/C 多语言）"""

SYSTEM_PROMPT = """你是一个接口文档专家。根据提供的接口代码和元数据（可能是 Java/SpringBoot、Python/FastAPI/Flask 或 C 语言），生成接口文档所需的信息。
请严格按照 JSON 格式返回，不要包含任何其他文本。"""


def build_user_prompt(endpoint_meta: dict, dto_context: str = "") -> str:
    """组装用户提示

    Args:
        endpoint_meta: 接口元数据 dict
        dto_context: 相关 DTO 类的字段定义（如有）

    Returns:
        完整的用户提示字符串
    """
    # 语言自适应说明（v2.4：根据源码特征提示 AI 正确理解上下文）
    lang = endpoint_meta.get("language", "")
    lang_hint = {
        "java": "这是一个 Java/SpringBoot Web 接口。",
        "python": "这是一个 Python Web 框架接口（FastAPI 或 Flask 装饰器路由）。",
        "c": "这是一个 C 语言的库函数（非 HTTP 接口，按函数说明文档的写法描述）。",
    }.get(lang, "这是一个 Web 接口。")

    prompt = f"""以下是接口信息，请生成接口文档增强数据。

{lang_hint}

接口类: {endpoint_meta.get('className', '')}
基础路径: {endpoint_meta.get('baseUrl', '')}
HTTP方法: {endpoint_meta.get('method', '')}
接口路径: {endpoint_meta.get('path', '')}
完整路径: {endpoint_meta.get('fullPath', '')}
方法名: {endpoint_meta.get('javaMethod', '')}
参数列表: {endpoint_meta.get('params', [])}
返回类型: {endpoint_meta.get('returnType', '')}
代码注释: {endpoint_meta.get('comment', '')}
"""

    if dto_context:
        prompt += f"\n相关DTO定义:\n{dto_context}\n"

    prompt += f"""
源码片段:
```
{endpoint_meta.get('sourceCode', '')}
```

请返回以下 JSON 格式（不要包含 markdown 代码块标记）:
{{
  "description": "用一句话描述这个接口的作用",
  "params": [
    {{
      "name": "参数名",
      "description": "参数含义说明",
      "required": true,
      "type": "参数类型",
      "example": "示例值"
    }}
  ],
  "requestExample": "请求体JSON示例",
  "responseExample": "响应体JSON示例",
  "edgeCases": ["边界场景1", "边界场景2"],
  "errorCodes": [
    {{"code": "400", "description": "参数校验失败"}}
  ]
}}"""

    return prompt
