from pydantic import BaseModel, Field
from typing import List, Optional


# 定义 Pydantic Schema 进行请求参数验证
class ScreenFilter(BaseModel):
    name: str
    value: float
    nameValue: str


class TestResultRequest(BaseModel):
    page_no: int = Field(1, gt=0, alias="pageNo")
    page_size: int = Field(20, gt=0, alias="pageSize")
    goods: str = Field('%', alias="goods")
    period: str = Field('%', alias="period")
    strategy_uid: str = Field('%', alias="strategyUid")
    order_by: int = Field(0, alias="orderBy")
    status: int = Field(1, alias="status")  # 1 = 有效, 0 = 无效
    screens: List[ScreenFilter] = Field(default=[], alias="screens")
    trader_report_type: Optional[int] = Field(default=3, alias="traderReportType")  # 1 自动  2手动  3系统