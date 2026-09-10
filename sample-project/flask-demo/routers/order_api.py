"""订单管理 API（FastAPI 示例项目）

演示 Python/FastAPI 项目的接口文档自动生成：
- 装饰器路由 @router.get / @router.post 自动识别
- 类型注解参数自动提取
- docstring 自动作为接口注释
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/orders", tags=["orders"])

# 内存存储（演示用）
_ORDERS = {
    1: {"order_id": 1, "user_id": 100, "product": "机械键盘", "amount": 2, "status": "paid"},
    2: {"order_id": 2, "user_id": 101, "product": "显示器", "amount": 1, "status": "shipped"},
}


@router.get("")
async def list_orders(status: str = "all", limit: int = 10):
    """查询订单列表，支持按状态过滤"""
    result = list(_ORDERS.values())
    if status != "all":
        result = [o for o in result if o["status"] == status]
    return {"total": len(result), "items": result[:limit]}


@router.get("/{order_id}")
async def get_order(order_id: int):
    """查询单个订单详情

    Args:
        order_id: 订单ID（路径参数）
    """
    order = _ORDERS.get(order_id)
    if order is None:
        return {"error": "order not found"}
    return order


@router.post("")
async def create_order(payload: OrderCreate):
    """创建新订单"""
    new_id = max(_ORDERS.keys()) + 1
    order = {
        "order_id": new_id,
        "user_id": payload.user_id,
        "product": payload.product,
        "amount": payload.amount,
        "status": "created",
    }
    _ORDERS[new_id] = order
    return order


@router.put("/{order_id}")
async def update_order(order_id: int, payload: OrderUpdate):
    """更新订单信息（如修改数量或状态）"""
    order = _ORDERS.get(order_id)
    if order is None:
        return {"error": "order not found"}
    order.update(payload.model_dump(exclude_none=True))
    return order


@router.delete("/{order_id}")
async def delete_order(order_id: int):
    """删除订单（软删除，仅演示）"""
    if order_id not in _ORDERS:
        return {"error": "order not found"}
    del _ORDERS[order_id]
    return {"success": True}
