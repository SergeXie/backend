from datetime import datetime
from pydantic import BaseModel, field_serializer
from typing import Optional


class EconomicNewsResponse(BaseModel):
    pkId: int
    time: str
    name: str
    affects: Optional[str] = None
    prevValue: Optional[str] = None
    expectValue: Optional[str] = None
    publishValue: Optional[str] = None
    createTime: Optional[datetime] = None
    updateTime: Optional[datetime] = None

    class Config:
        orm_mode = True  # 允许 Pydantic 从 ORM 对象读取数据

    # 把 datetime 转换成字符串
    @field_serializer("createTime", "updateTime")
    def serialize_dt(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")


class MarketNewsResponse(BaseModel):
    pkId: int
    time: str
    content: str
    createTime: Optional[datetime] = None
    updateTime: Optional[datetime] = None

    class Config:
        orm_mode = True

    # 把 datetime 转换成字符串
    @field_serializer("createTime", "updateTime")
    def serialize_dt(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")