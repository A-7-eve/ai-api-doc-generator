"""用户管理 API（Flask 示例项目）

演示 Flask 项目的接口文档自动生成：
- @app.route("/path", methods=[...]) 路由自动识别
- methods 参数提取 HTTP 方法（缺省视为 GET）
"""

from flask import Flask, jsonify, request

app = Flask(__name__)

_USERS = {
    1: {"user_id": 1, "username": "alice", "email": "alice@example.com"},
    2: {"user_id": 2, "username": "bob", "email": "bob@example.com"},
}


@app.route("/api/users", methods=["GET"])
def list_users():
    """查询全部用户"""
    return jsonify(list(_USERS.values()))


@app.route("/api/users/<int:user_id>")
def get_user(user_id):
    """查询单个用户

    Args:
        user_id: 用户ID（路径参数）
    """
    user = _USERS.get(user_id)
    if user is None:
        return jsonify({"error": "user not found"}), 404
    return jsonify(user)


@app.route("/api/users", methods=["POST"])
def create_user():
    """创建用户（请求体 JSON）"""
    body = request.get_json(silent=True) or {}
    new_id = max(_USERS.keys()) + 1
    user = {
        "user_id": new_id,
        "username": body.get("username", ""),
        "email": body.get("email", ""),
    }
    _USERS[new_id] = user
    return jsonify(user), 201


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """删除用户"""
    if user_id not in _USERS:
        return jsonify({"error": "user not found"}), 404
    del _USERS[user_id]
    return jsonify({"success": True})
