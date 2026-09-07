"""Markdown 文档生成器"""

from models.schemas import ProjectMeta


def generate_markdown(project: ProjectMeta) -> str:
    """生成 Markdown 格式的接口文档

    Args:
        project: 项目元数据

    Returns:
        Markdown 字符串
    """
    lines = []
    lines.append(f"# {project.projectName} 接口文档\n")
    lines.append(f"> 由 AI 辅助接口文档自动生成系统生成\n\n")
    lines.append("---\n\n")

    ep_index = 0

    for controller in project.controllers:
        lines.append(f"## {controller.className}\n")
        if controller.comment:
            lines.append(f"{controller.comment}\n")
        lines.append("\n")

        for ep in controller.endpoints:
            ep_index += 1
            lines.append(f"### {ep_index}. {ep.description or ep.javaMethod}\n")
            lines.append(
                f"- **接口路径**: `{ep.method.value} {ep.fullPath}`\n"
            )
            lines.append(f"- **方法名**: `{ep.javaMethod}`\n")
            if ep.returnType:
                lines.append(f"- **返回类型**: `{ep.returnType}`\n")
            lines.append("\n")

            # 请求参数表
            if ep.params:
                lines.append("**请求参数**:\n\n")
                lines.append("| 参数名 | 类型 | 位置 | 必填 | 说明 | 示例 |\n")
                lines.append("|--------|------|------|------|------|------|\n")
                for p in ep.params:
                    location = {
                        "@PathVariable": "path",
                        "@RequestParam": "query",
                        "@RequestBody": "body",
                    }.get(p.annotation, "-")
                    req = "是" if p.required else "否"
                    desc = p.description or "-"
                    example = p.example or "-"
                    lines.append(
                        f"| {p.name} | {p.type} | {location} | {req} | {desc} | {example} |\n"
                    )
                lines.append("\n")

            # 请求示例
            if ep.requestExample:
                lines.append("**请求示例**:\n```json\n")
                lines.append(ep.requestExample)
                lines.append("\n```\n\n")

            # 响应示例
            if ep.responseExample:
                lines.append("**响应示例**:\n```json\n")
                lines.append(ep.responseExample)
                lines.append("\n```\n\n")

            # 边界场景
            if ep.edgeCases:
                lines.append("**边界场景**:\n")
                for case in ep.edgeCases:
                    lines.append(f"- {case}\n")
                lines.append("\n")

            # 错误码
            if ep.errorCodes:
                lines.append("**错误码**:\n\n")
                lines.append("| 码 | 说明 |\n")
                lines.append("|----|------|\n")
                for err in ep.errorCodes:
                    code = err.get("code", "")
                    desc = err.get("description", "")
                    lines.append(f"| {code} | {desc} |\n")
                lines.append("\n")

            lines.append("---\n\n")

    return "".join(lines)
