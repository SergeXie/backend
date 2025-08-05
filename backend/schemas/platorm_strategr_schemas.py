from pydantic import BaseModel, Field
from typing import List, Optional


# 定义 Pydantic Schema 进行请求参数验证
class ScreenFilter(BaseModel):
    name: str
    value: float
    nameValue: str


class TestResultRequest(BaseModel):
    page_no: Optional[int] = Field(None, gt=0, alias="pageNo")
    page_size: Optional[int] = Field(None, gt=0, alias="pageSize")
    goods: str = Field('%', alias="goods")
    period: str = Field('%', alias="period")
    strategy_uid: str = Field('%', alias="strategyUid")
    order_by: int = Field(0, alias="orderBy")
    status: int = Field(1, alias="status")  # 1 = 有效, 0 = 无效
    screens: List[ScreenFilter] = Field(default=[], alias="screens")
    trader_report_type: Optional[int] = Field(default=None, alias="traderReportType")  # 1 自动  2手动  3系统


class RealOrderFloatingProfitModel(BaseModel):
    """
    回测时间范围内实时策略历史订单浮动盈亏请求模型
    """
    goods: str = Field(default=None, description='交易品种')
    period: str = Field(default=None, description='交易周期')
    initialCash: int = Field(default=100000, description='初始资金')
    strategyUid: str = Field(default=None, description='系统策略uid')
    beginTime: Optional[str] = Field(default=None, description='开始时间')
    endTime: Optional[str] = Field(default=None, description='开始时间')


