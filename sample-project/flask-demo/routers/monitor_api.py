"""健康检查与统计接口"""

from fastapi import APIRouter

router = APIRouter(tags=["monitor"])


@router.get("/health")
async def health_check():
    """服务健康检查（无参数 GET 接口示例）"""
    return {"status": "ok"}


@router.get("/stats/orders")
async def order_stats(date_from: str, date_to: str):
    """统计时间段内的订单指标

    Args:
        date_from: 开始日期 YYYY-MM-DD
        date_to: 结束日期 YYYY-MM-DD
    """
    return {"date_from": date_from, "date_to": date_to, "count": 0}
