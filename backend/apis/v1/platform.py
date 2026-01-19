import calendar
import datetime
import json
import multiprocessing
import traceback
import uuid
from concurrent.futures import ProcessPoolExecutor
from typing import Optional
from fastapi import APIRouter, Query
from sqlalchemy import select, and_, update, func, or_
from starlette.requests import Request
from starlette.responses import Response
from common.log import log
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.dql_platform import DplGoodsTest, DqlIndicators, DqlStrategy, DqlPwdLink, DqlStrategyTestResult, DqlOrder, \
    DqlStrategyIndicatorRel
from schemas.base import ErrorModel
from schemas.platorm import GoodsResponse, AddTraderStrategyData, AddTraderTicksData, DqlIndicatorsModel
from services.dynamic_kline_service import DynamicKlineService
from services.indicatory_service import get_indicator_data_async
from utils.common import select_goods_common, RandomIDGenerator, select_kline_data, Trader, \
    GoodTrader, PandasData, cache, get_indicator_data, model_classes, \
    get_entities_list, generate_random_string, statistics_from_orders, adjust_unpaired_trades, filter_by_time
from utils.prod_backtrader import MyStrategy
from utils.timezone import timezone
import pandas as pd
from utils.indicators import *
from utils.trader_report_calculate import ManualComprehensiveAnalyzer

router = APIRouter()

executor = ProcessPoolExecutor(max_workers=multiprocessing.cpu_count())  # 可调并发数


@router.get("/getKlineCount", name="获取K线时间段数量")
async def get_kline_count(goods: str, period: str, beginTime: str, endTime: str):
    async with async_db_session() as db:
        select_model_class, result = await select_goods_common(db, goods, model_classes)

        if not select_model_class:
            return await response_base.fail(msg="数据库表未找到！", data=[])

        stmt = (
            select(func.count())
            .select_from(select_model_class)
            .where(
                select_model_class.tradingGoods == result.trading_goods,
                select_model_class.platform == result.platform,
                select_model_class.type == period,
                select_model_class.tradeDateTime.between(beginTime, endTime)  # 含头含尾
            )
        )

        res = await db.execute(stmt)
        total = res.scalar_one()

        return await response_base.success(data={"total": total})


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
        order_strategy = (await db.execute(select(DqlOrder).where(DqlOrder.strategyUid == strategyUid))).scalars().first()
        if not order_strategy:
            return await response_base.fail(msg="该策略不存在实时回测报告", data=[])

        # timestamp 关仓时间
        stmt = (
            select(DqlOrder)
            .where(
                and_(
                    DqlOrder.tradingGoods == goods,
                    DqlOrder.period == period,
                    DqlOrder.strategyUid == strategyUid,
                    # 这里是合并后的 or_ 逻辑
                    or_(
                        DqlOrder.openTime.between(beginTime, endTime),
                        DqlOrder.timestamp.between(beginTime, endTime)
                    )
                )
            )
            .order_by(DqlOrder.openTime.asc())
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return await response_base.fail(msg="时间范围内不存在实时回测报告", data=[])

        strategy = (await db.execute(select(DqlStrategy).where(DqlStrategy.uid == strategyUid))).scalars().first()

        strategy_indicator_rels = (await db.execute(select(
            DqlStrategyIndicatorRel).where(DqlStrategyIndicatorRel.sid == strategyUid))).scalars().first()
        indicatorDataList = list()

        indicatorData = (await db.execute(select(DqlIndicators).where(
            DqlIndicators.uid == strategy_indicator_rels.iid))).scalars().first()

        if indicatorData:
            indicator_dict = DqlIndicatorsModel.from_orm(indicatorData).dict()
            indicator_dict["parameters"] = json.loads(strategy_indicator_rels.indicatorParameter)
        else:
            indicator_dict = None

        indicatorDataList.append(indicator_dict)

        digits = (await db.execute(
            select(DplGoodsTest.digits).where(DplGoodsTest.goods == goods)
        )).scalars().first()

    # 需要格式化的所有时间字段
    time_fields = ['createTime', 'openTime', 'closeTime', 'timestamp']
    data = []
    for row in rows:
        d = row.__dict__.copy()
        d.pop('_sa_instance_state', None)
        for field in time_fields:
            if field in d and isinstance(d[field], datetime.datetime):
                d[field] = d[field].strftime('%Y-%m-%d %H:%M:%S')
        data.append(d)

    new_trader_result = filter_by_time(data, beginTime, endTime)

    traderResult = await adjust_unpaired_trades(db, beginTime, endTime, new_trader_result)

    trader_report, orders = statistics_from_orders(traderResult)

    analyzer = ManualComprehensiveAnalyzer()

    newReportTemplate = analyzer.get_analysis_from_result(orders)

    result_data = [{"goods": goods, "period": period, "startTime": beginTime, "endTime": endTime,
                    "name": strategy.name, "initialCash": 100000, "digits": digits, "parameter": None,
                    "paramsStrName": None, "account": None, "userName": None, "currency": "USD", "spread": 0,
                    "strategyUid": strategyUid,"testerUids": strategyUid, "traderReportType": 3,
                    "netAssetValues": trader_report["cashCurve"], "parameterList": json.loads(strategy.parameters),
                    "traderResult": traderResult, "traderReport": trader_report,
                    "indicatorData": indicatorDataList, "newReportTemplate": newReportTemplate}]

    return await response_base.success(data=result_data)


@router.get("/dynamicKline", name="动态0号K线")
async def get_dynamic_kline(
    goods: str = Query(..., title="交易平台-交易品种"),
    period: str = Query(..., title="周期"),
    startTime: str = Query(None, title="起始时间")
):
    async with async_db_session() as db:

        now = datetime.datetime.utcnow() + datetime.timedelta(hours=2)

        service = await DynamicKlineService.create(
            db=db,
            goods=goods,
            model_classes=model_classes
        )

        if not service:
            return await response_base.fail(
                msg="数据库表未找到！",
                data=[]
            )

        data = await service.get_dynamic_kline(
            period=period,
            start_time_str=startTime,
            now=now
        )

        return await response_base.success(data=data)


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
        return await response_base.success(data={"goods": goods, "period": period, "utc": result.utc, "lineData": result_list})


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
            return await response_base.success(data={"goods": goods, "period": period, "utc": result.utc,
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
        return await response_base.success(data={"goods": goods, "period": period, "utc": result.utc,
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

        return await response_base.success(data={"goods": goods, "period": period, "utc": result.utc,
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
    return await get_indicator_data_async(request, "FrontKline", executor, name="history")


@router.post("/indicatorAfterKLine", name="获取指标最新数据")
async def indicator_after_kline(request: Request):
    """
    :param request:
    :return:
    """

    return await get_indicator_data_async(request, "AfterKline", executor, name="latest")


@router.post("/indicatorGoodsPeriodKLines", name="获取指标时段数据")
async def indicator_goods_kline(request: Request):
    """
    :param request:
    :return:
    """
    return await get_indicator_data_async(request, "PeriodKLines", executor, name=None)


@router.post("/indicatorGoodsPeriodKLinesCopy", name="获取指标时段数据")
async def indicator_goods_kline(request: Request):
    """
    :param request:
    :return:
    """
    return await get_indicator_data_async(request, "PeriodKLines", executor, name=None)


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
