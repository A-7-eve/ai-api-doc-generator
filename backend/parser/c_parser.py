"""C 代码解析模块：正则提取 C 函数签名，生成"函数清单"式接口元数据。

定位说明（与 Java/Python HTTP 路由不同）：
- C 语言没有路由注解/装饰器体系，无法直接映射 HTTP 语义
- 本引擎的定位是"API 函数清单"：把导出函数（非 static）作为可调用接口列出
- 生成的条目：method 统一为 POST，path 为函数名，参数照常提取
- 因此 C 项目导出 Markdown 完整可用；OpenAPI 的 paths 会为空（文档已注明）

语法版本（任务2 版本管理）：
- 正则引擎兼容 ANSI C (C89) 与 C99/C11 的函数定义风格
  * 经典风格:  int add(int a, int b) { ... }
  * K&R 风格:  int add(a, b) int a; int b; { ... }（不完整支持，参数按无类型处理）
  * 指针返回:  char* concat(const char* s1, const char* s2)
  * 函数指针参数等复杂签名按"提取失败即跳过"处理，不报错
"""

import os
import re
import logging
from typing import Optional

from models.schemas import ProjectMeta, ControllerMeta, EndpointMeta, ParamMeta, HTTPMethod

logger = logging.getLogger(__name__)

# 引擎信息（供 engine_registry 汇总）
ENGINE_NAME = "c-regex"
ENGINE_VERSION = "1.0"

# C 关键字（函数名不能是关键字）
_C_KEYWORDS = {
    "if", "else", "for", "while", "do", "switch", "case", "default",
    "return", "break", "continue", "goto", "sizeof", "typedef",
    "struct", "union", "enum", "static", "extern", "const", "volatile",
    "register", "auto", "inline", "restrict", "signed", "unsigned",
    "void", "char", "short", "int", "long", "float", "double",
}

# 函数定义正则：
#   [返回类型] 函数名(参数列表) { 或 ; 结尾（声明也收录，但优先定义）
# 返回类型允许: 标识符 + 指针/空格组合，如 "static int" "char*"
_FUNC_DEF_RE = re.compile(
    r"""^[ \t]*
    (?:(?:static|extern|inline|const|unsigned|signed|struct|enum|union)\s+)*
    (?:unsigned\s+|signed\s+)?                 # 可选符号修饰
    (?:(?:void|char|short|int|long|float|double)\s+|[\w]+[\s*]+)   # 返回类型
    (?P<ret>\**)\s*                            # 返回类型指针星号
    (?P<name>[A-Za-z_]\w*)\s*                  # 函数名
    \((?P<args>[^;()]*)\)\s*                   # 参数列表（不含嵌套括号）
    (?P<end>\{|;)                              # 定义 or 声明
    """,
    re.MULTILINE | re.VERBOSE,
)

# 参数切分后单个参数: "int x" "const char* s" "double" ...
# 完整捕获：[const/unsigned/struct 等修饰词] + 基础类型 + 指针星号 + 可选参数名
_PARAM_RE = re.compile(
    r"^\s*(?P<type>(?:(?:const|volatile|unsigned|signed|struct|union|enum)\s+)*"
    r"[\w]+(?:\s*\*+\s*|\s+)+)"
    r"(?P<name>[A-Za-z_]\w*)?\s*$"
)

# 跳过的目录（与 python_parser 保持一致）
_SKIP_DIRS = {"test", "tests", "venv", ".venv", "__pycache__", "build", "cmake-build-debug"}

# 文件级注释（文件开头注释块）提取
_FILE_COMMENT_RE = re.compile(r"/\*\*(.*?)\*/", re.DOTALL)


def parse_c_project(project_path: str) -> ProjectMeta:
    """解析整个 C 项目：每个 .c/.h 文件作为一个 Controller（函数清单）"""
    project_name = os.path.basename(os.path.normpath(project_path))
    controllers: list[ControllerMeta] = []

    for root, _dirs, files in os.walk(project_path):
        parts = os.path.normpath(root).split(os.sep)
        if any(seg in _SKIP_DIRS for seg in parts):
            continue
        for fname in files:
            if not (fname.endswith(".c") or fname.endswith(".h")):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    source = f.read()
            except OSError as e:
                logger.warning(f"读取 C 文件失败({fpath}): {e}")
                continue
            ctrl = parse_c_file(source, fname)
            if ctrl and ctrl.endpoints:
                controllers.append(ctrl)

    return ProjectMeta(projectName=project_name, controllers=controllers)


def parse_c_file(source: str, filename: str = "module.c") -> Optional[ControllerMeta]:
    """解析单个 C 文件，提取函数清单

    每个 .c/.h 文件视为一个"Controller"（className=文件名），
    文件内的非 static 函数视为对外可调用的接口函数。
    static 函数（内部实现）跳过。
    """
    endpoints: list[EndpointMeta] = []
    seen: set[str] = set()   # .c 定义与 .h 声明去重（同名取先出现者）

    # 预处理：去掉块注释内容和字符串字面量（避免注释里的函数原型被误匹配）
    cleaned = _strip_comments_and_strings(source)

    # 文件头注释作为 Controller 说明
    fm = _FILE_COMMENT_RE.search(source)
    file_comment = None
    if fm:
        first_line = fm.group(1).strip().split("\n")[0].strip().lstrip("* ")
        if first_line:
            file_comment = first_line

    for m in _FUNC_DEF_RE.finditer(cleaned):
        name = m.group("name")
        if name in _C_KEYWORDS or name in seen:
            continue
        # 跳过 static 函数（模块内部实现，非对外接口）
        seg = m.group(0)
        sig = seg.split("(")[0]
        if re.search(r"\bstatic\b", sig):
            continue

        ret_ptr = m.group("ret") or ""
        args_str = m.group("args").strip()
        params = _parse_c_params(args_str)
        is_declaration = m.group("end") == ";"

        seen.add(name)
        endpoints.append(_build_endpoint(
            name=name, ret_ptr=ret_ptr, m=m, cleaned=cleaned,
            params=params, is_declaration=is_declaration, raw=source,
        ))

    if not endpoints:
        return None

    return ControllerMeta(
        className=filename,
        baseUrl="",
        endpoints=endpoints,
        comment=file_comment or f"C 源文件 {filename}（函数清单）",
    )


def _parse_c_params(args_str: str) -> list[ParamMeta]:
    """解析 C 参数列表 "int a, char* s, double" → ParamMeta 列表"""
    if not args_str or args_str == "void" or args_str == "":
        return []
    params: list[ParamMeta] = []
    for chunk in args_str.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        pm = _PARAM_RE.match(chunk)
        if pm:
            ptype = pm.group("type").strip()
            pname = pm.group("name") or f"arg{len(params) + 1}"
            params.append(ParamMeta(
                name=pname,
                type=ptype,
                annotation="@RequestParam",   # C 无 HTTP 语义，统一 query 风格
                required=True,
            ))
        else:
            # 复杂签名（函数指针等）：整体当类型，参数名按序号
            params.append(ParamMeta(
                name=f"arg{len(params) + 1}",
                type=chunk,
                annotation="@RequestParam",
                required=True,
            ))
    return params


def _build_endpoint(name, ret_ptr, m, cleaned, params, is_declaration, raw) -> EndpointMeta:
    """构造函数条目对应的 EndpointMeta"""
    # 定位原始源码中的函数（cleaned 与 raw 行号一致，按字符偏移回溯）
    line_no = cleaned[:m.start()].count("\n") + 1
    source_lines = raw.split("\n")
    snippet = "\n".join(source_lines[line_no - 1: line_no + 14]) if line_no <= len(source_lines) else ""

    # 函数体上方注释（查找原始 source 中函数定义上一行的 // 或 /* */ 注释）
    comment = _find_leading_comment(source_lines, line_no)

    return EndpointMeta(
        method=HTTPMethod.POST,          # C 无 HTTP 语义，统一 POST
        path=f"/{name}",                 # 路径=函数名
        fullPath=f"/{name}",
        javaMethod=name,                 # 字段名沿用 javaMethod，实际是 C 函数名
        returnType=_return_type_str(m, ret_ptr),
        comment=comment or (f"函数声明（定义在其他编译单元）" if is_declaration else None),
        sourceCode=snippet,
        params=params,
    )


def _return_type_str(m, ret_ptr: str) -> str:
    """从匹配结果还原返回类型字符串（去掉函数名部分）"""
    seg = m.group(0).split("(")[0].strip()
    # 去掉修饰关键字前缀
    for kw in ("static ", "extern ", "inline "):
        while seg.startswith(kw):
            seg = seg[len(kw):]
    # 去掉末尾的函数名（最后一个标识符）
    seg = re.sub(r"[A-Za-z_]\w*\s*$", "", seg).strip()
    return seg


def _find_leading_comment(lines: list[str], line_no: int) -> Optional[str]:
    """向上查找函数定义行的注释（// 或单行 /* */，最多回看 3 行）"""
    for i in range(line_no - 2, max(-1, line_no - 5), -1):
        stripped = lines[i].strip() if 0 <= i < len(lines) else ""
        if not stripped:
            continue
        if stripped.startswith("//"):
            return stripped.lstrip("/ ").strip()
        if stripped.startswith("/*") and stripped.endswith("*/"):
            return stripped.strip("/* ").strip()
        if not stripped.startswith(("*", "/*", "//")):
            break
    return None


def _strip_comments_and_strings(source: str) -> str:
    """去掉块注释内容和字符串字面量（保持行结构不变，行号对齐）"""
    out: list[str] = []
    i, n = 0, len(source)
    in_block_comment = False
    in_string = False
    in_char = False

    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                out.append("  ")
                i += 2
                continue
            out.append("\n" if ch == "\n" else " ")
            i += 1
        elif in_string:
            if ch == "\\":
                out.append("  " if nxt else " ")
                i += 2
                continue
            if ch == '"':
                in_string = False
            out.append("\n" if ch == "\n" else " ")
            i += 1
        elif in_char:
            if ch == "\\":
                out.append("  " if nxt else " ")
                i += 2
                continue
            if ch == "'":
                in_char = False
            out.append(" ")
            i += 1
        else:
            if ch == "/" and nxt == "*":
                in_block_comment = True
                out.append("  ")
                i += 2
            elif ch == "/" and nxt == "/":
                # 行注释：吞到行尾
                j = source.find("\n", i)
                if j == -1:
                    j = n
                out.append(" " * (j - i))
                i = j
            elif ch == '"':
                in_string = True
                out.append(" ")
                i += 1
            elif ch == "'":
                in_char = True
                out.append(" ")
                i += 1
            else:
                out.append(ch)
                i += 1

    return "".join(out)
