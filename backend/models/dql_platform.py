import uuid
from datetime import datetime
from typing import Annotated
from sqlalchemy import String, VARCHAR, BigInteger, DateTime, Integer, Float, TIMESTAMP, Text, Double, Index
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    pass


# 通用 Mapped 类型主键, 需手动添加，参考以下使用方式
# MappedBase -> id: Mapped[id_key]
# DataClassBase && Base -> id: Mapped[id_key] = mapped_column(init=False)
id_key = Annotated[
    int, mapped_column(primary_key=True, index=True, autoincrement=True, sort_order=-999, comment='主键id')
]


def get_uuid4_str() -> str:
    """
    获取 uuid4 字符串

    :return:
    """
    return str(uuid.uuid4())


class DplGoodsTest(Base):

    __tablename__ = "dql_goods"

    pkid: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goods: Mapped[str] = mapped_column(VARCHAR(64),comment='平台-交易品种')
    goodType: Mapped[str] = mapped_column(VARCHAR(64),comment='品种类型')
    table_name: Mapped[str] = mapped_column(VARCHAR(32), comment='平台表名')
    trading_goods: Mapped[str] = mapped_column(VARCHAR(64), unique=True, index=True, comment='交易品种')
    platform: Mapped[str] = mapped_column(VARCHAR(64), unique=True, index=True, comment='平台')
    digits: Mapped[int] = mapped_column(Integer, nullable=False, server_default='2', comment='精度')
    isSynthesise: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0', comment='是否是需要合成的品种')



class BaseTrading(Base):

    __abstract__ = True

    pkId:Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False, comment='平台')
    tradingGoods: Mapped[str] = mapped_column(String(64), nullable=False, comment='交易品种')
    type: Mapped[str] = mapped_column(String(64), nullable=False, server_default='0', comment='种类年线、日线等')
    tradeDateTime: Mapped[datetime | None] = mapped_column(DateTime, nullable=False, comment='时间点')
    digits: Mapped[int] = mapped_column(Integer, nullable=False, server_default='2', comment='精度')
    spread: Mapped[float] = mapped_column(Float, nullable=False, server_default='0.0000000000', comment='点差')
    swapLong: Mapped[float] = mapped_column(Float, nullable=False, server_default='0.0000000000', comment='多单隔夜利息')
    swapShort: Mapped[float] = mapped_column(Float, nullable=False, server_default='0.0000000000', comment='空单隔夜利息')
    opening: Mapped[float] = mapped_column(Float, nullable=False, server_default='0.0000000000', comment='开盘价')
    closed: Mapped[float] = mapped_column(Float, nullable=False, server_default='0.0000000000', comment='收盘价')
    high: Mapped[float] = mapped_column(Float, nullable=False, server_default='0.0000000000', comment='最高价')
    low: Mapped[float] = mapped_column(Float, nullable=False, server_default='0.0000000000', comment='最低价')
    vol: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default='0', comment='成交量')
    creationTime: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False,
                                                   server_default='CURRENT_TIMESTAMP', comment='创建时间')


class TradingFPG(BaseTrading):
    __tablename__ = 'dql_trading_fpg'
    

class TradingFPG2(BaseTrading):
    __tablename__ = 'dql_trading_fpg_tests'


class TradingBRC5(BaseTrading):
    __tablename__ = 'dql_trading_bcr5'


class TradingOnda(BaseTrading):
    __tablename__ = 'dql_trading_onda'


class TradingFXTM5(BaseTrading):
    __tablename__ = 'dql_trading_fxtm5'


class TradingFXTM5xxj(BaseTrading):
    __tablename__ = 'dql_trading_xxj'


class TradingIndex(BaseTrading):
    __tablename__ = 'dql_trading_index'


class TradingIndex2(BaseTrading):
    __tablename__ = 'dql_trading_index2'


class DqlIndicators(Base):
    """
    指标表
    """
    __tablename__ = 'dql_indicators'

    pkId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(64), nullable=False, comment='唯一标识符')
    name: Mapped[str] = mapped_column(String(32), nullable=False, comment='策略指标名称')
    className: Mapped[str] = mapped_column(String(32), nullable=False, comment='指标名称')
    description: Mapped[str] = mapped_column(String(255), nullable=False, comment='指标备注')
    parameters: Mapped[str] = mapped_column(String(1024), nullable=False, comment='指标参数')
    type: Mapped[int] = mapped_column(Integer, nullable=False, comment='指标参数')
    subType: Mapped[int] = mapped_column(Integer, nullable=False, comment='副图参数')
    owner: Mapped[str] = mapped_column(String(64), nullable=False, comment='用户')
    createTime: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False,
                                                 server_default='CURRENT_TIMESTAMP', comment='创建时间')
    pinyinname: Mapped[str] = mapped_column(String(255), nullable=False, comment='中文指标的拼音')
    weights: Mapped[str] = mapped_column(Float, nullable=False, comment='指标权重')


class DqlStrategy(Base):
    """
    策略表
    """

    __tablename__ = 'dql_strategy'

    pkId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(64), nullable=False, comment='唯一标识符')
    indicatorsClassName: Mapped[str] = mapped_column(String(64), nullable=False, comment='指标类名 自定义策略的为空')
    name: Mapped[str] = mapped_column(String(32), nullable=False, comment='策略名称')
    className: Mapped[str] = mapped_column(String(32), nullable=False, comment='策略名称')
    description: Mapped[str] = mapped_column(String(255), nullable=False, comment='指标备注')
    parameters: Mapped[str] = mapped_column(String(1024), nullable=False, comment='指标参数')
    type: Mapped[int] = mapped_column(Integer, nullable=False, comment='0为系统指标 1为自定义策略')
    owner: Mapped[str] = mapped_column(String(64), nullable=False, comment='用户')
    codeFilePath: Mapped[str] = mapped_column(String(255), nullable=False, comment='代码文件目录')
    pinyinname: Mapped[str] = mapped_column(String(255), nullable=False, comment='中文指标的拼音')
    weights: Mapped[str] = mapped_column(Float, nullable=False, comment='指标权重')
    is_delete: Mapped[int] = mapped_column(Integer, nullable=False, comment='0 未删除 1 已删除')
    createTime: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False,
                                                server_default='CURRENT_TIMESTAMP', comment='创建时间')


class DqlStrategyTestResult(Base):

    """
    指标策略结果表
    """

    __tablename__ = "dql_strategy_test_result"

    pkId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment='唯一标识符')
    title: Mapped[str] = mapped_column(String(64), nullable=False, comment='标题')
    notes: Mapped[str] = mapped_column(String(255), nullable=False, comment='备注')
    strategyUid: Mapped[str] = mapped_column(String(64), nullable=False, comment='回测策略uid')
    goodsId: Mapped[str] = mapped_column(String(64), nullable=False, comment='品种')
    period: Mapped[str] = mapped_column(String(8), nullable=False, comment='周期')
    spread: Mapped[int] = mapped_column(Integer, nullable=False, comment='点差')
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, comment='杠杆')
    traderResult: Mapped[str] = mapped_column(LONGTEXT, nullable=False, comment='交易结果')
    indicatorResult: Mapped[str] = mapped_column(LONGTEXT, nullable=False, comment='指标数据结果')
    parameter: Mapped[str] = mapped_column(String(1024), nullable=False, comment='策略参数')
    startTime: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False,comment='开始时间')
    endTime: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, comment='结束时间')
    isBursted: Mapped[int] = mapped_column(Integer, nullable=False, comment='是否爆仓 0 未爆仓 1 已爆仓')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='1 已入库 0 未入库')
    yieldRate: Mapped[float] = mapped_column(Double, nullable=False, comment='收益率')
    mdr: Mapped[float] = mapped_column(Double, nullable=False, comment='最大回撤率')
    winRate: Mapped[float] = mapped_column(Double, nullable=False, comment='胜率')
    pnl: Mapped[float] = mapped_column(Double, nullable=False, comment='盈亏')
    plr: Mapped[float] = mapped_column(Double, nullable=False, comment='盈亏比')
    tradeCount: Mapped[float] = mapped_column(Double, nullable=False, comment='交易单数')
    maxProfit: Mapped[float] = mapped_column(Double, nullable=False, comment='最大每手盈利')
    maxLoss: Mapped[float] = mapped_column(Double, nullable=False, comment='最大每手亏损')
    avgProfit: Mapped[float] = mapped_column(Double, nullable=False, comment='平均每单盈亏')
    maxFUR: Mapped[float] = mapped_column(Double, nullable=False, comment='最大资金利用率')
    score: Mapped[float] = mapped_column(Double, nullable=False, comment='得分')
    is_delete: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment='0 未删除 1 已删除')
    paramsStrName: Mapped[str] = mapped_column(String(32), comment='前端参数名字')
    weight: Mapped[int] = mapped_column(Integer, default=0, comment='权重')
    weightNotes: Mapped[int] = mapped_column(Integer, default=0, comment='权重备注')
    calculationStatus: Mapped[int] = mapped_column(Integer, nullable=False, index=True,
                                                   comment='计算回测结果状态 1 计算完成 0 未计算完成')
    newReportTemplate: Mapped[str] = mapped_column(LONGTEXT, nullable=False, comment='新报告模板')

    traderReportType: Mapped[int] = mapped_column(Integer, nullable=False, index=True,
                                                  comment='交易报告上传类型  0 手动上传  1 自动上传  其他为系统报告')

    createTime: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False,
                                                 server_default='CURRENT_TIMESTAMP', comment='创建时间')


class DqlPwdLink(Base):
    """
    口令链接表
    """
    __tablename__ = 'dql_pwd_link'

    pkId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    linkUid: Mapped[str] = mapped_column(String(64), nullable=False, comment='唯一标识符')
    linkParameters: Mapped[str] = mapped_column(String(32), nullable=False, comment='链接参数')
    createTime: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False,
                                                 server_default='CURRENT_TIMESTAMP', comment='创建时间')


class TradingStrategy(Base):
    """
    交易策略表
    """

    __tablename__ = 'trading_strategy'

    pkId: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tradeUid: Mapped[int] = mapped_column(String(64), nullable=False, comment='交易ID')
    strategyUid: Mapped[str] = mapped_column(String(64), nullable=False, comment='策略uid')
    name: Mapped[str] = mapped_column(String(32), nullable=False, comment='策略名称')
    goods: Mapped[str] = mapped_column(String(64), nullable=False, comment='品种')
    period: Mapped[str] = mapped_column(String(8), nullable=False, comment='周期')
    parameter: Mapped[str] = mapped_column(Text, nullable=False, comment='参数')
    createTime: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False,
                                                 server_default='CURRENT_TIMESTAMP', comment='创建时间')





