"""Java 代码解析器单元测试

覆盖：
1. AST 解析：正常 SpringBoot Controller 代码
2. 正则兜底：含 javalang 无法解析的语法的代码
3. DTO 解析
4. 参数提取（@RequestParam / @PathVariable / @RequestBody）
5. 路径拼接（类级 @RequestMapping + 方法级映射）
"""

import pytest
import os
import sys

# 确保 backend 目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.java_parser import parse_project
from parser.regex_fallback import regex_parse_file
from models.schemas import HTTPMethod


# ── 测试数据 ──

SAMPLE_CONTROLLER = """\
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping("/{id}")
    public User getUser(@PathVariable Long id) {
        return userService.findById(id);
    }

    @PostMapping
    public User create(@RequestBody User user) {
        return userService.save(user);
    }

    @PutMapping("/{id}")
    public User update(@PathVariable Long id, @RequestBody User user) {
        user.setId(id);
        return userService.save(user);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        userService.deleteById(id);
    }

    @GetMapping
    public List<User> list(@RequestParam(required = false) String name) {
        return userService.findAll(name);
    }
}
"""

# 含 Java 14 record 语法，javalang 无法解析
UNPARSEABLE_CONTROLLER = """\
package com.example.controller;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    public record OrderRequest(String productId, int quantity) {}

    @PostMapping("/create")
    public String createOrder(@RequestBody OrderRequest req) {
        return "order-" + req.productId();
    }

    @GetMapping("/{orderId}")
    public String getOrder(@PathVariable String orderId) {
        return "order-detail-" + orderId;
    }
}
"""

SAMPLE_DTO = """\
package com.example.dto;

public class User {
    private Long id;
    private String name;
    private String email;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
}
"""


# ── AST 解析测试 ──

class TestAstParser:

    def test_parse_controller_count(self, tmp_path):
        """解析一个 Controller 文件，应识别出 1 个 Controller"""
        fpath = tmp_path / "UserController.java"
        fpath.write_text(SAMPLE_CONTROLLER, encoding="utf-8")
        project = parse_project(str(tmp_path))
        assert len(project.controllers) == 1

    def test_parse_endpoint_count(self, tmp_path):
        """应识别出 5 个接口"""
        fpath = tmp_path / "UserController.java"
        fpath.write_text(SAMPLE_CONTROLLER, encoding="utf-8")
        project = parse_project(str(tmp_path))
        assert len(project.controllers[0].endpoints) == 5

    def test_parse_http_methods(self, tmp_path):
        """应正确识别 GET/POST/PUT/DELETE"""
        fpath = tmp_path / "UserController.java"
        fpath.write_text(SAMPLE_CONTROLLER, encoding="utf-8")
        project = parse_project(str(tmp_path))
        methods = [ep.method for ep in project.controllers[0].endpoints]
        assert HTTPMethod.GET in methods
        assert HTTPMethod.POST in methods
        assert HTTPMethod.PUT in methods
        assert HTTPMethod.DELETE in methods

    def test_parse_base_url(self, tmp_path):
        """应正确提取类级 @RequestMapping 的 baseUrl"""
        fpath = tmp_path / "UserController.java"
        fpath.write_text(SAMPLE_CONTROLLER, encoding="utf-8")
        project = parse_project(str(tmp_path))
        assert project.controllers[0].baseUrl == "/api/users"

    def test_parse_full_path(self, tmp_path):
        """fullPath 应拼接 baseUrl + method path"""
        fpath = tmp_path / "UserController.java"
        fpath.write_text(SAMPLE_CONTROLLER, encoding="utf-8")
        project = parse_project(str(tmp_path))
        ep = project.controllers[0].endpoints[0]
        assert ep.fullPath == "/api/users/{id}"

    def test_parse_path_variable(self, tmp_path):
        """应正确提取 @PathVariable 参数"""
        fpath = tmp_path / "UserController.java"
        fpath.write_text(SAMPLE_CONTROLLER, encoding="utf-8")
        project = parse_project(str(tmp_path))
        ep = project.controllers[0].endpoints[0]  # GET /{id}
        assert len(ep.params) == 1
        assert ep.params[0].annotation == "@PathVariable"
        assert ep.params[0].name == "id"

    def test_parse_request_param_optional(self, tmp_path):
        """应正确提取 @RequestParam(required = false)"""
        fpath = tmp_path / "UserController.java"
        fpath.write_text(SAMPLE_CONTROLLER, encoding="utf-8")
        project = parse_project(str(tmp_path))
        list_ep = [ep for ep in project.controllers[0].endpoints if ep.method == HTTPMethod.GET and ep.path == ""][0]
        assert len(list_ep.params) == 1
        assert list_ep.params[0].annotation == "@RequestParam"
        assert list_ep.params[0].required is False

    def test_parse_dto(self, tmp_path):
        """应正确解析 DTO 类字段"""
        fpath = tmp_path / "User.java"
        fpath.write_text(SAMPLE_DTO, encoding="utf-8")
        project = parse_project(str(tmp_path))
        assert len(project.dtos) == 1
        assert project.dtos[0].className == "User"
        field_names = [f.name for f in project.dtos[0].fields]
        assert "id" in field_names
        assert "name" in field_names

    def test_skip_test_directory(self, tmp_path):
        """应跳过 test 目录下的文件"""
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "TestController.java").write_text(SAMPLE_CONTROLLER, encoding="utf-8")
        project = parse_project(str(tmp_path))
        assert len(project.controllers) == 0


# ── 正则兜底测试 ──

class TestRegexFallback:

    def test_regex_parse_controller(self):
        """正则兜底应能解析 Controller"""
        controllers, dtos = regex_parse_file(UNPARSEABLE_CONTROLLER)
        assert len(controllers) == 1
        assert controllers[0].className == "OrderController"
        assert controllers[0].baseUrl == "/api/orders"

    def test_regex_parse_endpoints(self):
        """正则兜底应提取出接口"""
        controllers, _ = regex_parse_file(UNPARSEABLE_CONTROLLER)
        assert len(controllers[0].endpoints) == 2

    def test_regex_parse_http_methods(self):
        """正则兜底应正确识别 HTTP 方法"""
        controllers, _ = regex_parse_file(UNPARSEABLE_CONTROLLER)
        methods = [ep.method for ep in controllers[0].endpoints]
        assert HTTPMethod.POST in methods
        assert HTTPMethod.GET in methods

    def test_regex_parse_path_variable(self):
        """正则兜底应提取 @PathVariable 参数"""
        controllers, _ = regex_parse_file(UNPARSEABLE_CONTROLLER)
        get_ep = [ep for ep in controllers[0].endpoints if ep.method == HTTPMethod.GET][0]
        assert len(get_ep.params) == 1
        assert get_ep.params[0].annotation == "@PathVariable"
        assert get_ep.params[0].name == "orderId"

    def test_fallback_triggered_on_parse_failure(self, tmp_path):
        """javalang 解析失败时应自动降级为正则兜底"""
        fpath = tmp_path / "OrderController.java"
        fpath.write_text(UNPARSEABLE_CONTROLLER, encoding="utf-8")
        project = parse_project(str(tmp_path))
        # 正则兜底应成功提取出 Controller
        assert len(project.controllers) == 1
        assert project.controllers[0].className == "OrderController"

    def test_regex_parse_dto(self):
        """正则兜底应能解析 DTO"""
        _, dtos = regex_parse_file(SAMPLE_DTO)
        assert len(dtos) == 1
        assert dtos[0].className == "User"
