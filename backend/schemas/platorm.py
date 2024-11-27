import datetime

from fastapi.params import Path, Query
from pydantic import BaseModel, Field
from typing import Optional, List

from schemas.base import ResponseSuccess

class GoodsData(BaseModel):
    pkid: int = Path(..., title="主键id")
    goods: str = Query(None, title="平台-品种")
    table_name: str = Query(None, title="表名")
    subGoods: str = Query(None, title="交易品种")
    platform: str = Query(None, title="平台")


class GoodsResponse(ResponseSuccess):

    data: List[GoodsData]


class AddTraderStrategy(BaseModel):
    initialCash: int = Path(title="初始本金"),
    goods: str = Query(..., title="交易品种"),
    period: str = Query(..., title="周期"),
    beginTime: str = Query(..., title="开始时间"),
    endTime: str = Query(..., title="结束时间")
    leverage: Optional[float] = 1.0  # 杠杆数量


class AddTraderStrategyData(BaseModel):
    goodsTradeArray: List[AddTraderStrategy]


class AddTraderTicks(BaseModel):

    ticksId: str = Query(..., title="交易ID"),
    size: float = Query(..., title="手数大小")
    position: Optional[str] = Query(None, title="方向: 多头（long） 空头（short）")
    orderType: Optional[str] = Query(None, title="订单类型：buy/sell")
    stopLoss: Optional[float] = 0  # 止损
    takeProfit: Optional[float] = 0  # 止盈
    price: Optional[float] = 0  # 价格 当市价单时 市价价格成交  挂单则需要传递
    type: Optional[int] = 0  # 可选参数，当选择挂单时需传递：1 =buy limit  2 = sell limit 3 = buy stop 4=sell stop
    operate: str = Query(default="marketOrder", title="操作：默认市价成交：marketOrder  挂单成交：pendingOrder")
    valid: Optional[str] = Query(None, title="订单有效期时间 例如2024-04-20 15:00")
    klineId: int = Path(title="K线id")


class TraderTicksGoods(BaseModel):
    goodsTraderId: str = Query(title="交易品种ID")
    ticks: List[AddTraderTicks]


class AddTraderTicksData(BaseModel):
    tradeId: str = Query(..., title="交易回测id")
    goodsTradeArray: List[TraderTicksGoods]
