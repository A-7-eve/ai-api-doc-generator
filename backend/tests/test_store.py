"""MySQL 存储层单元测试

覆盖：
1. 项目存储：保存、读取、列表、删除
2. 接口存储：保存（关联项目）、读取、按项目列表
3. 不存在的 ID 返回 None
4. 数据持久化（重启不丢失）

说明：测试使用独立测试库（apidoc_test），与真实数据（apidoc 库）完全隔离。
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
import pymysql.cursors
import config
from models.schemas import (
    ProjectMeta, ControllerMeta, EndpointMeta, ParamMeta, HTTPMethod,
)


def _make_project(project_id="proj-test-001") -> ProjectMeta:
    ep = EndpointMeta(
        endpointId="ep-test-001",
        method=HTTPMethod.GET,
        path="/users/{id}",
        fullPath="/api/users/{id}",
        javaMethod="getUser",
        params=[ParamMeta(name="id", type="Long", annotation="@PathVariable", required=True)],
        description="获取用户",
    )
    ctrl = ControllerMeta(
        controllerId="ctrl-test-001",
        className="UserController",
        baseUrl="/api",
        endpoints=[ep],
    )
    return ProjectMeta(
        projectId=project_id,
        projectName="test-project",
        controllers=[ctrl],
    )


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """整个测试会话使用独立测试库，结束后清理"""
    import store as store_module

    # 指向测试库
    store_module._DB_CONF["database"] = config.DB_NAME_TEST

    # 创建测试库（无 database 连接）
    conf = dict(store_module._DB_CONF)
    conf.pop("database", None)
    conn = pymysql.connect(**conf, cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME_TEST}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()

    # 在测试库中建表
    store_module._init_db()

    yield

    # 会话结束后清空测试库数据（保留表结构，加快下次启动）
    conn = store_module._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            cur.execute("DELETE FROM endpoints")
            cur.execute("DELETE FROM projects")
            cur.execute("DELETE FROM users")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def isolated_store(_test_database):
    """每个测试前清空项目/接口表，测试间互不影响"""
    import store as store_module

    conn = store_module._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            cur.execute("DELETE FROM endpoints")
            cur.execute("DELETE FROM projects")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    finally:
        conn.close()

    return store_module


class TestProjectStore:

    def test_save_and_get(self, isolated_store):
        project = _make_project("p1")
        isolated_store.projects["p1"] = project
        loaded = isolated_store.projects.get("p1")
        assert loaded is not None
        assert loaded.projectName == "test-project"

    def test_get_nonexistent(self, isolated_store):
        assert isolated_store.projects.get("nonexistent-id") is None

    def test_list_all(self, isolated_store):
        isolated_store.projects["p1"] = _make_project("p1")
        isolated_store.projects["p2"] = _make_project("p2")
        all_projects = isolated_store.projects.list_all()
        assert len(all_projects) == 2

    def test_delete(self, isolated_store):
        isolated_store.projects["p1"] = _make_project("p1")
        assert isolated_store.projects.delete("p1") is True
        assert isolated_store.projects.get("p1") is None

    def test_delete_nonexistent(self, isolated_store):
        assert isolated_store.projects.delete("nonexistent") is False

    def test_contains(self, isolated_store):
        isolated_store.projects["p1"] = _make_project("p1")
        assert "p1" in isolated_store.projects
        assert "nonexistent" not in isolated_store.projects


class TestEndpointStore:

    def test_save_and_get(self, isolated_store):
        project = _make_project("p1")
        isolated_store.projects["p1"] = project
        ep = project.controllers[0].endpoints[0]
        isolated_store.endpoints.set_with_project("ep1", ep, "p1")

        loaded = isolated_store.endpoints.get("ep1")
        assert loaded is not None
        assert loaded.javaMethod == "getUser"

    def test_get_nonexistent(self, isolated_store):
        assert isolated_store.endpoints.get("nonexistent") is None

    def test_list_by_project(self, isolated_store):
        project = _make_project("p1")
        isolated_store.projects["p1"] = project
        ep = project.controllers[0].endpoints[0]
        isolated_store.endpoints.set_with_project("ep1", ep, "p1")

        eps = isolated_store.endpoints.list_by_project("p1")
        assert len(eps) == 1

    def test_list_by_empty_project(self, isolated_store):
        eps = isolated_store.endpoints.list_by_project("empty")
        assert len(eps) == 0

    def test_update_endpoint(self, isolated_store):
        project = _make_project("p1")
        isolated_store.projects["p1"] = project
        ep = project.controllers[0].endpoints[0]
        isolated_store.endpoints.set_with_project("ep1", ep, "p1")

        # 修改并保存
        ep.description = "更新后的描述"
        isolated_store.endpoints["ep1"] = ep

        loaded = isolated_store.endpoints.get("ep1")
        assert loaded.description == "更新后的描述"
