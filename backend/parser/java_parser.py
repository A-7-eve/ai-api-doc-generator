"""Java 代码解析模块：用 javalang AST 解析 SpringBoot Controller，提取接口元数据。

解析策略：
1. 优先使用 javalang AST 精确解析（能获取完整类型、参数、注释信息）
2. AST 解析失败时自动降级为正则兜底（提取基本结构，信息可能不完整）
"""

import os
import re
import logging
import javalang
from typing import Optional

from models.schemas import (
    ProjectMeta, ControllerMeta, EndpointMeta, ParamMeta,
    DtoMeta, DtoFieldMeta, HTTPMethod,
)
from parser.regex_fallback import regex_parse_file

logger = logging.getLogger(__name__)

# Spring MVC 映射注解 → HTTP 方法
MAPPING_ANNOTATIONS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
    "RequestMapping": None,  # 需看 method 属性
}


def parse_project(project_path: str) -> ProjectMeta:
    """解析整个 Java/SpringBoot 项目

    Args:
        project_path: 项目根目录路径  

    Returns:
        ProjectMeta: 项目元数据
    """   
    project_name = os.path.basename(os.path.normpath(project_path))
    controllers: list[ControllerMeta] = []
    dtos: list[DtoMeta] = []

    # 遍历所有 .java 文件
    for root, _dirs, files in os.walk(project_path):
        # 跳过 test 目录（检查路径中是否包含 test 目录段）
        parts = os.path.normpath(root).split(os.sep)
        if "test" in parts:
            continue
        for fname in files:
            if not fname.endswith(".java"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()

            # 尝试 javalang AST 解析
            try:
                tree = javalang.parse.parse(source)
            except Exception as e:
                # AST 解析失败，降级为正则兜底
                logger.warning(f"AST 解析失败，降级正则兜底: {fname} ({e})")
                fb_controllers, fb_dtos = regex_parse_file(source)
                controllers.extend(fb_controllers)
                dtos.extend(fb_dtos)
                continue

            package_name = tree.package.name if tree.package else None

            for _, class_decl in tree.filter(javalang.tree.ClassDeclaration):
                annotations = [a.name for a in (class_decl.annotations or [])]
                is_controller = any(
                    name in annotations
                    for name in ("RestController", "Controller")
                )

                if is_controller:
                    ctrl = _parse_controller(class_decl, source, package_name)
                    if ctrl:
                        controllers.append(ctrl)
                else:
                    # 尝试作为 DTO 解析
                    dto = _parse_dto(class_decl)
                    if dto:
                        dtos.append(dto)

    return ProjectMeta(
        projectName=project_name,
        controllers=controllers,
        dtos=dtos,
    )


def _parse_controller(
    class_decl: javalang.tree.ClassDeclaration,
    source: str,
    package_name: Optional[str],
) -> Optional[ControllerMeta]:
    """解析单个 Controller 类"""
    class_name = class_decl.name
    base_url = _extract_base_url(class_decl)
    class_comment = _extract_class_comment(class_decl, source)

    endpoints: list[EndpointMeta] = []

    for method in class_decl.methods:
        ep = _parse_method(method, base_url, class_name, source)
        if ep:
            endpoints.append(ep)

    if not endpoints:
        return None

    return ControllerMeta(
        className=class_name,
        baseUrl=base_url,
        packageName=package_name,
        comment=class_comment,
        endpoints=endpoints,
    )


def _extract_base_url(class_decl: javalang.tree.ClassDeclaration) -> str:
    """提取类级 @RequestMapping 的 baseUrl"""
    for ann in (class_decl.annotations or []):
        if ann.name == "RequestMapping":
            return _extract_path_from_annotation(ann)
    return ""  # 无类级 @RequestMapping（如 petclinic），返回空


def _extract_path_from_annotation(ann) -> str:
    """从注解中提取 path/value 属性"""
    # 无属性，只有值: @GetMapping("/owners")
    if not ann.element:
        return ""
    # 字符串字面量: @GetMapping("/owners")
    if isinstance(ann.element, javalang.tree.Literal):
        return _clean_path(ann.element.value)
    # ElementArrayValue: @GetMapping({"/vets.json", "/vets.xml"})
    if isinstance(ann.element, javalang.tree.ElementArrayValue):
        # ElementArrayValue 的 values 是一个 list
        values = ann.element.values
        if values and len(values) > 0:
            first = values[0]
            if isinstance(first, javalang.tree.Literal):
                return _clean_path(first.value)
        return ""
    if isinstance(ann.element, list):
        # ElementPairs: @RequestMapping(value = "/api", method = RequestMethod.GET)
        for elem in ann.element:
            if isinstance(elem, javalang.tree.ElementValuePair):
                if elem.name in ("value", "path"):
                    val = elem.value
                    if isinstance(val, javalang.tree.Literal):
                        return _clean_path(val.value)
                    if isinstance(val, javalang.tree.ElementArrayValue):
                        values = val.values
                        if values and len(values) > 0:
                            first = values[0]
                            if isinstance(first, javalang.tree.Literal):
                                return _clean_path(first.value)
        # ElementArrayValue 列表（无属性名）
        for elem in ann.element:
            if isinstance(elem, javalang.tree.ElementArrayValue):
                values = elem.values
                if values and len(values) > 0:
                    first = values[0]
                    if isinstance(first, javalang.tree.Literal):
                        return _clean_path(first.value)
    return ""


def _parse_method(
    method: javalang.tree.MethodDeclaration,
    base_url: str,
    class_name: str,
    source: str,
) -> Optional[EndpointMeta]:
    """解析单个方法，提取接口信息"""
    http_method: Optional[str] = None
    path: str = ""

    for ann in (method.annotations or []):
        ann_name = ann.name
        if ann_name in MAPPING_ANNOTATIONS:
            mapped = MAPPING_ANNOTATIONS[ann_name]
            if mapped:
                # @GetMapping / @PostMapping 等
                http_method = mapped
                path = _extract_path_from_annotation(ann)
            elif ann_name == "RequestMapping":
                # @RequestMapping 需看 method 属性
                http_method, path = _parse_request_mapping(ann)
            break  # 只取第一个映射注解

    if not http_method:
        return None  # 不是接口方法

    full_path = (base_url + path).replace("//", "/") or "/"
    if not full_path.startswith("/"):
        full_path = "/" + full_path

    # 提取参数
    params = _extract_params(method)

    # 提取返回类型
    return_type = _extract_return_type(method)

    # 提取注释
    comment = _extract_method_comment(method, source)

    # 提取源码片段
    source_code = _extract_method_source(method, source)

    return EndpointMeta(
        method=HTTPMethod(http_method),
        path=path,
        fullPath=full_path,
        javaMethod=method.name,
        returnType=return_type,
        comment=comment,
        sourceCode=source_code,
        params=params,
    )


def _parse_request_mapping(ann) -> tuple[Optional[str], str]:
    """解析 @RequestMapping 注解，返回 (http_method, path)"""
    path = ""
    method_str = "GET"  # 默认

    if not ann.element:
        return method_str, path

    if isinstance(ann.element, javalang.tree.Literal):
        path = _clean_path(ann.element.value)
        return method_str, path

    if isinstance(ann.element, javalang.tree.ElementArrayValue):
        values = ann.element.values
        if values and len(values) > 0:
            first = values[0]
            if isinstance(first, javalang.tree.Literal):
                path = _clean_path(first.value)
        return method_str, path

    if isinstance(ann.element, list):
        for elem in ann.element:
            if isinstance(elem, javalang.tree.ElementValuePair):
                if elem.name in ("value", "path"):
                    val = elem.value
                    if isinstance(val, javalang.tree.Literal):
                        path = _clean_path(val.value)
                    elif isinstance(val, javalang.tree.ElementArrayValue):
                        values = val.values
                        if values and len(values) > 0:
                            first = values[0]
                            if isinstance(first, javalang.tree.Literal):
                                path = _clean_path(first.value)
                elif elem.name == "method":
                    # method = RequestMethod.GET
                    val = elem.value
                    if isinstance(val, javalang.tree.MemberReference):
                        method_str = val.member.upper()
                    elif isinstance(val, javalang.tree.Literal):
                        method_str = _clean_literal(val.value).upper()

    return method_str, path


def _extract_params(method: javalang.tree.MethodDeclaration) -> list[ParamMeta]:
    """提取方法参数列表"""
    params: list[ParamMeta] = []
    if not method.parameters:
        return params

    for param in method.parameters:
        param_name = param.name
        param_type = _type_to_str(param.type)

        annotation = None
        required = True

        for ann in (param.annotations or []):
            ann_name = ann.name
            if ann_name == "RequestParam":
                annotation = "@RequestParam"
                # 检查 required 属性
                if ann.element and isinstance(ann.element, list):
                    for elem in ann.element:
                        if (
                            isinstance(elem, javalang.tree.ElementValuePair)
                            and elem.name == "required"
                        ):
                            if isinstance(elem.value, javalang.tree.Literal):
                                required = elem.value.value != "false"
            elif ann_name == "PathVariable":
                annotation = "@PathVariable"
            elif ann_name == "RequestBody":
                annotation = "@RequestBody"

        # 跳过 BindingResult、Model、Map 等框架参数
        skip_types = {"BindingResult", "Model", "Map", "HttpServletRequest",
                       "HttpServletResponse", "Principal", "Locale"}
        if any(skip in param_type for skip in skip_types):
            continue

        params.append(ParamMeta(
            name=param_name,
            type=param_type,
            annotation=annotation,
            required=required,
        ))

    return params


def _extract_return_type(method: javalang.tree.MethodDeclaration) -> Optional[str]:
    """提取方法返回类型"""
    if not method.return_type:
        return None
    return _type_to_str(method.return_type)


def _type_to_str(type_node) -> str:
    """将类型节点转为字符串"""
    if isinstance(type_node, str):
        return type_node
    if isinstance(type_node, javalang.tree.BasicType):
        result = type_node.name
        if type_node.dimensions:
            result += "[]" * len(type_node.dimensions)
        return result
    if isinstance(type_node, javalang.tree.ReferenceType):
        # 处理泛型: List<Owner> → List<Owner>
        result = type_node.name
        if type_node.arguments:
            arg_strs = []
            for arg in type_node.arguments:
                if isinstance(arg, javalang.tree.TypeArgument):
                    if arg.type:
                        arg_strs.append(_type_to_str(arg.type))
                    else:
                        arg_strs.append("?")
            result += "<" + ", ".join(arg_strs) + ">"
        return result
    return str(type_node)


def _clean_path(value: str) -> str:
    """清理路径字符串：去掉引号"""
    return value.strip().strip('"').strip("'")


def _clean_literal(value: str) -> str:
    """清理字面量：去掉引号"""
    return value.strip().strip('"').strip("'")


def _parse_dto(class_decl: javalang.tree.ClassDeclaration) -> Optional[DtoMeta]:
    """解析 DTO/Entity 类，提取字段"""
    fields: list[DtoFieldMeta] = []
    for member in class_decl.body:
        if isinstance(member, javalang.tree.FieldDeclaration):
            for var in member.declarators:
                field_name = var.name
                field_type = _type_to_str(member.type)
                field_annotations = [a.name for a in (member.annotations or [])]
                fields.append(DtoFieldMeta(
                    name=field_name,
                    type=field_type,
                    annotations=field_annotations,
                ))
    if not fields:
        return None
    return DtoMeta(className=class_decl.name, fields=fields)


def _extract_class_comment(class_decl, source: str) -> Optional[str]:
    """提取类上方的 Javadoc 注释"""
    return _extract_comment_before(class_decl, source)


def _extract_method_comment(method, source: str) -> Optional[str]:
    """提取方法的 Javadoc 注释"""
    return _extract_comment_before(method, source)


def _extract_comment_before(node, source: str) -> Optional[str]:
    """提取节点上方的注释"""
    if not hasattr(node, "position") or node.position is None:
        return None
    line = node.position.line
    lines = source.split("\n")
    # 从前一行往上找注释
    for i in range(line - 2, max(line - 10, -1), -1):
        if i < 0 or i >= len(lines):
            break
        stripped = lines[i].strip()
        if stripped.endswith("*/"):
            # 找到注释结束，往上找注释开始
            comment_lines = []
            for j in range(i, max(i - 10, -1), -1):
                if j < 0:
                    break
                line_text = lines[j].strip()
                comment_lines.insert(0, line_text)
                if line_text.startswith("/*"):
                    break
            return "\n".join(comment_lines)
        if stripped and not stripped.startswith("//") and not stripped.startswith("*"):
            break
    return None


def _extract_method_source(method, source: str) -> str:
    """提取方法的源码片段"""
    if not hasattr(method, "position") or method.position is None:
        return ""
    start_line = method.position.line
    lines = source.split("\n")
    # 找方法结束（简单策略：找下一个 } 同级）
    brace_count = 0
    end_line = start_line
    for i in range(start_line - 1, len(lines)):
        brace_count += lines[i].count("{") - lines[i].count("}")
        end_line = i + 1
        if brace_count == 0 and i > start_line - 1:
            break
    return "\n".join(lines[start_line - 1:end_line])
