import calendar
from datetime import datetime
import json
import traceback
import uuid
from typing import Optional
from fastapi import APIRouter, Query
from sqlalchemy import select, and_, update
from starlette.requests import Request
from starlette.responses import Response
from common.log import log
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.dql_platform import DplGoodsTest, DqlIndicators, DqlStrategy, DqlPwdLink, DqlStrategyTestResult, DqlOrder
from schemas.base import ErrorModel
from schemas.platorm import GoodsResponse, AddTraderStrategyData, AddTraderTicksData
from utils.common import select_goods_common, RandomIDGenerator, select_kline_data, Trader, \
    GoodTrader, PandasData, cache, get_indicator_data, model_classes, \
    get_entities_list, generate_random_string
from utils.prod_backtrader import MyStrategy
from utils.timezone import timezone
import pandas as pd
from utils.indicators import *


router = APIRouter()

# 保存内存变量
product_list = []


@router.get("/selectAllGoods", name="查询所有平台品种列表",
            responses={200: {"model": GoodsResponse}, 400: {"model": ErrorModel}})
async def test_user(page_no: Optional[int] = 1, page_size: Optional[int] = 100):

    async with async_db_session() as db:
        # 计算偏移量
        offset = (page_no - 1) * page_size
        platform_goods = await db.execute(select(DplGoodsTest).offset(offset).limit(page_size))
        result = platform_goods.scalars().all()

        data_list = [{"pkId": data.pkid, "goods": data.goods,
                      "digits": data.digits, "goodType": data.goodType,
                      "platform": data.platform} for data in result]

        return await response_base.success(data=data_list)


from datetime import datetime

@router.get("/selectKlineOrders", name="获取K线历史下单订单信息")
async def select_kline_orders(goods: str, period: str, beginTime: str, endTime: str, strategyUid: str):
    """
    :param goods: 交易品种 FPG-AUDUSD
    :param period: 周期
    :param beginTime: 开始时间
    :param endTime: 结束时间
    :param strategyUid: 策略uid
    """
    async with async_db_session() as db:
        stmt = (
            select(DqlOrder)
            .where(
                and_(
                    DqlOrder.tradingGoods == goods,
                    DqlOrder.period == period,
                    DqlOrder.timestamp.between(beginTime, endTime),
                    DqlOrder.strategyUid == strategyUid,
                )
            )
            .order_by(DqlOrder.timestamp.asc())
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

    # 需要格式化的所有时间字段
    time_fields = ['createTime', 'openTime', 'closeTime', 'timestamp']
    data = []
    for row in rows:
        d = row.__dict__.copy()
        d.pop('_sa_instance_state', None)
        for field in time_fields:
            if field in d and isinstance(d[field], datetime):
                d[field] = d[field].strftime('%Y-%m-%d %H:%M:%S')
        data.append(d)

    return await response_base.success(data=data)


@router.get("/dynamicKline", name="动态0号K线")
async def get_dynamic_kline(goods: str = Query(..., title="交易平台-交易品种"),
                            period: str = Query(..., title="周期")):
    """
    根据时间周期动态生成 K 线数据
    :param goods:
    :return:
    """
    print("执行动态K0")
    # 当前时间（假设需要 +2 小时）
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
    # now = datetime.datetime.utcnow()

    # 解析周期（以分钟为单位）
    period_map = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
        "W1": 10080,
        "MN": 43800
    }

    # 动态计算时间范围
    interval_minutes = period_map[period]

    if period == "W1":
        # 获取上一周的时间范围
        start_time = now - datetime.timedelta(days=now.weekday() + 1)  # 上一周的周日
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)  # 设置为当天零点
        end_time = start_time + datetime.timedelta(days=7)  # 上一周的周末

    elif period == "D1":
        # D1 周期，调整到当天的 00:00:00
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + datetime.timedelta(days=1)  # 次日 00:00:00

    elif period == "MN":
        # 本月的月初和月底
        start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)  # 月初
        _, last_day = calendar.monthrange(now.year, now.month)  # 获取本月最后一天
        end_time = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)  # 月底

    elif period == "H4":
        # H4处理
        start_time = now.replace(minute=(now.minute // interval_minutes) * interval_minutes, second=0, microsecond=0)
        end_time = start_time + datetime.timedelta(minutes=interval_minutes)

    else:
        # 其他周期处理
        start_time = now.replace(minute=(now.minute // interval_minutes) * interval_minutes, second=0, microsecond=0)
        end_time = start_time + datetime.timedelta(minutes=interval_minutes)

    print("start_time:", start_time)
    print("end_time:", end_time)

    async with async_db_session() as db:
        # 因M1数据没有更新到FPG-XAUUSD_合成，临时策略用FPG-XAUUSD,后续需要改
        if goods == "FPG-XAUUSD_合成":
            goods = "FPG-XAUUSD"

        select_model_class, result = await select_goods_common(db, goods, model_classes)

        if not select_model_class:
            return await response_base.fail(msg="数据库表未找到！", data=[])

        # 根据 lineId 查询出当前的时间
        select_k_time = select(select_model_class).where(
            select_model_class.platform == result.platform,
            select_model_class.tradingGoods == result.trading_goods,
            select_model_class.type == "M1",
            select_model_class.tradeDateTime >= start_time,
            select_model_class.tradeDateTime < end_time
        ).order_by(select_model_class.tradeDateTime)

        # 执行查询
        detail = await db.execute(select_k_time)
        kline_datas = detail.scalars().all()

        if kline_datas:
            is_final = False
            # 将数据转换为 DataFrame
            df = pd.DataFrame([{
                "pkId": x.pkId,
                "tradeDateTime": x.tradeDateTime.strftime("%Y-%m-%d %H:%M:%S"),
                "unxTimestamp": x.tradeDateTime.timestamp(),
                "swapLong": x.swapLong,
                "swapShort": x.swapShort,
                "opening": float(x.opening),
                "digits": x.digits,
                "spread": int(x.spread),
                "high": float(x.high),
                "low": float(x.low),
                "closed": float(x.closed),
                "vol": x.vol
            } for x in kline_datas])

            df['tradeDateTime'] = pd.to_datetime(df['tradeDateTime'])
            df = df.set_index('tradeDateTime')

            # 定义不同周期的类型名称映射
            type_dict = {
                'M5': '5min',  # 替换为小写 'min'
                'M15': '15min',
                'M30': '30min',
                'H1': '1h',  # 替换为小写 'h'
                'H4': '4h',
                'D1': '1d',  # 替换为小写 'd'
                'W1': 'W',  # 替换为小写 'w'
                'MN': 'ME'  # 替换为小写 'm'
            }

            interval = type_dict[period]
            # Pandas 聚合
            # 对高、低、成交量和spread进行常规的聚合处理
            resampled_df = df.resample(interval).agg({
                'high': 'max',  # 获取该周期的最高价
                'low': 'min',  # 获取该周期的最低价
                'vol': 'sum',  # 获取该周期的成交量总和
                'spread': 'last',  # 获取该周期的最后一个spread值
                'pkId': 'last',  # 取最后一个 pkId
                'swapLong': 'mean',  # 取周期内 swapLong 的平均值
                'swapShort': 'mean',  # 取周期内 swapShort 的平均值
            }).reset_index()

            # 单独处理开盘价和收盘价：获取该周期的第一根K线的开盘价和最后一根K线的收盘价
            resampled_df['opening'] = df['opening'].resample(interval).first().values  # 第一根K线的开盘价
            resampled_df['closed'] = df['closed'].resample(interval).last().values  # 最后一根K线的收盘价

            # 转换为字典
            if not resampled_df.empty:
                row = resampled_df.iloc[0]
                # 转换为 Python 基础类型
                lineData = {
                    "pkId": int(row["pkId"]),
                    "timestamp": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "unxTimestamp": int(start_time.timestamp()),
                    "open": float(row["opening"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["closed"]),
                    "vol": int(row["vol"]),
                    "spread": float(row["spread"]),
                    "swapLong": float(row["swapLong"]),  # 添加 swapLong
                    "swapShort": float(row["swapShort"])  # 添加 swapShort
                }
        else:
            is_final = True
            new_start_time = start_time - datetime.timedelta(minutes=interval_minutes)
            print("new_start_time:{}".format(new_start_time))
            print("start_time:{}".format(start_time))
            print("period:{}".format(period))
            select_k_time = select(select_model_class).where(
                select_model_class.platform == result.platform,
                select_model_class.tradingGoods == result.trading_goods,
                select_model_class.type == period,
                select_model_class.tradeDateTime >= new_start_time,
                select_model_class.tradeDateTime < start_time
            ).order_by(select_model_class.tradeDateTime.desc()).limit(1)
            # 再次执行查询
            detail = await db.execute(select_k_time)
            latest_data = detail.scalars().first()
            print(latest_data)
            if latest_data:
                lineData = {
                    "pkId": latest_data.pkId,
                    "timestamp": latest_data.tradeDateTime.strftime('%Y-%m-%d %H:%M:%S'),
                    "unxTimestamp": latest_data.tradeDateTime.timestamp(),
                    "open": latest_data.opening,
                    "high": latest_data.high,
                    "low": latest_data.low,
                    "close": latest_data.closed,
                    "vol": latest_data.vol,
                    "spread": latest_data.spread,
                    "swapLong": latest_data.swapLong,  # 添加 swapLong
                    "swapShort": latest_data.swapShort  # 添加 swapShort
                }
            else:
                lineData = None

        print("lineData")
        print(lineData)

        return await response_base.success(data={"goods": goods, "period": period, "utc": 2, "is_final": is_final,
                                                 "lineData": lineData})


@router.get("/selectFrontKline", name="获取K线历史数据")
async def select_kline_front(lineId: Optional[int] = 0,
                             goods: str = Query(..., title="交易平台-交易品种"),
                             period: str = Query(..., title="周期")):
    """
    往前是小于  往后是大于
    :param lineId: 最前k线id，0时返回所有k线，往前查询数据库数据，根据id
    :param goods: 交易品种 FPG-AUDUSD
    :param period: 周期  M1---1分钟；M5---5分钟； M15---15分钟； M30---30分钟 “H1” 表示小时  D1 表示天  W 周 WN 月
    :return:

    """
    # 获取当前时间
    current_time = datetime.datetime.now()

    # 将当前时间转换为字符串时间
    formatted_current_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
    # 根据给定的交易品种 交易平台和周期查询出 所有数据来，返回K线数据出去
    # 查询中间表 DplGoodsTest
    async with async_db_session() as db:
        select_model_class, result = await select_goods_common(db, goods, model_classes)

        if not select_model_class: return await response_base.fail(msg="数据库表未找到！", data=[])

        query = select(select_model_class).where(
            select_model_class.tradingGoods == result.trading_goods,
            select_model_class.platform == result.platform,
            select_model_class.type == period).order_by(select_model_class.tradeDateTime.desc()).limit(1000)

        if lineId != 0:
            # 根据 lineId 查询出当前的时间
            select_k_time = select(select_model_class).where(
                select_model_class.tradingGoods == result.trading_goods,
                select_model_class.platform == result.platform,
                select_model_class.type == period,
                select_model_class.pkId == lineId)

            detail = await db.execute(select_k_time)

            trader_datas = detail.scalars().first()

            # 将时间转换为字符串时间
            formatted_datetime = trader_datas.tradeDateTime.strftime('%Y-%m-%d %H:%M:%S')

            query = query.where(select_model_class.tradeDateTime <= formatted_datetime)

        if period.startswith("W") or period.startswith("D") or period.startswith("MN"):
            # 根据period参数的取值进行条件判断
            period_dict = {"period": period, "platform": result.platform,
                           "tradingGoods": result.trading_goods, "lineId": lineId, "type": "FrontKline"}

            period_tuple = tuple(period_dict.items())

        else:
            period_tuple = None

        result_list = await select_kline_data(db, query, period_tuple)  # 不使用缓存处理函数

        result_list = sorted(result_list, key=lambda x: x['timestamp'])

        print(len(result_list))

        # trading_goods 交易品种  period 周期
        return await response_base.success(data={"goods": goods, "period": period, "utc": 2, "lineData": result_list})


@router.get("/selectAfterKLine", name="获取K线最新数据")
async def select_platform_goods_k_line(lineId: int,
                                       goods: str = Query(..., title="交易平台-交易品种"),
                                       period: str = Query(..., title="周期")):
    """
    lineId 最新k线id 必填 # 传递的是pkId
    :param goods: 交易品种 FPG-AUDUSD
    :param period: 周期  M1---1分钟；M5---5分钟； M15---15分钟； M30---30分钟 “H1” 表示小时  D1 表示天  W 周 WN 月
    :return:
    """
    async with async_db_session() as db:

        select_model_class, result = await select_goods_common(db, goods, model_classes)

        if not select_model_class:
            return await response_base.fail(msg="数据库表未找到！", data=[])

        # 根据 lineId 查询出当前的时间
        select_k_time = select(select_model_class).where(
            select_model_class.tradingGoods == result.trading_goods,
            select_model_class.platform == result.platform,
            select_model_class.type == period,
            select_model_class.pkId == lineId)

        detail = await db.execute(select_k_time)

        trader_datas = detail.scalars().first()

        if trader_datas:

            # 将时间转换为字符串时间
            formatted_datetime = trader_datas.tradeDateTime.strftime('%Y-%m-%d %H:%M:%S')

            # 计算偏移量
            # 查询指定模型的数据
            query = select(select_model_class).where(
    select_model_class.tradingGoods == result.trading_goods,
                select_model_class.platform == result.platform,
                select_model_class.type == period,
                select_model_class.tradeDateTime >= formatted_datetime).limit(1000)

        else:
            return await response_base.success(data={"goods": goods, "period": period, "utc": 2,
                                                     "lineData": []})

        if period.startswith("W") or period.startswith("D") or period.startswith("MN"):
            # 根据period参数的取值进行条件判断
            period_dict = {"period": period, "platform": result.platform,
                           "tradingGoods": result.trading_goods, "lineId": lineId,
                           "indicatortype": "AfterKLine"}

            period_tuple = tuple(period_dict.items())

        else:
            period_tuple = None

        result_list = await select_kline_data(db, query, period_tuple)

        # trading_goods 交易品种  period 周期
        return await response_base.success(data={"goods": goods, "period": period, "utc": 2,
                                                 "lineData": result_list})


@router.get("/selectGoodsKLines", name="获取K线时段数据")
async def select_multiple_goods_k_lines(goods: str = Query(..., title="交易平台-交易品种"),
                                        period: str = Query(..., title="周期"),
                                        beginTime: str = Query(..., title="开始时间"),
                                        endTime: str = Query(..., title="结束时间"),
                                        ):
    """
    查询交易品种周期的K线数据
    :param goods:
    :param period:
    :param beginTime:
    :param endTime:
    :return:
    """
    # 查询中间表 DplGoodsTest
    async with async_db_session() as db:

        select_model_class, result = await select_goods_common(db, goods, model_classes)

        if not select_model_class:
            return await response_base.fail(msg="数据库表未找到！", data=[])

        result_data = select(select_model_class).where(
            select_model_class.tradingGoods == result.trading_goods,
            select_model_class.platform == result.platform,
            select_model_class.type == period,
            select_model_class.tradeDateTime.between(beginTime, endTime)).order_by(
            select_model_class.tradeDateTime.desc())


        result_list = await select_kline_data(db, result_data)  # 不使用缓存处理函数

        return await response_base.success(data={"goods": goods, "period": period, "utc": 2,
                                                 "beginTime": beginTime, "endTime": endTime,
                                                 "lineData": result_list})


@router.post("/traderGoodsStrategy", name="选择多个交易品种开始回测接口")
async def add_trader_goods_strategy(reqeust: Request, add_trader_strategy_schemas: AddTraderStrategyData):
    """
    :param reqeust:
    :param add_trader_strategy_schemas:
    :return:
    """
    data_json = await reqeust.json()
    print("交易品种参数：{}".format(data_json))
    # 添加的多个数据是一次性提交过来
    goods_trade_array = data_json["goodsTradeArray"]
    if not goods_trade_array:
        return await response_base.fail(msg="商品参数为空")

    # 自生成交易id返回给前端
    trader_id = RandomIDGenerator()

    # 生成交易品种ID UUID唯一性
    for data_goods in goods_trade_array:
        generator_uuid = uuid.uuid4()
        data_goods["goodsTraderId"] = str(generator_uuid)

    trader_strategy = Trader()

    # 添加多个交易品种
    trader_strategy.add_goods_trader(goods_trade_array, trader_id.generate_random_id())

    return await response_base.success(**{"data": {"tradeId": trader_strategy.trader_id,
                                                   "goodsTradeArray": goods_trade_array}})


@router.post("/traderGoodsOrder", name="回测手动下单交易接口")
async def select_trader_goods_strategy(request: Request,
                                       add_trader_ticks: AddTraderTicksData):

    """
    :param request
    :param pkId: 交易品种ID
    :param add_trader_ticks: 订单数组
    :return:
    """
    try:
        # Instantiate Cerebro engine
        cerebro = bt.Cerebro()
        data = add_trader_ticks.dict()

        print("请求的数据：{}".format(data))

        tradeId = data["tradeId"]
        goodsTradeArray = data["goodsTradeArray"][0]
        goodsTraderId = data["goodsTradeArray"][0].get("goodsTraderId", 0)

        trader_goods_strategy = GoodTrader()
        select_traderId = trader_goods_strategy.select_trade_id(tradeId)
        if not select_traderId:
            return await response_base.fail(msg="tradeId not found !", data=[])

        # 组织数据结构
        ticks_ids = trader_goods_strategy.add_ticks(goodsTradeArray, tradeId)

        if not ticks_ids:
            return await response_base.fail(msg="goodsTraderId not found !", data=[])

        print("trader_goods_strategy:{}".format(trader_goods_strategy.trader_goods_strategy_data))

        # 交易回测
        # 第一步加载数据源出来，选择从数据库中读取出来，根据交易品种查询
        data_source = []
        async with async_db_session() as db:
            # 获取周期，开始时间，结束时间进行数据库查询
            for goods in trader_goods_strategy.trader_goods_strategy_data["goodsTradeArray"]:
                # 第一步查询中间表 交易品种表
                select_model_class, result = await select_goods_common(db, goods["goods"], model_classes)

                # # 第二步，根据交易品种表的 table_name 字段查找主表，拿到交易历史数据加入到backtrader的数据源中（开始时间 - 结束时间）
                details = await db.execute(
                    select(select_model_class).where(and_(select_model_class.tradingGoods == result.trading_goods,
                                                          select_model_class.platform == result.platform,
                                                          select_model_class.type == goods["period"],
                                                          select_model_class.tradeDateTime.between(
                                                              goods["beginTime"], goods["endTime"]))))

                results = details.scalars().all()

            # 从数据库加载数据源
            results_data_list = [{"pkId": x.pkId, "datetime": timezone.str_f(x.tradeDateTime), "open": x.opening,
                                  "high": x.high, "low": x.low, "close": x.closed,
                                  "volume": x.vol, "openinterest": 0, "klineId": x.pkId} for x in results]

            # 添加 backtrader 大脑
            # 添加数据源
            df = pd.DataFrame(results_data_list)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            data = PandasData(dataname=df)

            # 加载数据
            cerebro.adddata(data)

            # Add strategys to Cerebro
            cerebro.addstrategy(MyStrategy,
                                trader_goods_strategy.trader_goods_strategy_data["goodsTradeArray"],
                                tradeId, goodsTraderId)

            # 设置初始资金
            cerebro.broker.setcash(int(goods["initialCash"]))
            # 设置杠杆数量
            cerebro.broker.setcommission(mult=goods["leverage"])

            print('初始现金: %.2f' % cerebro.broker.getvalue())  # 打印初始现金
            start_portfolio_value = cerebro.broker.getvalue()
            # Run Cerebro Engine
            result = cerebro.run(tradehistory=True)
            print('策略运行结束后的现金: %.2f' % cerebro.broker.getvalue())  # 打印策略运行结束后的现金

            end_portfolio_value = cerebro.broker.getvalue()
            pnl = end_portfolio_value - start_portfolio_value

            # 返回结果
            ret = result[0].get_analysis()

            ret[0]["summary"]["leverage"] = goods.get("leverage", 1)

            return await response_base.success(**{"data": ret})

    except Exception as e:
        info = traceback.format_exc()
        log.error("回测手动下单交易接口出错：{}".format(info))
        print("错误信息：{}".format(info))
        return Response(status_code=500, content="系统错误!")


@router.get("/indicatorsList", name="获取所有指标列表")
async def indicators_list(pageNo: int = Query(1), pageSize: int = Query(100),
                          orderBy: int = Query(0), keyWord: str = Query('%')):
    """

    :param pageNo:
    :param pageSize:
    :param orderBy:
    :param keyWord:
    :return:
    """

    return await get_entities_list(DqlIndicators, pageNo, pageSize, orderBy, keyWord)


@router.post("/indicatorFrontKline", name="获取指标历史数据")
async def indicator_front_kline(request: Request):
    """

    :param request:
    :return:
    """
    return await get_indicator_data(request, "FrontKline", name="history")


@router.post("/indicatorAfterKLine", name="获取指标最新数据")
async def indicator_after_kline(request: Request):
    """
    :param request:
    :return:
    """

    return await get_indicator_data(request, "AfterKline", name="latest")


@router.post("/indicatorGoodsPeriodKLines", name="获取指标时段数据")
async def indicator_goods_kline(request: Request):
    """
    :param request:
    :return:
    """
    return await get_indicator_data(request, "PeriodKLines", name=None)


@router.post("/addLink", name="添加口令链接")
async def add_link(request: Request):
    """
    :param request:
    :return:
    """

    data = await request.json()

    link_parameters = data.get("linkParameters", None)
    if not link_parameters: return await response_base.fail(msg="口令参数失效 !", data=[])

    async with async_db_session() as db:
        # 入库
        db_add_link = DqlPwdLink(linkUid=generate_random_string("LK"), linkParameters=link_parameters)
        db.add(db_add_link)
        await db.commit()

        return await response_base.success(data={"linkUid": db_add_link.linkUid})


@router.get("/selectLink", name="查询口令链接")
async def select_link(request: Request, linkUid: str):
    """
    :param request:
    :return:
    """

    if not linkUid: return await response_base.fail(msg="链接不存在!", data=[])

    async with async_db_session() as db:
        # 查询
        select_links = await db.execute(select(DqlPwdLink).where(DqlPwdLink.linkUid == linkUid))

        result = select_links.scalars().first()

        if not result:
            return await response_base.fail(msg="链接不存在!", data=[])

        return await response_base.success(data={"linkParameters": result.linkParameters})


@router.get("/update_data")
async def update_data():
    async with async_db_session() as db:
        # 查询
        select_links = await db.execute(select(DqlStrategyTestResult))

        result = select_links.scalars().all()

        for x in result:
            datas = json.loads(x.traderResult)
            traderResult = datas.get("traderResult", [])
            traderReport = datas.get("traderReport", {})
            floatingPointValues = datas.get("floatingPointValues", [])
            netAssetValues = datas.get("netAssetValues", [])

            for trade in traderResult:
                trade["openTime"] = None
                trade["openPrice"] = 0
                trade["closeTime"] = None
                trade["goodsId"] = None  # 交易品种/货币对
                trade["taxes"] = 0.0  # 税
                trade["commission"] = 0.0  # 手续费
                trade["swap"] = 0.0  # 隔夜费

            # 将修改后的traderResult转换回JSON字符串
            traderResult_json = json.dumps(
                     {"traderResult": traderResult,
                      "traderReport": traderReport,
                      "floatingPointValues": floatingPointValues,
                      "netAssetValues": netAssetValues})

            # 更新plr字段
            stmt = (
                update(DqlStrategyTestResult)
                .where(DqlStrategyTestResult.pkId == x.pkId)
                .values(traderResult=traderResult_json)
            )
            await db.execute(stmt)
            await db.commit()

            print("ok")
            traderResult = json.loads(x.traderResult)
            print(traderResult)


@router.get("/clearGoodsCach", name="清除交易品种缓存")
async def clear_goods_echo():
    """
    清除所以交易品种缓存
    :return:
    """
    # 在需要的时候清除缓存
    cache.clear()

    return "OK"


@router.post("/indicatorDifferenceData", name="对比不同版本的指标数据")
async def indicator_goods_kline(request: Request):
    """
    :param request:
    :return:
    """
    returndata = await get_indicator_data(request, "PeriodKLines", name=None)
    indicator_data_list = returndata['data']

    need_compared_Data = []  # 将需要对比的数据加载到这里

    result = {}
    for indicator_data in indicator_data_list:
        # print(indicator_data)
        result = indicator_data
        need_compared_Data.append(indicator_data['data'])

    try:
        original_indicator_data = need_compared_Data[0]  # 原始指标数据
        new_indicator_data = need_compared_Data[1]  # 新的指标数据
    except IndexError:
        return await response_base.fail(msg="请选择了两个指标", data=[])

    diff = []
    if len(original_indicator_data) != len(new_indicator_data):
        # 计算对称差集
        diff = symmetric_difference(original_indicator_data, new_indicator_data)
    elif len(original_indicator_data) == len(new_indicator_data):
        diff = []
        for i in range(len(original_indicator_data)):
            if original_indicator_data[i] != new_indicator_data[i]:
                tmp = list_difference(original_indicator_data[i], new_indicator_data[i])
                if len(tmp) != 0:
                    if isinstance(tmp, dict):
                        diff.append(tmp)
                    elif isinstance(tmp, list):
                        diff += tmp

    result['data'] = diff
    return await response_base.success(data=result)


# 求对称差集
def symmetric_difference(lst1, lst2):
    # 对称差集结果
    sym_diff = []

    # 添加在lst1中但不在lst2中的元素
    for elem in lst1:
        if elem not in lst2:
            sym_diff.append(elem)

    # 添加在lst2中但不在lst1中的元素
    for elem in lst2:
        if elem not in lst1:
            sym_diff.append(elem)

    return sym_diff

# 求不同点
def list_difference(lst1, lst2):
    """
    :param lst1:
    :param lst2:
    :return:
        [
            {
                "type": "brokenline",
                "color": "#00FF00",
                "data": [
                    {
                        "kLineId": 1620001,
                        "timestamp": "2024-05-01 21:55:00",
                        "price": 2328.21
                    },
                    {
                        "kLineId": 1621854,
                        "timestamp": "2024-05-01 23:35:00",
                        "price": 2320.48
                    }
                ]
            },
            {
                "type": "brokenline",
                "color": "#00FF00",
                "data": [
                    {
                        "kLineId": 1620001,
                        "timestamp": "2024-05-01 21:55:00",
                        "price": 2328.21
                    },
                    {
                        "kLineId": 1621854,
                        "timestamp": "2024-05-01 23:35:00",
                        "price": 2320.48
                    }
                ]
            },
        ]
    """
    data_type = lst1['type']
    if data_type == 'line':
        result = []
        ls1 = lst1['data']
        ls2 = lst2['data']
        # ls1 = [{'kLineId': 1597622, 'timestamp': '2024-05-01 01:15:00', 'price': 2288.28}, {'kLineId': 1599004, 'timestamp': '2024-05-01 02:40:00', 'price': 2293.17}, {'kLineId': 1603915, 'timestamp': '2024-05-01 07:15:10', 'price': 2281.53}, {'kLineId': 1606384, 'timestamp': '2024-05-01 09:30:10', 'price': 2289.66}, {'kLineId': 1607653, 'timestamp': '2024-05-01 10:40:00', 'price': 2283.39}, {'kLineId': 1613322, 'timestamp': '2024-05-01 15:50:00', 'price': 2299.91}, {'kLineId': 1613708, 'timestamp': '2024-05-01 16:10:00', 'price': 2295.12}, {'kLineId': 1614810, 'timestamp': '2024-05-01 17:10:00', 'price': 2310.37}, {'kLineId': 1615454, 'timestamp': '2024-05-01 17:45:00', 'price': 2297.33}, {'kLineId': 1616364, 'timestamp': '2024-05-01 18:35:00', 'price': 2310.4}, {'kLineId': 1619027, 'timestamp': '2024-05-01 21:00:00', 'price': 2295.68}, {'kLineId': 1620001, 'timestamp': '2024-05-01 21:55:00', 'price': 2328.21}, {'kLineId': 1621854, 'timestamp': '2024-05-01 23:35:00', 'price': 2320.48}]
        # ls2 = [{'kLineId': 1597622, 'timestamp': '2024-05-01 01:15:00', 'price': 2288.28}, {'kLineId': 1599004, 'timestamp': '2024-05-01 02:40:00', 'price': 2293.17}, {'kLineId': 1603915, 'timestamp': '2024-05-01 07:15:00', 'price': 2281.53}, {'kLineId': 1606384, 'timestamp': '2024-05-01 09:30:00', 'price': 2289.66}, {'kLineId': 1607653, 'timestamp': '2024-05-01 10:40:00', 'price': 2283.39}, {'kLineId': 1613322, 'timestamp': '2024-05-01 15:50:00', 'price': 2299.91}, {'kLineId': 1613708, 'timestamp': '2024-05-01 16:10:10', 'price': 2295.12}, {'kLineId': 1614810, 'timestamp': '2024-05-01 17:10:00', 'price': 2310.37}, {'kLineId': 1616364, 'timestamp': '2024-05-01 18:35:00', 'price': 2310.4}, {'kLineId': 1619027, 'timestamp': '2024-05-01 21:00:00', 'price': 2295.68}, {'kLineId': 1620001, 'timestamp': '2024-05-01 21:55:00', 'price': 2328.21}, {'kLineId': 1621230, 'timestamp': '2024-05-01 23:00:00', 'price': 2306.95}, {'kLineId': 1621854, 'timestamp': '2024-05-01 23:35:00', 'price': 2320.48}]
        if len(ls1) == len(ls2):
            res1 = []
            res2 = []
            for i in range(len(ls1)):
                if ls1[i] != ls2[i]:
                    res1.append(ls1[i])
            result1 = lst1
            result1['data'] = res1
            for i in range(len(ls2)):
                if ls2[i] != ls1[i]:
                    res2.append(ls2[i])
            result2 = lst2
            result2['data'] = res2
            result = [result1, result2]
        else:
            res1, res2 = difference1(ls1, ls2)

            for i in res1:
                tmp = lst1.copy()
                tmp['data'] = i
                result.append(tmp)

            for i in res2:
                tmp = lst2.copy()
                tmp['data'] = i
                result.append(tmp)

        return result
    if data_type == 'brokenline':
        result = []
        ls1 = lst1['data']
        ls2 = lst2['data']
        # ls1 = [{'kLineId': 1597622, 'timestamp': '2024-05-01 01:15:00', 'price': 2288.28}, {'kLineId': 1599004, 'timestamp': '2024-05-01 02:40:00', 'price': 2293.17}, {'kLineId': 1603915, 'timestamp': '2024-05-01 07:15:10', 'price': 2281.53}, {'kLineId': 1606384, 'timestamp': '2024-05-01 09:30:10', 'price': 2289.66}, {'kLineId': 1607653, 'timestamp': '2024-05-01 10:40:00', 'price': 2283.39}, {'kLineId': 1613322, 'timestamp': '2024-05-01 15:50:00', 'price': 2299.91}, {'kLineId': 1613708, 'timestamp': '2024-05-01 16:10:00', 'price': 2295.12}, {'kLineId': 1614810, 'timestamp': '2024-05-01 17:10:00', 'price': 2310.37}, {'kLineId': 1615454, 'timestamp': '2024-05-01 17:45:00', 'price': 2297.33}, {'kLineId': 1616364, 'timestamp': '2024-05-01 18:35:00', 'price': 2310.4}, {'kLineId': 1619027, 'timestamp': '2024-05-01 21:00:00', 'price': 2295.68}, {'kLineId': 1620001, 'timestamp': '2024-05-01 21:55:00', 'price': 2328.21}, {'kLineId': 1621854, 'timestamp': '2024-05-01 23:35:00', 'price': 2320.48}]
        # ls2 = [{'kLineId': 1597622, 'timestamp': '2024-05-01 01:15:00', 'price': 2288.28}, {'kLineId': 1599004, 'timestamp': '2024-05-01 02:40:00', 'price': 2293.17}, {'kLineId': 1603915, 'timestamp': '2024-05-01 07:15:00', 'price': 2281.53}, {'kLineId': 1606384, 'timestamp': '2024-05-01 09:30:00', 'price': 2289.66}, {'kLineId': 1607653, 'timestamp': '2024-05-01 10:40:00', 'price': 2283.39}, {'kLineId': 1613322, 'timestamp': '2024-05-01 15:50:00', 'price': 2299.91}, {'kLineId': 1613708, 'timestamp': '2024-05-01 16:10:10', 'price': 2295.12}, {'kLineId': 1614810, 'timestamp': '2024-05-01 17:10:00', 'price': 2310.37}, {'kLineId': 1616364, 'timestamp': '2024-05-01 18:35:00', 'price': 2310.4}, {'kLineId': 1619027, 'timestamp': '2024-05-01 21:00:00', 'price': 2295.68}, {'kLineId': 1620001, 'timestamp': '2024-05-01 21:55:00', 'price': 2328.21}, {'kLineId': 1621230, 'timestamp': '2024-05-01 23:00:00', 'price': 2306.95}, {'kLineId': 1621854, 'timestamp': '2024-05-01 23:35:00', 'price': 2320.48}]
        res1, res2 = difference1(ls1, ls2)
        for i in res1:
            tmp = lst1
            tmp['data'] = i
            result.append(tmp)
        for i in res2:
            tmp = lst2
            tmp['data'] = i
            result.append(tmp)
        return result
    if data_type == 'bmp':
        ls1 = lst1['data']
        ls2 = lst2['data']
        result = lst1
        result['data'] = difference2(ls1, ls2)
        return result
    if data_type == 'text':

        ls1 = lst1['data']
        ls2 = lst2['data']
        result = lst1
        result['data'] = difference2(ls1, ls2)
        return result

def difference1(lst1, lst2):  # 左右两边的数据没有比较
    common_elements = [item for item in lst1 if item in lst2]
    # print(common_elements)
    # 初始化结果列表
    result1 = []
    result2 = []
    # 遍历公共元素对
    for i in range(len(common_elements) - 1):
        start = common_elements[i]
        end = common_elements[i + 1]
        # 找到start和end在a1_tuples中的索引，并获取它们之间的子数组
        start_index_a1 = lst1.index(start)
        end_index_a1 = lst1.index(end)
        subarray_a1 = lst1[start_index_a1: end_index_a1+1]
        # 找到start和end在a2_tuples中的索引，并获取它们之间的子数组
        start_index_a2 = lst2.index(start)
        end_index_a2 = lst2.index(end)
        subarray_a2 = lst2[start_index_a2: end_index_a2+1]
        # 如果两个子数组不同，则将[start, end]添加到结果中

        # print(subarray_a1, subarray_a2)
        if subarray_a1 != subarray_a2:
            result1 += [subarray_a1]
            result2 += [subarray_a2]
            # result.append([subarray_a1, subarray_a2])
    if lst1[0] != lst2[0]:
        pass
    if lst1[-1] != lst2[-1]:
        end = common_elements[-1]
        end_index_a1 = lst1.index(end)
        result1.append(lst1[end_index_a1-1:])
        end_index_a2 = lst2.index(end)
        result2.append(lst2[end_index_a2-1:])

    if len(common_elements) == 0:
        result1 = [lst1]
        result2 = [lst2]

    return result1, result2


def difference2(lst1, lst2):
    return symmetric_difference(lst1, lst2)
