"""C 代码解析器单元测试（v2.4 多语言支持）

覆盖：
1. 函数定义/声明提取（{} 定义与 ; 声明均收录）
2. static 函数跳过（内部实现非对外接口）
3. 参数类型解析（含 const/指针修饰）
4. 注释提取（// 与 /* */、文件头注释）
5. 注释/字符串字面量中的伪函数防误匹配
6. 目录级解析（.c/.h 各自独立清单）
"""

import pytest
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.c_parser import (
    parse_c_project,
    parse_c_file,
    ENGINE_NAME,
    ENGINE_VERSION,
)


# ── 测试数据 ──

C_SRC = """\
/**
 * 用户数据访问模块
 */
#include <stdio.h>

// 创建用户，返回用户ID
int create_user(const char* name, int age) {
    return 1;
}

/* 按ID查询用户 */
user_t* get_user(int user_id) {
    return NULL;
}

// 内部辅助函数（static 应跳过）
static int helper_check(int x) {
    return x * 2;
}

// 删除用户
void delete_user(int user_id) {
}

// 更新用户（声明，定义在其他编译单元）
int update_user(int user_id, const char* new_name, int age);
"""

TRICKY_SRC = """\
#include <stdio.h>
/* int fake_in_comment(int a, int b) { */
// void also_fake(int x);

int real_one(char* msg) {
    printf("int inside_string(int y) {");
    return 0;
}
"""

EMPTY_SRC = """\
#include <stdio.h>
#define MAX 100
typedef struct { int a; } foo_t;
"""


# ── 函数提取 ──

class TestFunctionExtract:
    def test_parse_c_file(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        assert ctrl is not None
        assert ctrl.className == "user_dao.c"

    def test_functions_found(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        names = [e.javaMethod for e in ctrl.endpoints]
        for expected in ("create_user", "get_user", "delete_user", "update_user"):
            assert expected in names, f"缺少函数 {expected}: {names}"

    def test_static_skipped(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        names = [e.javaMethod for e in ctrl.endpoints]
        assert "helper_check" not in names

    def test_method_uniform_post(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        for e in ctrl.endpoints:
            assert e.method.value == "POST"  # C 无 HTTP 语义，统一 POST

    def test_path_is_function_name(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        cu = next(e for e in ctrl.endpoints if e.javaMethod == "create_user")
        assert cu.path == "/create_user"


# ── 参数与返回类型 ──

class TestParamsAndReturn:
    def test_param_names(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        cu = next(e for e in ctrl.endpoints if e.javaMethod == "create_user")
        assert [p.name for p in cu.params] == ["name", "age"]

    def test_const_pointer_type(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        cu = next(e for e in ctrl.endpoints if e.javaMethod == "create_user")
        assert cu.params[0].type == "const char*"

    def test_return_type_int(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        cu = next(e for e in ctrl.endpoints if e.javaMethod == "create_user")
        assert cu.returnType == "int"

    def test_return_type_pointer(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        gu = next(e for e in ctrl.endpoints if e.javaMethod == "get_user")
        assert "user_t*" in gu.returnType


# ── 注释提取 ──

class TestComments:
    def test_line_comment(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        cu = next(e for e in ctrl.endpoints if e.javaMethod == "create_user")
        assert cu.comment == "创建用户，返回用户ID"

    def test_block_comment(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        gu = next(e for e in ctrl.endpoints if e.javaMethod == "get_user")
        assert gu.comment == "按ID查询用户"

    def test_file_header_comment(self):
        ctrl = parse_c_file(C_SRC, "user_dao.c")
        assert "用户数据访问模块" in (ctrl.comment or "")


# ── 防误匹配 ──

class TestAntiFalseMatch:
    def test_comment_string_not_matched(self):
        ctrl = parse_c_file(TRICKY_SRC, "tricky.c")
        names = [e.javaMethod for e in ctrl.endpoints]
        assert "fake_in_comment" not in names
        assert "also_fake" not in names
        assert "inside_string" not in names
        assert "real_one" in names

    def test_no_function_returns_none(self):
        assert parse_c_file(EMPTY_SRC, "empty.c") is None


# ── 目录级解析 ──

class TestProjectParse:
    def test_c_and_h_independent_lists(self):
        with tempfile.TemporaryDirectory() as td:
            proj = os.path.join(td, "c-demo")
            os.makedirs(proj)
            with open(os.path.join(proj, "user_dao.c"), "w", encoding="utf-8") as f:
                f.write(C_SRC)
            with open(os.path.join(proj, "user_dao.h"), "w", encoding="utf-8") as f:
                f.write("int create_user(const char* name, int age);\n")

            meta = parse_c_project(proj)
            assert meta.projectName == "c-demo"
            # .c 和 .h 各自独立清单
            assert len(meta.controllers) == 2

    def test_engine_info(self):
        assert ENGINE_NAME == "c-regex"
        assert ENGINE_VERSION == "1.0"
