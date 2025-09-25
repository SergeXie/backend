from sqlalchemy import Integer, String, TIMESTAMP, text, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass


class DqlJinshiEconomicNews(Base):
    __tablename__ = "dql_jinshi_economic_news"

    pkId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="自增ID")
    time: Mapped[str] = mapped_column(String(10), nullable=False, comment="数据发布时间")
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
    time: Mapped[str] = mapped_column(String(10), nullable=False, comment="数据发布时间")
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



