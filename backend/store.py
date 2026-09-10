"""MySQL 持久化存储：项目数据、接口数据、文档数据和用户数据的持久化存储。

演进历史：内存 dict → SQLite → MySQL 8.0（pymysql 驱动）。
对外暴露与原 dict 接口兼容的 ProjectStore / EndpointStore，使上层路由无需改动。
users 表 + UserStore 为角色功能新增；
docs 表 + DocStore 为 v2.4 在线编辑功能新增。

表结构：
- projects(project_id PK, project_data JSON 文本, created_at)
- endpoints(endpoint_id PK, project_id, endpoint_data, updated_at)
- users(user_id PK, username UNIQUE, password_hash, role, created_at)
- docs(project_id + format 联合主键, content, updated_at)  ← v2.4
"""

import uuid
import hashlib
import secrets
import threading
from datetime import datetime, timezone
from typing import Optional

import pymysql
import pymysql.cursors

import config
from models.schemas import ProjectMeta, EndpointMeta, UserMeta

# 线程锁（每操作独立开关连接，锁用于串行化写冲突）
_lock = threading.Lock()

# 当前生效的连接配置（dict），供测试 fixture monkeypatch 隔离
_DB_CONF = {
    "host": config.DB_HOST,
    "port": int(config.DB_PORT),
    "user": config.DB_USER,
    "password": config.DB_PASSWORD,
    "database": config.DB_NAME,
    "charset": "utf8mb4",
    "autocommit": False,
}


def _get_conn() -> pymysql.connections.Connection:
    """获取数据库连接（每操作独立开关）"""
    return pymysql.connect(**_DB_CONF, cursorclass=pymysql.cursors.DictCursor)


def hash_password(password: str, salt: str | None = None) -> str:
    """密码哈希：pbkdf2_hmac(sha256, 10万轮)，格式 salt$hash"""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码：stored 格式为 salt$hash"""
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt), stored)


def _table_exists(conn, table: str) -> bool:
    """检查表是否存在"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name = %s",
            (_DB_CONF["database"], table),
        )
        return cur.fetchone()["cnt"] > 0


def _index_exists(conn, index: str) -> bool:
    """检查索引是否存在（MySQL 无 CREATE INDEX IF NOT EXISTS）"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM information_schema.statistics "
            "WHERE table_schema = %s AND table_name = 'endpoints' AND index_name = %s",
            (_DB_CONF["database"], index),
        )
        return cur.fetchone()["cnt"] > 0


def _create_database_if_missing():
    """确保目标数据库存在（不依赖外部手工建库）"""
    conf = dict(_DB_CONF)
    conf.pop("database", None)
    conn = pymysql.connect(**conf, cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{_DB_CONF['database']}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


def _init_db():
    """初始化数据库表结构（幂等，可重复调用）

    说明：endpoints 不建外键约束，仅保留 project_id 字段 + 索引，
    与原 SQLite 行为一致（SQLite 默认不启用外键），兼容历史孤儿数据。
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id   VARCHAR(64) PRIMARY KEY,
                    project_data MEDIUMTEXT NOT NULL,
                    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS endpoints (
                    endpoint_id   VARCHAR(64) PRIMARY KEY,
                    project_id    VARCHAR(64) NOT NULL,
                    endpoint_data MEDIUMTEXT NOT NULL,
                    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id       CHAR(36) PRIMARY KEY,
                    username      VARCHAR(64) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role          VARCHAR(16) NOT NULL DEFAULT 'user',
                    created_at    VARCHAR(64) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            # v2.4 在线编辑：文档编辑版存储表（联合主键 project_id+format）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS docs (
                    project_id VARCHAR(64) NOT NULL,
                    format     VARCHAR(16) NOT NULL,
                    content    MEDIUMTEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (project_id, format)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        conn.commit()
        if not _index_exists(conn, "idx_endpoints_project"):
            with conn.cursor() as cur:
                cur.execute("CREATE INDEX idx_endpoints_project ON endpoints(project_id)")
            conn.commit()
    finally:
        conn.close()


def _ensure_default_admin():
    """首次启动时创建默认管理员 admin / admin123"""
    with _lock:
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE username = %s", ("admin",))
                if cur.fetchone() is None:
                    cur.execute(
                        "INSERT INTO users (user_id, username, password_hash, role, created_at) "
                        "VALUES (%s, %s, %s, 'admin', %s)",
                        (
                            str(uuid.uuid4()),
                            "admin",
                            hash_password("admin123"),
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
            conn.commit()
        finally:
            conn.close()


# 初始化（模块导入时执行）
_create_database_if_missing()
_init_db()
_ensure_default_admin()


class ProjectStore:
    """项目存储，接口兼容 dict[projectId, ProjectMeta]"""

    def __setitem__(self, project_id: str, project: ProjectMeta):
        data = project.model_dump_json()
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "REPLACE INTO projects (project_id, project_data) VALUES (%s, %s)",
                        (project_id, data),
                    )
                conn.commit()
            finally:
                conn.close()

    def __getitem__(self, project_id: str) -> ProjectMeta:
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT project_data FROM projects WHERE project_id = %s",
                        (project_id,),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
        if row is None:
            raise KeyError(project_id)
        return ProjectMeta.model_validate_json(row["project_data"])

    def get(self, project_id: str) -> Optional[ProjectMeta]:
        try:
            return self[project_id]
        except KeyError:
            return None

    def __contains__(self, project_id: str) -> bool:
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM projects WHERE project_id = %s",
                        (project_id,),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
        return row is not None

    def list_all(self) -> list[ProjectMeta]:
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT project_data FROM projects ORDER BY created_at DESC"
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()
        return [ProjectMeta.model_validate_json(r["project_data"]) for r in rows]

    def delete(self, project_id: str) -> bool:
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM projects WHERE project_id = %s", (project_id,)
                    )
                    deleted = cur.rowcount > 0
                    cur.execute(
                        "DELETE FROM endpoints WHERE project_id = %s", (project_id,)
                    )
                    cur.execute(
                        "DELETE FROM docs WHERE project_id = %s", (project_id,)
                    )
                conn.commit()
                return deleted
            finally:
                conn.close()


class EndpointStore:
    """接口存储，接口兼容 dict[endpointId, EndpointMeta]"""

    def __setitem__(self, endpoint_id: str, endpoint: EndpointMeta):
        data = endpoint.model_dump_json()
        # 尝试找到对应的 project_id
        project_id = ""
        if hasattr(endpoint, "_project_id"):
            project_id = endpoint._project_id
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "REPLACE INTO endpoints (endpoint_id, project_id, endpoint_data) "
                        "VALUES (%s, %s, %s)",
                        (endpoint_id, project_id, data),
                    )
                conn.commit()
            finally:
                conn.close()

    def set_with_project(self, endpoint_id: str, endpoint: EndpointMeta, project_id: str):
        """设置接口并关联项目 ID"""
        data = endpoint.model_dump_json()
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "REPLACE INTO endpoints (endpoint_id, project_id, endpoint_data) "
                        "VALUES (%s, %s, %s)",
                        (endpoint_id, project_id, data),
                    )
                conn.commit()
            finally:
                conn.close()

    def __getitem__(self, endpoint_id: str) -> EndpointMeta:
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT endpoint_data FROM endpoints WHERE endpoint_id = %s",
                        (endpoint_id,),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
        if row is None:
            raise KeyError(endpoint_id)
        return EndpointMeta.model_validate_json(row["endpoint_data"])

    def get(self, endpoint_id: str) -> Optional[EndpointMeta]:
        try:
            return self[endpoint_id]
        except KeyError:
            return None

    def __contains__(self, endpoint_id: str) -> bool:
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM endpoints WHERE endpoint_id = %s",
                        (endpoint_id,),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
        return row is not None

    def list_by_project(self, project_id: str) -> list[EndpointMeta]:
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT endpoint_data FROM endpoints WHERE project_id = %s",
                        (project_id,),
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()
        return [EndpointMeta.model_validate_json(r["endpoint_data"]) for r in rows]

    def get_project_id(self, endpoint_id: str) -> Optional[str]:
        """查询接口所属的项目 ID，不存在返回 None"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT project_id FROM endpoints WHERE endpoint_id = %s",
                        (endpoint_id,),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
        return row["project_id"] if row else None


class UserStore:
    """用户存储（角色功能）"""

    def create(self, username: str, password: str, role: str = "user") -> UserMeta:
        """创建用户，用户名重复抛 ValueError"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM users WHERE username = %s", (username,)
                    )
                    if cur.fetchone():
                        raise ValueError(f"用户名已存在: {username}")
                    user = UserMeta(
                        userId=str(uuid.uuid4()),
                        username=username,
                        role=role,
                        createdAt=datetime.now(timezone.utc).isoformat(),
                    )
                    cur.execute(
                        "INSERT INTO users (user_id, username, password_hash, role, created_at) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (
                            user.userId,
                            username,
                            hash_password(password),
                            role,
                            user.createdAt,
                        ),
                    )
                conn.commit()
                return user
            finally:
                conn.close()

    def get_by_username(self, username: str) -> Optional[tuple[UserMeta, str]]:
        """按用户名查询，返回 (用户, 密码哈希)，不存在返回 None"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, username, password_hash, role, created_at "
                        "FROM users WHERE username = %s",
                        (username,),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        user = UserMeta(
            userId=row["user_id"],
            username=row["username"],
            role=row["role"],
            createdAt=row["created_at"],
        )
        return user, row["password_hash"]

    def get(self, user_id: str) -> Optional[UserMeta]:
        """按用户 ID 查询"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, username, role, created_at "
                        "FROM users WHERE user_id = %s",
                        (user_id,),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
        if row is None:
            return None
        return UserMeta(
            userId=row["user_id"],
            username=row["username"],
            role=row["role"],
            createdAt=row["created_at"],
        )

    def list_all(self) -> list[UserMeta]:
        """列出所有用户（不含密码）"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, username, role, created_at "
                        "FROM users ORDER BY created_at"
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()
        return [
            UserMeta(
                userId=r["user_id"],
                username=r["username"],
                role=r["role"],
                createdAt=r["created_at"],
            )
            for r in rows
        ]

    def set_role(self, user_id: str, role: str) -> bool:
        """修改用户角色，成功返回 True"""
        if role not in ("admin", "user"):
            raise ValueError("role 仅支持 admin 或 user")
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET role = %s WHERE user_id = %s",
                        (role, user_id),
                    )
                    updated = cur.rowcount > 0
                conn.commit()
                return updated
            finally:
                conn.close()

    def delete(self, user_id: str) -> bool:
        """删除用户，成功返回 True"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
                    deleted = cur.rowcount > 0
                conn.commit()
                return deleted
            finally:
                conn.close()


class DocStore:
    """文档编辑版存储（v2.4 在线编辑）

    docs 表按 (project_id, format) 存用户编辑后的文档内容；
    reset 删除记录即回退到生成器现场生成版。
    """

    def get(self, project_id: str, fmt: str) -> Optional[str]:
        """获取编辑版内容，无记录返回 None"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT content FROM docs WHERE project_id = %s AND format = %s",
                        (project_id, fmt),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()
        return row["content"] if row else None

    def set(self, project_id: str, fmt: str, content: str):
        """保存编辑版内容（upsert）"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "REPLACE INTO docs (project_id, format, content) VALUES (%s, %s, %s)",
                        (project_id, fmt, content),
                    )
                conn.commit()
            finally:
                conn.close()

    def reset(self, project_id: str, fmt: str) -> bool:
        """删除编辑版记录（回退到生成版），有删除返回 True"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM docs WHERE project_id = %s AND format = %s",
                        (project_id, fmt),
                    )
                    deleted = cur.rowcount > 0
                conn.commit()
                return deleted
            finally:
                conn.close()

    def delete_by_project(self, project_id: str) -> bool:
        """删除项目下全部编辑版文档（项目删除时联动清理）"""
        with _lock:
            conn = _get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM docs WHERE project_id = %s", (project_id,)
                    )
                    deleted = cur.rowcount > 0
                conn.commit()
                return deleted
            finally:
                conn.close()


# 对外暴露的存储实例（接口与原 dict 兼容）
projects = ProjectStore()
endpoints = EndpointStore()
users = UserStore()
docs = DocStore()
