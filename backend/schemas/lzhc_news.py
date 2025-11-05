from datetime import datetime
from pydantic import BaseModel, field_serializer, Field
from typing import Optional


class EconomicNewsResponse(BaseModel):
    pkId: int
    time: str
    name: str
    affects: Optional[str] = None
    prevValue: Optional[str] = None
    expectValue: Optional[str] = None
    publishValue: Optional[str] = None
    star: Optional[int] = None
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
    preds: int

    class Config:
        orm_mode = True
        from_attributes = True

    # 把 datetime 转换成字符串
    @field_serializer("createTime", "updateTime")
    def serialize_dt(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")

class JinshiEventBase(BaseModel):
    pkId: int
    country: Optional[str] = Field(None, max_length=100, description="国家或地区")
    determine: Optional[int] = Field(None, description="是否确定事件（1确定，0待定）")
    eventContent: str = Field(..., description="事件内容，例如会议、公告或领导访问等")
    eventTime: Optional[datetime] = Field(None, description="事件发生时间（UTC时间）")
    note: Optional[str] = Field(None, description="备注信息（若有）")
    people: Optional[str] = Field(None, max_length=100, description="相关人物（若有）")
    region: Optional[str] = Field(None, max_length=100, description="相关地区（若有）")
    star: Optional[int] = Field(None, description="重要等级（星级）")
    emergencies: Optional[int] = Field(0, description="是否为紧急事件（1是，0否）")
    vipResource: Optional[str] = Field(None, max_length=255, description="来源或特殊资源信息")

    # 把 datetime 转换成字符串
    @field_serializer("eventTime")
    def serialize_dt(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")

    class Config:
        orm_mode = True
        from_attributes = True


# ===================== 金十假期 =====================
class JinshiHolidayBase(BaseModel):
    pkId: int
    holidayDate: datetime = Field(..., description="假期日期（UTC时间）")
    country: Optional[str] = Field(None, max_length=100, description="国家或地区")
    exchangeName: Optional[str] = Field(None, max_length=255, description="交易所名称")
    name: Optional[str] = Field(None, max_length=255, description="假期名称，例如国庆节、圣诞节等")
    restNote: Optional[str] = Field(None, description="休市说明，例如“休市一日”")

    # 把 datetime 转换成字符串
    @field_serializer("holidayDate")
    def serialize_dt(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")

    class Config:
        from_attributes = True
        orm_mode = True


# 非农数据统计
class MarketStatisticsOut(BaseModel):
    pkId: int
    economicNewsUid: int
    time: str
    name: str
    newsType: Optional[str]
    m5: Optional[str]
    m30: Optional[str]
    h1: Optional[str]
    d1: Optional[str]
    w1: Optional[str]
    createTime: datetime

    # 把 datetime 转换成字符串
    @field_serializer("createTime")
    def serialize_dt(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")

    class Config:
        orm_mode = True
