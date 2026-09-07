"""角色与鉴权单元测试

覆盖：
1. 密码哈希与校验（hash_password / verify_password）
2. JWT 签发与解析（create_token + get_current_user 的核心逻辑）
3. 用户存储（创建/查重/改角色/删除）
4. 项目归属校验（check_project_owner）

说明：测试使用独立测试库（apidoc_test），与真实数据（apidoc 库）完全隔离。
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
import pymysql.cursors
import config
import store as store_module
from store import hash_password, verify_password
from models.schemas import UserMeta, ProjectMeta


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """整个测试会话使用独立测试库，结束后清理"""
    store_module._DB_CONF["database"] = config.DB_NAME_TEST

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

    store_module._init_db()
    yield


@pytest.fixture
def isolated_users(_test_database):
    """每个测试前清空用户表，测试间互不影响"""
    conn = store_module._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users")
        conn.commit()
    finally:
        conn.close()

    return store_module.UserStore()


class TestPasswordHashing:

    def test_hash_and_verify_correct(self):
        stored = hash_password("admin123")
        assert verify_password("admin123", stored) is True

    def test_verify_wrong_password(self):
        stored = hash_password("admin123")
        assert verify_password("wrong", stored) is False

    def test_hash_with_fixed_salt_deterministic(self):
        h1 = hash_password("abc", salt="deadbeef")
        h2 = hash_password("abc", salt="deadbeef")
        assert h1 == h2

    def test_hash_contains_salt(self):
        stored = hash_password("mypassword")
        salt, _ = stored.split("$", 1)
        assert len(salt) == 32  # 16字节 hex = 32字符

    def test_verify_malformed_stored(self):
        assert verify_password("x", "no-salt-here") is False


class TestToken:

    def test_create_and_decode(self):
        from security import create_token, SECRET_KEY, ALGORITHM
        import jwt
        token = create_token("uid-1", "alice", "admin")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "uid-1"
        assert payload["username"] == "alice"
        assert payload["role"] == "admin"

    def test_expired_token_rejected(self):
        from security import SECRET_KEY, ALGORITHM
        import jwt
        from datetime import datetime, timedelta, timezone
        payload = {
            "sub": "uid-1",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    def test_tampered_token_rejected(self):
        from security import create_token, SECRET_KEY, ALGORITHM
        import jwt
        token = create_token("uid-1", "alice", "user")
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token + "x", SECRET_KEY, algorithms=[ALGORITHM])


class TestUserStore:

    def test_create_user(self, isolated_users):
        user = isolated_users.create("bob", "pass123456")
        assert user.username == "bob"
        assert user.role == "user"
        assert user.userId

    def test_create_admin_role(self, isolated_users):
        user = isolated_users.create("root", "pass123456", role="admin")
        assert user.role == "admin"

    def test_duplicate_username_rejected(self, isolated_users):
        isolated_users.create("bob", "pass123456")
        with pytest.raises(ValueError):
            isolated_users.create("bob", "other12345")

    def test_get_by_username(self, isolated_users):
        isolated_users.create("bob", "pass123456")
        result = isolated_users.get_by_username("bob")
        assert result is not None
        user, password_hash = result
        assert user.username == "bob"
        assert verify_password("pass123456", password_hash)

    def test_get_by_username_nonexistent(self, isolated_users):
        assert isolated_users.get_by_username("nobody") is None

    def test_get_by_id(self, isolated_users):
        created = isolated_users.create("bob", "pass123456")
        loaded = isolated_users.get(created.userId)
        assert loaded is not None
        assert loaded.username == "bob"

    def test_list_all(self, isolated_users):
        isolated_users.create("u1", "pass123456")
        isolated_users.create("u2", "pass123456")
        assert len(isolated_users.list_all()) == 2

    def test_set_role(self, isolated_users):
        created = isolated_users.create("bob", "pass123456")
        assert isolated_users.set_role(created.userId, "admin") is True
        assert isolated_users.get(created.userId).role == "admin"

    def test_set_role_invalid(self, isolated_users):
        created = isolated_users.create("bob", "pass123456")
        with pytest.raises(ValueError):
            isolated_users.set_role(created.userId, "superadmin")

    def test_set_role_nonexistent(self, isolated_users):
        assert isolated_users.set_role("no-such-id", "admin") is False

    def test_delete_user(self, isolated_users):
        created = isolated_users.create("bob", "pass123456")
        assert isolated_users.delete(created.userId) is True
        assert isolated_users.get(created.userId) is None

    def test_delete_nonexistent(self, isolated_users):
        assert isolated_users.delete("no-such-id") is False


class TestProjectOwner:

    def _make_project(self, owner_id=None) -> ProjectMeta:
        return ProjectMeta(
            projectId="p1",
            projectName="demo",
            ownerUserId=owner_id,
        )

    def test_admin_always_allowed(self):
        from security import check_project_owner
        admin = UserMeta(userId="admin-1", username="admin", role="admin")
        project = self._make_project(owner_id="someone-else")
        check_project_owner(project, admin)  # 不抛异常即通过

    def test_owner_allowed(self):
        from security import check_project_owner
        user = UserMeta(userId="u1", username="alice", role="user")
        project = self._make_project(owner_id="u1")
        check_project_owner(project, user)

    def test_non_owner_rejected(self):
        from fastapi import HTTPException
        from security import check_project_owner
        user = UserMeta(userId="u2", username="mallory", role="user")
        project = self._make_project(owner_id="u1")
        with pytest.raises(HTTPException) as exc_info:
            check_project_owner(project, user)
        assert exc_info.value.status_code == 403

    def test_legacy_project_visible_to_all(self):
        """旧数据无归属人时对所有用户可见（兼容历史数据）"""
        from security import check_project_owner
        user = UserMeta(userId="u2", username="alice", role="user")
        project = self._make_project(owner_id=None)
        check_project_owner(project, user)
