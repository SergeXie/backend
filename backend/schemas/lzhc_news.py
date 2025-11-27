from datetime import datetime
from pydantic import BaseModel, field_serializer, Field
from typing import Optional


class EconomicNewsResponse(BaseModel):
    pkId: int = Field(..., description="主键ID")
    time: str = Field(..., description="发布时间")
    name: str = Field(..., description="经济指标名称")
    affects: Optional[str] = Field(None, description="影响方向")
    prevValue: Optional[str] = Field(None, description="前值")
    expectValue: Optional[str] = Field(None, description="预期值")
    publishValue: Optional[str] = Field(None, description="公布值")
    star: Optional[int] = Field(None, description="重要性星级")
    createTime: Optional[datetime] = Field(None, description="创建时间")
    updateTime: Optional[datetime] = Field(None, description="更新时间")
    isPeriodicStatistics: Optional[int] = Field(0, description="是否存在周期统计，1=存在，0=不存在")

    # 新增的三个字段
    finalScore: Optional[float] = None  # 评分 Impact Level
    scoreDescription: Optional[str] = None  # 方向一致性
    evaluateStrengthText: Optional[str] = None  # 方向文字
    direction: Optional[str] = None  # 方向
    tag: Optional[str] = None  # 标签

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
    preds: Optional[int] = 0

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
    summary: Optional[dict]

    # 把 datetime 转换成字符串
    @field_serializer("createTime")
    def serialize_dt(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")

    class Config:
        orm_mode = True
