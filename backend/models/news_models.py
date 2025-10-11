from sqlalchemy import Integer, String, TIMESTAMP, text, Text, BigInteger, SmallInteger, DateTime, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass


class DqlJinshiEconomicNews(Base):
    __tablename__ = "dql_jinshi_economic_news"

    pkId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    time: Mapped[str] = mapped_column(String(50), nullable=False, comment="数据发布时间")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="经济指标名称")
    affects: Mapped[str] = mapped_column(String(50), nullable=True, comment="影响方向")
    prevValue: Mapped[str] = mapped_column(String(50), nullable=True, comment="前值")
    expectValue: Mapped[str] = mapped_column(String(50), nullable=True, comment="预期值")
    publishValue: Mapped[str] = mapped_column(String(50), nullable=True, comment="公布值")
    createTime: Mapped[str] = mapped_column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="记录创建时间"
    )
    updateTime: Mapped[str] = mapped_column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        comment="记录最后更新时间"
    )


class DqlJinshiMarketNews(Base):
    __tablename__ = "dql_jinshi_market_news"

    pkId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    time: Mapped[str] = mapped_column(String(50), nullable=False, comment="数据发布时间")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="快讯内容")
    createTime: Mapped[str] = mapped_column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="记录创建时间"
    )
    updateTime: Mapped[str] = mapped_column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        comment="记录最后更新时间"
    )


class DqlJinshiEvent(Base):
    __tablename__ = "dql_jinshi_event"

    pkId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="唯一ID，对应金十事件ID")
    country: Mapped[str] = mapped_column(String(100), nullable=True, comment="国家或地区")
    determine: Mapped[int] = mapped_column(SmallInteger, nullable=True, comment="是否确定事件（1确定，0待定）")
    eventContent: Mapped[str] = mapped_column(Text, nullable=False, comment="事件内容，例如会议、公告或领导访问等")
    eventTime: Mapped[DateTime] = mapped_column(DateTime, nullable=True, comment="事件发生时间（UTC时间）")
    note: Mapped[str] = mapped_column(Text, nullable=True, comment="备注信息（若有）")
    people: Mapped[str] = mapped_column(String(100), nullable=True, comment="相关人物（若有）")
    region: Mapped[str] = mapped_column(String(100), nullable=True, comment="相关地区（若有）")
    star: Mapped[int] = mapped_column(SmallInteger, nullable=True, comment="重要等级（星级）")
    emergencies: Mapped[int] = mapped_column(SmallInteger, nullable=True, default=0, comment="是否为紧急事件（1是，0否）")
    vipResource: Mapped[str] = mapped_column(String(255), nullable=True, comment="来源或特殊资源信息")
    createTime: Mapped[DateTime] = mapped_column(TIMESTAMP, nullable=False, server_default=func.current_timestamp(), comment="记录创建时间")
    updateTime: Mapped[DateTime] = mapped_column(TIMESTAMP, nullable=False, server_default=func.current_timestamp(), server_onupdate=func.current_timestamp(), comment="记录更新时间")


class DqlJinshiHoliday(Base):
    __tablename__ = "dql_jinshi_holiday"

    pkId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="唯一ID，对应金十假期ID")
    holidayDate: Mapped[DateTime] = mapped_column(DateTime, nullable=False, comment="假期日期（UTC时间）")
    country: Mapped[str] = mapped_column(String(100), nullable=True, comment="国家或地区")
    exchangeName: Mapped[str] = mapped_column(String(255), nullable=True, comment="交易所名称")
    name: Mapped[str] = mapped_column(String(255), nullable=True, comment="假期名称，例如国庆节、圣诞节等")
    restNote: Mapped[str] = mapped_column(Text, nullable=True, comment="休市说明，例如“休市一日”")
    createTime: Mapped[DateTime] = mapped_column(TIMESTAMP, nullable=False, server_default=func.current_timestamp(), comment="记录创建时间")
    updateTime: Mapped[DateTime] = mapped_column(TIMESTAMP, nullable=False, server_default=func.current_timestamp(), server_onupdate=func.current_timestamp(), comment="记录更新时间")


