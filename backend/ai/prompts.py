"""AI 增强层 Prompt 模板"""

SYSTEM_PROMPT = """你是一个接口文档专家。根据提供的 Java 接口代码和元数据，生成接口文档所需的信息。
请严格按照 JSON 格式返回，不要包含任何其他文本。"""


def build_user_prompt(endpoint_meta: dict, dto_context: str = "") -> str:
    """组装用户提示

    Args:
        endpoint_meta: 接口元数据 dict
        dto_context: 相关 DTO 类的字段定义（如有）

    Returns:
        完整的用户提示字符串
    """
    prompt = f"""以下是 SpringBoot 接口信息，请生成接口文档增强数据。

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
```java
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
