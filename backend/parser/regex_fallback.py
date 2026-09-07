"""正则兜底解析：当 javalang AST 解析失败时，用正则提取基本信息。

适用场景：
- Java 代码包含 javalang 不支持的语法（如 record、sealed class、文本块等）
- 代码有语法错误但基本注解结构完整
"""

import re
import logging
from typing import Optional
from models.schemas import (
    ControllerMeta, EndpointMeta, ParamMeta, DtoMeta, DtoFieldMeta, HTTPMethod,
)

logger = logging.getLogger(__name__)

# ── 正则模式 ──

# 匹配 @Controller / @RestController 标注的类（注解和 class 之间可能有其他注解）
CONTROLLER_PATTERN = re.compile(
    r'@(?:Rest)?Controller\b'
    r'[\s\S]*?'
    r'(?:public\s+)?class\s+(\w+)',
    re.MULTILINE,
)

# 匹配类级 @RequestMapping
CLASS_REQUEST_MAPPING_PATTERN = re.compile(
    r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?"([^"]*)"',
    re.MULTILINE,
)

# 匹配方法级映射注解
MAPPING_PATTERN = re.compile(
    r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)'
    r'\s*(?:\(\s*(?:value\s*=\s*)?"([^"]*)"\s*\))?',
    re.MULTILINE,
)

# 匹配方法签名
METHOD_SIGNATURE_PATTERN = re.compile(
    r'(?:public\s+)([\w<>,\s\[\]]+)\s+(\w+)\s*\(([^)]*)\)',
    re.MULTILINE,
)

# 匹配 @RequestMapping 的 method 属性
REQUEST_MAPPING_METHOD_PATTERN = re.compile(
    r'method\s*=\s*RequestMethod\.(\w+)',
)

# 匹配参数注解
PARAM_ANNOTATION_PATTERN = re.compile(
    r'@(RequestParam|PathVariable|RequestBody)\s*(?:\(([^)]*)\))?\s*(.+)',
)

# DTO 字段
DTO_FIELD_PATTERN = re.compile(
    r'(?:public\s+)?(?:static\s+)?(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\s*[;=]',
    re.MULTILINE,
)

# DTO 类检测（有 @Entity / 无 Controller 注解但有字段）
DTO_CLASS_PATTERN = re.compile(
    r'class\s+(\w+)\s*(?:extends\s+\w+\s*)?(?:implements\s+[\w,\s]+\s*)?\{',
    re.MULTILINE,
)

ANNOTATION_METHOD_MAP = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
    "RequestMapping": None,  # 需看 method 属性
}


def regex_parse_file(source: str) -> tuple[list[ControllerMeta], list[DtoMeta]]:
    """用正则从源码中提取 Controller 和 DTO

    Args:
        source: Java 源码字符串

    Returns:
        (controllers, dtos)
    """
    controllers: list[ControllerMeta] = []
    dtos: list[DtoMeta] = []

    # 检测是否包含 Controller
    ctrl_match = CONTROLLER_PATTERN.search(source)
    if ctrl_match:
        ctrl = _regex_parse_controller(source, ctrl_match)
        if ctrl:
            controllers.append(ctrl)
            return controllers, dtos

    # 非 Controller → 尝试作为 DTO 解析
    dto = _regex_parse_dto(source)
    if dto:
        dtos.append(dto)

    return controllers, dtos


def _regex_parse_controller(
    source: str, ctrl_match: re.Match,
) -> Optional[ControllerMeta]:
    """用正则提取 Controller 基本信息"""
    class_name = ctrl_match.group(1)

    # 提取 baseUrl
    base_url = ""
    rm_match = CLASS_REQUEST_MAPPING_PATTERN.search(source)
    if rm_match:
        base_url = rm_match.group(1)

    # 找到类体（第一个 { 之后）
    class_body_start = source.find("{", ctrl_match.end())
    if class_body_start == -1:
        class_body_start = ctrl_match.end()
    class_body = source[class_body_start:]

    endpoints: list[EndpointMeta] = []

    for m in MAPPING_PATTERN.finditer(class_body):
        ann_name = m.group(1)
        path = m.group(2) or ""

        # 确定 HTTP 方法
        if ann_name == "RequestMapping":
            # 方法级 @RequestMapping，检查 method 属性
            method_str = "GET"  # 默认
            rm_method = REQUEST_MAPPING_METHOD_PATTERN.search(m.group(0))
            if rm_method:
                method_str = rm_method.group(1).upper()
            http_method = method_str
        else:
            http_method = ANNOTATION_METHOD_MAP.get(ann_name, "GET")

        # 提取方法名和参数
        search_start = m.end()
        method_match = METHOD_SIGNATURE_PATTERN.search(class_body[search_start:search_start + 500])
        java_method = ""
        params: list[ParamMeta] = []
        return_type = ""

        if method_match:
            return_type = method_match.group(1).strip()
            java_method = method_match.group(2)
            param_str = method_match.group(3)
            params = _extract_params(param_str)

        # 组装 fullPath
        full_path = (base_url + "/" + path).replace("//", "/")
        if not full_path.startswith("/"):
            full_path = "/" + full_path

        endpoints.append(EndpointMeta(
            method=HTTPMethod(http_method),
            path="/" + path if path and not path.startswith("/") else path,
            fullPath=full_path,
            javaMethod=java_method or "unknown",
            returnType=return_type or None,
            comment=None,
            sourceCode=None,
            params=params,
        ))

    if not endpoints:
        return None

    logger.info(f"正则兜底解析 Controller: {class_name} ({len(endpoints)} 接口)")

    return ControllerMeta(
        className=class_name,
        baseUrl=base_url,
        packageName=None,
        comment=None,
        endpoints=endpoints,
    )


def _extract_params(param_str: str) -> list[ParamMeta]:
    """从参数字符串中提取参数列表"""
    params: list[ParamMeta] = []
    if not param_str.strip():
        return params

    # 按逗号分割（简单策略，不处理嵌套泛型中的逗号）
    raw_params = _split_params(param_str)

    for raw in raw_params:
        raw = raw.strip()
        if not raw:
            continue

        # 提取注解
        ann_match = PARAM_ANNOTATION_PATTERN.match(raw)
        annotation = None
        required = True
        type_and_name = raw

        if ann_match:
            annotation = f"@{ann_match.group(1)}"
            ann_args = ann_match.group(2)
            if ann_args and "required" in ann_args:
                required = "required=false" not in ann_args.replace(" ", "")
            type_and_name = ann_match.group(3)

        # 跳过框架参数
        skip_types = {"BindingResult", "Model", "Map", "HttpServletRequest",
                       "HttpServletResponse", "Principal", "Locale",
                       "RedirectAttributes", "SessionStatus"}
        if any(skip in type_and_name for skip in skip_types):
            continue

        # 提取类型和参数名
        parts = type_and_name.strip().split()
        if len(parts) >= 2:
            param_type = parts[-2]
            param_name = parts[-1]
            # 处理泛型中的 <>
            if "<" in param_type:
                # 可能是 List<Owner> owner → 类型在前
                param_type = " ".join(parts[:-1])
                param_name = parts[-1]

            params.append(ParamMeta(
                name=param_name,
                type=param_type,
                annotation=annotation,
                required=required,
            ))

    return params


def _split_params(param_str: str) -> list[str]:
    """智能分割参数字符串（处理泛型中的逗号）"""
    params: list[str] = []
    depth = 0
    current = []

    for char in param_str:
        if char == "<":
            depth += 1
            current.append(char)
        elif char == ">":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            params.append("".join(current))
            current = []
        else:
            current.append(char)

    if current:
        params.append("".join(current))

    return params


def _regex_parse_dto(source: str) -> Optional[DtoMeta]:
    """用正则提取 DTO 类字段"""
    # 找 class 声明
    class_match = DTO_CLASS_PATTERN.search(source)
    if not class_match:
        return None

    class_name = class_match.group(1)

    # 提取类体
    class_body_start = source.find("{", class_match.end())
    if class_body_start == -1:
        return None
    class_body = source[class_body_start:]

    fields: list[DtoFieldMeta] = []

    for m in DTO_FIELD_PATTERN.finditer(class_body):
        field_type = m.group(1).strip()
        field_name = m.group(2).strip()

        # 跳过方法返回类型误匹配
        if field_name in ("return", "if", "for", "while", "switch"):
            continue

        # 提取字段上的注解
        line_start = class_body.rfind("\n", 0, m.start()) + 1
        line_prefix = class_body[line_start:m.start()].strip()
        annotations = re.findall(r'@(\w+)', line_prefix)

        fields.append(DtoFieldMeta(
            name=field_name,
            type=field_type,
            annotations=annotations,
        ))

    if not fields:
        return None

    logger.info(f"正则兜底解析 DTO: {class_name} ({len(fields)} 字段)")

    return DtoMeta(className=class_name, fields=fields)
