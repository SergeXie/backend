import ast
import json
import os
import random
import re
import sys
import traceback
import shutil
from collections import defaultdict, namedtuple
import chardet
import backtrader as bt
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy import select, desc, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response
from apis.v1.platform import model_classes
from common.log import log
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.dql_platform import DqlStrategyTestResult, DqlStrategy, DqlIndicators, TradingStrategy, DplGoodsTest
from schemas.platorm_strategr_schemas import TestResultRequest
from utils.common import fetch_trading_data, PandasData, get_entities_list, generate_random_string, \
    generate_lazy_pinyin, indicator_classes, \
    to_float, format_datetime, select_goods_common, select_kline_data
from utils.public_strategy import ComprehensiveAnalyzer
from utils.strategys import reload_strategies
from task_dramatiq.dramatiq_strategy import task_run_backtest
from utils.trader_report_calculate import extract_transactions, generate_trader_report, normalize_to_float, data_filters
from dateutil import parser

router = APIRouter()


strategy_classes = {}
strategy_classes = reload_strategies()


UPLOAD_DIRECTORY = os.path.join("utils", "strategys")

prefix = "http://127.0.0.1:8081/api/v1/platform/strategy/"


def get_absolute_path(relative_path):
    """ 获取文件的绝对路径 """
    if hasattr(sys, '_MEIPASS'):
        file_path = os.path.join(sys._MEIPASS, relative_path)
        file_path = file_path.replace("\\dist\\main\\_internal", "")
        return file_path

    return os.path.join(os.path.abspath("."), relative_path)


def get_param(file_path):

    params_list = []
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    start_end_pattern = re.compile(r'# <start>(.*?)# <end>', re.DOTALL)
    start_end_match = start_end_pattern.search(content)

    if start_end_match:
        params_content = start_end_match.group(1)
        param_pattern = re.compile(r'#\s*@param\(([^)]+)\)')
        param_matches = param_pattern.findall(params_content)

        # 解析匹配到的@param注释，并存储到列表中
        for match in param_matches:
            # 拆分参数
            key_value_pairs = [pair.strip() for pair in match.split(',') if pair.strip()]
            param_dict = {}
            for pair in key_value_pairs:
                k, v = pair.split('=')
                param_dict[k.strip()] = v.strip().strip('"\'')  # 移除可能存在的引号

            # 转换默认值
            if param_dict['type'] == 'float':
                param_dict['defaultValue'] = float(param_dict['defaultValue'])
            # 添加到列表
            params_list.append(param_dict)

    return params_list


async def fetch_indicators(db: AsyncSession, uid: int):
    select_indicators = await db.execute(select(DqlStrategy).where(
        DqlStrategy.uid == uid, DqlStrategy.is_delete == 0))
    return select_indicators.scalars().first()


async def create_strategy_record(db: AsyncSession, indicator_data_request, strategys):
    """
    :param db: 数据库会话
    :param indicator_data_request: 请求参数
    :param strategys:  策略对象
    :return:
    """
    try:
        # 创建策略结果记录
        add_strategy_record = DqlStrategyTestResult(
            uid=generate_random_string("TR"),
            title=strategys.name,
            notes=strategys.description,
            strategyUid=indicator_data_request.get("uid", 0),
            goodsId=indicator_data_request["goods"],
            period=indicator_data_request["period"],
            startTime=indicator_data_request["startTime"],
            endTime=indicator_data_request["endTime"],
            traderResult="{}",
            parameter=json.dumps(indicator_data_request.get("parameter", {})),
            isBursted=0, status=0, yieldRate=0,
            mdr=0, winRate=0, plr=0, tradeCount=0,
            pnl=0,maxProfit=0, maxLoss=0, avgProfit=0, maxFUR=0, score=0,
            is_delete=0, spread=indicator_data_request.get("spread", 0),
            leverage=indicator_data_request.get("leverage", 1),
            paramsStrName=indicator_data_request.get("paramsStrName", None),
            newReportTemplate=json.dumps(indicator_data_request.get("newReportTemplate", {}))
        )
        db.add(add_strategy_record)
        await db.commit()
        return add_strategy_record.uid

    except Exception as e:
        info = traceback.format_exc()
        log.error("策略存储插入数据库失败：{}".format(info))
        await db.rollback()  # 如果发生异常，回滚事务
        await db.close()
        return None


async def run_backtest(db: AsyncSession, indicator_data_request, strategys, tester_uid, goods_data, task_name=None):
    """

    :param db: 会话
    :param indicator_data_request: 请求参数
    :param strategys: 策略对象
    :param tester_uid: 策略接口uid
    :param task_name: 任务名称
    :return:
    """
    try:
        # 根据period参数的取值进行条件判断
        period_dict = {"period": indicator_data_request.get("period", None),
                       "tradingGoods": indicator_data_request.get("goods", None),
                       "beginTime": indicator_data_request.get("startTime", None),
                       "endTime": indicator_data_request.get("endTime", None)}

        period_tuple = tuple(period_dict.items())

        indicator_params = indicator_data_request.get("parameter", {})
        # 在参数中增加k线的品种和周期
        indicator_params['Kline_period'] = indicator_data_request.get("period", None)
        indicator_params['Kline_goods'] = indicator_data_request.get("goods", None)

        trading_data = await fetch_trading_data(db, indicator_data_request.get("goods", None),
                                                indicator_data_request.get("period", None), model_classes,
                                                begin_time=indicator_data_request.get("startTime", None),
                                                end_time=indicator_data_request.get("endTime", None),
                                                period_tuple=period_tuple, class_name=json.loads(strategys.className))

        if not trading_data:
            return

        # 创建backtrader大脑实例
        cerebro = bt.Cerebro()

        # 启用 cheat-on-close 让市价单在当前K线收盘执行
        cerebro.broker.set_coc(True)  # 允许市价单在当前K线收盘价执行

        # 数据源处理
        df = pd.DataFrame(trading_data)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        data = PandasData(dataname=df)

        # 添加数据源
        cerebro.adddata(data)
        # strategys.className 存储的是列表类型
        for class_name in json.loads(strategys.className):
            # 加载策略goodsId
            cerebro.addstrategy(strategy_classes.get(class_name), indicator_params,
                                goodsId=indicator_data_request.get("goods", None),
                                begin_time=indicator_data_request.get("startTime", None),
                                baseLots=goods_data.baseLots)

        Indicators_subType = None
        # 指标数据
        if indicator_classes.get(strategys.indicatorsClassName):
            query = await db.execute(select(DqlIndicators).where(
                DqlIndicators.className == strategys.indicatorsClassName))

            DqlIndicators_result = query.scalars().first()
            Indicators_subType = DqlIndicators_result.subType
            cerebro.addstrategy(indicator_classes.get(strategys.indicatorsClassName),
                                indicator_params, indicator_name=None, comments=None,
                                begin_time=indicator_data_request.get("startTime", None))

        # 综合分析器
        cerebro.addanalyzer(ComprehensiveAnalyzer, _name='comprehensive')
        # 添加最大回撤分析器
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

        # 设置初始资金
        cerebro.broker.set_cash(float(indicator_data_request.get("initialCash", 10000)))

        # mult 合约单位100  leverage 杠杆
        cerebro.broker.setcommission(
            commission=indicator_data_request.get("commission", 0),
            mult=goods_data.profitRatio, leverage=indicator_data_request.get("leverage", 1))

        if indicator_data_request.get("spread", 0):
            # 设置滑点/点差
            cerebro.broker.set_slippage_fixed(fixed=indicator_data_request.get("spread", 0) / 100)

        result = cerebro.run(stdstats=True, tradehistory=True)
        # 获取最大回撤信息
        drawdown = result[0].analyzers.drawdown.get_analysis()

        # 回测结果
        trader_return = result[0].get_analysis()

        traderResult = trader_return.get('trader_result')
        traderReport = trader_return.get('trader_report')
        floatingPointValues = trader_return.get('floating_point_values')
        netAssetValues = trader_return.get('net_asset_values')
        newReportTemplate = result[0].analyzers.comprehensive.get_analysis()
        try:
            indicator_result_data = result[1].get_analysis()
            indicator_data_dict = {
                "startPoint": indicator_result_data[1],
                "endPoint": indicator_result_data[2],
                "buyselldata": indicator_result_data[3] if len(indicator_result_data[3:4]) > 0 else {},
                "data": indicator_result_data[0],
                "subType": Indicators_subType
            }
        except Exception as e:
            indicator_data_dict = {}

        traderReport["maxFUR"] = float(format(drawdown.max.drawdown, f".{int(2)}f"))
        traderReport["mdr"] = float(format(drawdown.max.drawdown, f".{int(2)}f"))
        return {"traderResult": traderResult, "traderReport": traderReport,
                "floatingPointValues": floatingPointValues, "netAssetValues": netAssetValues,
                "indicatorResult": indicator_data_dict,
                "newReportTemplate": newReportTemplate}

    except Exception as e:
        info = traceback.format_exc()
        log.error("策略结果插入数据库失败：{}".format(info))
        await db.rollback()  # 如果发生异常，回滚事务
        await db.close()
        return None


@router.get("/list", name="获取所有策略列表")
async def strategy_list(pageNo: int = Query(1), pageSize: int = Query(100),
                        orderBy: int = Query(0), keyWord: str = Query('%')):

    """
    :param pageNo:
    :param pageSize:
    :param orderBy:
    :param keyWord:
    :return:
    """

    return await get_entities_list(DqlStrategy, pageNo, pageSize, orderBy, keyWord)


@router.get("/viewCode", name="查看源代码")
async def view_strategy_code(uid: str):
    """
    :param uid: 策略uid
    :return:
    """

    try:
        async with async_db_session() as db:
            result = await db.execute(select(DqlStrategy).where(DqlStrategy.uid == uid))
            file_record = result.scalars().first()

            if not file_record:
                return await response_base.fail(code=400, msg="File not found")

            file_path = file_record.codeFilePath

            try:
                absolute_file_path = get_absolute_path(file_path)
                print(absolute_file_path)

                # Detect the file encoding
                with open(absolute_file_path, 'rb') as file:
                    raw_data = file.read()
                    result = chardet.detect(raw_data)
                    encoding = result['encoding']

                # Read the file with the detected encoding
                with open(absolute_file_path, 'r', encoding=encoding) as file:
                    content = file.read()

            except FileNotFoundError:
                return await response_base.fail(code=400, msg="File not found on the server")
            except UnicodeDecodeError as e:
                return await response_base.fail(code=400, msg=f"Error reading file: {str(e)}")
            except Exception as e:
                log.info("系统错误：{}".format(e))
                return Response(status_code=500, content="系统错误")

            return await response_base.success(data={"code": content})

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"获取文件内容错误：{info}")
        return Response(status_code=500, content="系统错误")


@router.post("/custom/upload", name="自定义策略文件上传")
async def upload_file(file: UploadFile = File(...)):
    """
    :param file:
    :return:
    """

    try:
        # # Get original filename and file extension
        original_filename = file.filename
        name, ext = os.path.splitext(original_filename)

        # Create a new filename with timestamp and random number
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_number = random.randint(1000, 9999)
        new_filename = f"{name}_{timestamp}_{random_number}{ext}"

        # Check if the file already exists
        absolute_file_path = get_absolute_path(f"utils/strategys/{new_filename}")
        print(absolute_file_path)
        with open(absolute_file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        with open(absolute_file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        try:
            ast.parse(code)  # 判读文件是否存在语法错误
        except SyntaxError as e:
            return await response_base.fail(code=400, msg=f"代码语法错误：{e}")

        global strategy_classes
        strategy_classes = reload_strategies()

        return await response_base.success(data={
            "path": f"utils/strategys/{new_filename}", "prefix": prefix})

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"上传文件错误：{info}")
        return Response(status_code=500, content="系统错误")


@router.post("/custom/update", name="自定义策略更新")
async def upload_file_update(request: Request):
    """
    :param request:
    :return:
    """
    try:
        print(request)
        request_data = await request.json()
        uid = request_data.get("uid", None)
        name = request_data.get("name", None)
        description = request_data.get("description", None)
        path = request_data.get("path", None)
        className = request_data.get("className", None)
        if className:
            className = className.split(",")

        if uid:
            if not path:
                return await response_base.fail(code=400, msg="请求参数不存在！")
        if not uid:
            if not name or not description or not path or not className:
                return await response_base.fail(code=400, msg="请求参数不存在！")

        absolute_file_path = get_absolute_path(path)
        filename_with_extension = os.path.basename(path)
        filename, _ = os.path.splitext(filename_with_extension)

        parameters = get_param(absolute_file_path)

        async with async_db_session() as db:
            # 查询策略是否存在
            query = await db.execute(select(DqlStrategy).where(DqlStrategy.uid == uid))
            new_strategy = query.scalars().first()

            if new_strategy:
                if new_strategy.type == 0:
                    return await response_base.fail(code=400, msg="系统策略不可更改!")

                # 更新策略信息
                # split_result = new_strategy.className.replace('.', ',.,').split(',')
                new_strategy.codeFilePath = path
                # new_strategy.className = filename + "." + split_result[2]
                new_strategy.createTime = datetime.now()
            else:
                # 创建新的策略
                new_strategy = DqlStrategy(
                    uid=generate_random_string("CS"),
                    name=name,
                    className=json.dumps([filename + "." + class_name for class_name in className]),
                    description=description,
                    parameters=json.dumps(parameters),
                    type=1,
                    owner="sys",
                    is_delete=0,
                    codeFilePath=path,
                    pinyinname=generate_lazy_pinyin(name),
                    weights=random.randint(1, 100)
                )
                db.add(new_strategy)

            await db.commit()
            await db.refresh(new_strategy)

        return await response_base.success(data={
            "path": f"{new_strategy.codeFilePath}", "prefix": prefix})

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"更新策略错误：{info}")
        await db.rollback()  # 如果发生异常，回滚事务
        return Response(status_code=500, content="系统错误")


@router.post("/testResultList", name="历史回测列表")
async def test_result_list(params: TestResultRequest):
    """
    :param pageNo:
    :param pageSize:
    :param goods:
    :param period:
    :param strategyUid:
    :param orderBy:
    :return:
    """

    order_dict = {
        0: DqlStrategyTestResult.createTime.desc(),
        1: DqlStrategyTestResult.yieldRate,
        -1: desc(DqlStrategyTestResult.yieldRate),
        2: DqlStrategyTestResult.mdr,
        -2: desc(DqlStrategyTestResult.mdr),
        3: DqlStrategyTestResult.winRate,
        -3: desc(DqlStrategyTestResult.winRate),
        4: DqlStrategyTestResult.plr,
        -4: desc(DqlStrategyTestResult.plr),
    }

    async with async_db_session() as db:

        query = select(
            DqlStrategyTestResult.uid,
            DqlStrategyTestResult.strategyUid,
            DqlStrategyTestResult.goodsId,
            DqlStrategyTestResult.period,
            DqlStrategyTestResult.parameter,
            DqlStrategyTestResult.startTime,
            DqlStrategyTestResult.endTime,
            DqlStrategyTestResult.createTime,
            DqlStrategyTestResult.tradeCount,
            DqlStrategyTestResult.pnl,
            DqlStrategyTestResult.plr,
            DqlStrategyTestResult.winRate,
            DqlStrategyTestResult.yieldRate,
            DqlStrategyTestResult.avgProfit,
            DqlStrategyTestResult.mdr,
            DqlStrategyTestResult.isBursted,
            DqlStrategyTestResult.maxFUR,
            DqlStrategyTestResult.score,
            DqlStrategyTestResult.paramsStrName,
            DqlStrategyTestResult.weight,
            DqlStrategyTestResult.weightNotes,
            DqlStrategyTestResult.status,
            DqlStrategyTestResult.title,
            DqlStrategyTestResult.traderReportType,
            DqlStrategyTestResult.maxProfit,
            DqlStrategyTestResult.maxLoss,
        ).where(
            DqlStrategyTestResult.is_delete == 0,
            DqlStrategyTestResult.status == params.status
        )

        if params.trader_report_type:
            if params.trader_report_type == 3:  # 系统
                query = query.where(DqlStrategyTestResult.traderReportType == None)
            else:
                query = query.where(DqlStrategyTestResult.traderReportType == params.trader_report_type)
        if params.goods != '%':
            query = query.where(DqlStrategyTestResult.goodsId.like(params.goods))

        if params.period != '%':
            query = query.where(DqlStrategyTestResult.period.like(params.period))

        if params.strategy_uid != '%':
            query = query.where(DqlStrategyTestResult.strategyUid == params.strategy_uid)

        # 处理筛选条件
        filter_mapping = {
            ">=": lambda field, val: field >= val,
            "<=": lambda field, val: field <= val,
            ">": lambda field, val: field > val,
            "<": lambda field, val: field < val,
            "=": lambda field, val: field == val,
        }

        # "screens":[{"name":"winRate","nameValue":">=","value":5}]
        for screen in params.screens:
            field = getattr(DqlStrategyTestResult, screen.name, None)
            if field and screen.nameValue in filter_mapping:
                query = query.where(filter_mapping[screen.nameValue](field, screen.value))

        # 计算总数
        total_count = await db.scalar(select(func.count()).select_from(query.subquery()))

        # 分页与排序
        offset = (params.page_no - 1) * params.page_size
        query = query.order_by(desc(DqlStrategyTestResult.weight), order_dict[params.order_by])
        query = query.offset(offset).limit(params.page_size)

        # 定义字段名称
        TestResult = namedtuple("TestResult", [
            "uid", "strategyUid", "goodsId", "period", "parameter", "startTime",
            "endTime", "createTime", "tradeCount", "pnl", "plr", "winRate", "yieldRate", "avgProfit",
            "mdr", "isBursted", "maxFUR", "score", "paramsStrName", "weight",
            "weightNotes", "status", "title", "traderReportType", "maxProfit", "maxLoss"
        ])

        results = (await db.execute(query)).fetchall()
        results = [TestResult(*data) for data in results]  # 把元组转换为 namedtuple

        # 处理查询结果
        results_list = [
            {
                "testerUids": data.uid,
                "strategyUid": data.strategyUid,
                "goods": data.goodsId,
                "period": data.period,
                "parameter": json.loads(data.parameter),
                "startTime": data.startTime.strftime('%Y-%m-%d %H:%M:%S'),
                "endTime": data.endTime.strftime('%Y-%m-%d %H:%M:%S'),
                "createTime": data.createTime.strftime('%Y-%m-%d %H:%M:%S'),
                "totalTrades": data.tradeCount,
                "pnl": data.pnl,
                "plr": data.plr,
                "winRate": data.winRate,
                "yieldRate": data.yieldRate,
                "avgProfit": data.avgProfit,
                "mdr": data.mdr,
                "isBursted": data.isBursted,
                "maxFUR": data.maxFUR,
                "score": data.score,
                "paramsStrName": data.paramsStrName,
                "weight": data.weight,
                "weightNotes": data.weightNotes,
                "status": data.status,
                "name": data.title,
                "traderReportType": data.traderReportType,
                "largestProfit": data.maxProfit,  # 最大每手盈利
                "largestLoss": data.maxLoss  # 最大每手亏损
            }
            for data in results
        ]

        return {
            "code": 200,
            "message": "Success",
            "pageNo": params.page_no,
            "pageSize": params.page_size,
            "data": results_list,
            "total": total_count,
        }


@router.post("/fetchTesterResult", name="获取回测结果")
async def fetch_tester_result(request: Request):
    """
    :param request:
    :return:
    """

    data_request = await request.json()

    testerUids = data_request.get("testerUids", [])
    try:
        async with async_db_session() as db:
            result_data = []
            # 根据 testerUids 查询历史回测结果
            query = await db.execute(select(
                DqlStrategyTestResult).where(
                DqlStrategyTestResult.uid.in_(testerUids),
                DqlStrategyTestResult.is_delete == 0,
                DqlStrategyTestResult.calculationStatus == 1))

            dql_strategy_test_result_all = query.scalars().all()

            for data in dql_strategy_test_result_all:
                trader_result = json.loads(data.traderResult)
                data_dict = dict()
                data_dict["testerUids"] = data.uid
                data_dict["name"] = data.title
                data_dict["goods"] = data.goodsId
                data_dict["period"] = data.period
                data_dict["leverage"] = 0
                data_dict["initialCash"] = 0
                data_dict["startTime"] = data.startTime.strftime('%Y-%m-%d %H:%M:%S')
                data_dict["endTime"] = data.endTime.strftime('%Y-%m-%d %H:%M:%S')
                data_dict["parameter"] = json.loads(data.parameter)
                data_dict["paramsStrName"] = data.paramsStrName
                data_dict["account"] = None
                data_dict["userName"] = None
                data_dict["currency"] = "USD"
                data_dict["leverage"] = data.leverage
                data_dict["spread"] = data.spread
                data_dict["traderResult"] = trader_result.get("traderResult", [])
                data_dict["traderReport"] = trader_result.get("traderReport", [])
                data_dict["indicatorResult"] = json.loads(data.indicatorResult) if data.indicatorResult else None
                data_dict["floatingPointValues"] = trader_result.get("floatingPointValues", [])
                data_dict["netAssetValues"] = trader_result.get("netAssetValues", [])
                data_dict["status"] = data.status
                data_dict["weight"] = data.weight
                data_dict["weightNotes"] = data.weightNotes
                data_dict["newReportTemplate"] = json.loads(data.newReportTemplate) if data.newReportTemplate else None
                data_dict["createTime"] = data.createTime.strftime('%Y-%m-%d %H:%M:%S')
                data_dict["traderReportType"] = data.traderReportType

                result_data.append(data_dict)

            return await response_base.success(data=result_data)

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"获取回测结果错误：{info}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@router.post("/fetchFloatingProfit", name="获取回测时间范围内浮动盈亏")
async def fetch_floating_profit(request: Request):

    try:
        data_request = await request.json()

        testerUids = data_request.get("testerUids", [])  # 策略UID

        async with async_db_session() as db:
            # 根据 testerUids 查询历史回测结果 取得回测时间
            query = await db.execute(select(
                DqlStrategyTestResult).where(
                DqlStrategyTestResult.uid.in_(testerUids),
                DqlStrategyTestResult.is_delete == 0,
                DqlStrategyTestResult.calculationStatus == 1))

            dql_strategy_test_result_all = query.scalars().all()

            result_list = []  # 存储最终的浮动盈亏数据

            for data in dql_strategy_test_result_all:
                trader_result = json.loads(data.traderResult)

                starting_cash = trader_result.get("traderReport", {}).get("startingCash", 10000)  # 起始资金

                # 订单记录 trader_orders
                trader_orders = trader_result.get("traderResult", [])

                # 拿起始时间-结束时间获取K线
                start_time = data.startTime.strftime('%Y-%m-%d %H:%M:%S')
                end_time = data.endTime.strftime('%Y-%m-%d %H:%M:%S')
                select_model_class, goods_ = await select_goods_common(db, data.goodsId, model_classes)
                if not select_model_class:
                    return await response_base.fail(msg="交易品种:{}未查询到".format(data.goodsId), data=[])

                db_select_kline = select(select_model_class).where(
                    select_model_class.tradingGoods == goods_.trading_goods,
                    select_model_class.platform == goods_.platform,
                    select_model_class.type == data.period,
                    select_model_class.tradeDateTime.between(start_time, end_time))

                kline_datas = await select_kline_data(db, db_select_kline)

                # === 初始化变量 ===
                floating_pnl_list = []  # 存储浮动盈亏数据

                # 查找closeTime等于null的（持仓单子）
                new_trader_orders = [x for x in trader_orders if x.get("closeTime", None)]
                # 使用集合跟踪已出现的 tradeid
                seen_tradeids = set()
                # 生成新列表，仅包含 closeTime 为空的记录，且 tradeid 不重复
                unique_open_trades = []
                for trade_id in new_trader_orders:
                    seen_tradeids.add(trade_id["tradeid"])

                for trade in trader_orders:
                    if trade.get("closeTime", None):
                        unique_open_trades.append(trade)
                    elif not trade.get("closeTime", None) and trade.get("tradeid", None) not in seen_tradeids:
                        unique_open_trades.append(trade)

                starting_cash = normalize_to_float(starting_cash)
                # === 遍历 K 线计算浮动盈亏 ===
                for kline in kline_datas:
                    current_price = kline["close"]  # K 线收盘价
                    current_date = kline["timestamp"]  # K 线时间
                    net_value = starting_cash  # 每根 K 线初始净值
                    profit = 0  # 初始化浮动盈亏
                    # 遍历所有交易订单，按时间顺序执行
                    for trade in unique_open_trades:
                        order_type = trade["orderType"]
                        close_time = trade.get("closeTime", None)
                        open_time = trade.get("openTime", None)
                        if open_time:
                            open_time = open_time
                        else:
                            open_time = trade.get("timestamp", None)
                        order_size = trade.get("size", None)
                        open_price = trade.get("openPrice", None)

                        if close_time:
                            # 计算浮动盈亏（持仓未平仓）
                            if open_time < current_date and close_time > current_date:
                                position = 1 if order_type == "buy" else -1
                                net_value = net_value + (current_price - open_price) * position * order_size * goods_.profitRatio

                            # 计算已实现盈亏（已平仓）
                            if close_time and close_time <= current_date:
                                net_value += trade["pnl"]

                        if open_time:
                            if open_time < current_date and not close_time:
                                position = 1 if order_type == "buy" else -1
                                net_value = net_value + (current_price - open_price) * position * order_size * goods_.profitRatio

                    # 存储当前时间的浮动盈亏
                    floating_pnl_list.append({
                        "timestamp": current_date,
                        "pnl": round(profit, 2),
                        "netValue": round(net_value, 2)
                    })

                # === 返回最终计算结果 ===
                result_list.append({
                    "testerUid": data.uid,
                    "floatingPnl": floating_pnl_list
                })

            return await response_base.success(data=result_list)

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"获取回测时间范围内浮动盈亏错误：{info}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@router.post("/syncBatchTest", name="策略批量回测(同步)")
async def indicator_sync_batch_test(request: Request):
    strategy_data_requests = await request.json()

    print("回测请求的参数：{}".format(strategy_data_requests))
    async with async_db_session() as db:
        result_data = []
        for strategy_data_requests in strategy_data_requests:
            strategy = await fetch_indicators(db, strategy_data_requests.get("uid", 0))

            if not strategy:
                return await response_base.fail(msg=f"uid:{strategy_data_requests.get('uid', 0)} not found !", data=[])

            # 根据品种或者品种表的手数和盈亏倍率
            dp_goods_data = await db.execute(select(DplGoodsTest).where(
                DplGoodsTest.goods == strategy_data_requests.get("goods")))

            goods_data = dp_goods_data.scalars().first()

            backtest_result = await run_backtest(db, strategy_data_requests, strategy, 0, goods_data, task_name="sync")

            if backtest_result is None:
                continue

            strategy_data_requests["account"] = None
            strategy_data_requests["userName"] = None
            strategy_data_requests["currency"] = "USD"
            traderResult = backtest_result["traderResult"]
            traderReport = backtest_result["traderReport"]
            strategy_data_requests["floatingPointValues"] = backtest_result["floatingPointValues"]
            strategy_data_requests["netAssetValues"] = backtest_result["netAssetValues"]
            strategy_data_requests["traderResult"] = traderResult
            strategy_data_requests["traderReport"] = traderReport
            strategy_data_requests["indicatorResult"] = backtest_result["indicatorResult"]
            strategy_data_requests["newReportTemplate"] = backtest_result["newReportTemplate"]

            try:
                tester_uid = await create_strategy_record(db, strategy_data_requests, strategy)

                await db.execute(
                    update(DqlStrategyTestResult).where(DqlStrategyTestResult.uid == tester_uid).values(
                        traderResult=json.dumps({"traderResult": traderResult,
                                                 "traderReport": traderReport,
                                                 "floatingPointValues": backtest_result["floatingPointValues"],
                                                 "netAssetValues": backtest_result["netAssetValues"]}),
                        indicatorResult=json.dumps(backtest_result["indicatorResult"]),
                        yieldRate=traderReport.get("yieldRate", 0),
                        isBursted=traderReport.get("isBursted", 0),
                        mdr=traderReport.get("mdr", 0),
                        winRate=traderReport.get("winRate", 0),
                        pnl=traderReport.get("totalNetProfit", 0),
                        plr=traderReport.get("plr", 0),
                        tradeCount=traderReport.get("totalTrades", 0),
                        maxProfit=traderReport.get("largestProfit", 0),
                        maxLoss=traderReport.get("largestLoss", 0),
                        avgProfit=traderReport.get("avgProfit", 0),
                        maxFUR=traderReport.get("maxFUR", 0),
                        score=traderReport.get("totalTrades", 0),
                        paramsStrName=strategy_data_requests.get("paramsStrName", 0),
                        calculationStatus=1  # 计算回测结果状态

                    )
                )
                await db.commit()

            except Exception as e:
                info = traceback.format_exc()
                log.error("策略结果插入数据库失败信息：{}".format(info))
                log.error("请求参数信息：{}".format(strategy_data_requests))
                await db.rollback()  # 如果发生异常，回滚事务
                raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

            finally:
                await db.close()

            strategy_data_requests["testerUids"] = tester_uid
            strategy_data_requests["createTime"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            result_data.append(strategy_data_requests)

        return await response_base.success(data=result_data)


@router.post("/asyncBatchTest", name="策略批量回测(异步)")
async def indicator_async_batch_test(request: Request):
    strategy_data_requests = await request.json()

    async with async_db_session() as db:
        result_data = []

        for strategy_data_requests in strategy_data_requests:
            strategy = await fetch_indicators(db, strategy_data_requests.get("uid", 0))

            if not strategy:
                return await response_base.fail(msg=f"uid:{strategy_data_requests.get('uid', 0)} not found !", data=[])

            tester_uid = await create_strategy_record(db, strategy_data_requests, strategy)

            # background_tasks.add_task(run_backtest, db, strategy_data_requests, strategy,
            #                          tester_uid, task_name="async")

            result_data.append({"index": strategy_data_requests.get("index"), "testerUid": tester_uid})

            strategy_data_requests["testerUids"] = tester_uid

            task_run_backtest.send(strategy_data_requests, tester_uid, task_name="async")

        return await response_base.success(data=result_data)


@router.get("/delete", name="策略删除")
async def strategy_delete(uid: str):
    """
    :param uid:  策略uid
    :return:
    """

    async with async_db_session() as db:
        # 查询策略表
        strategy_query = await db.execute(select(DqlStrategy).where(
            DqlStrategy.uid == uid, DqlStrategy.is_delete == 0))
        result = strategy_query.scalars().first()

        if result is None:
            return await response_base.fail(msg="策略不存在")

        if result.type == 0:
            return await response_base.fail(msg="系统策略不可删除")

        result.is_delete = 1
        await db.commit()

        return await response_base.success(msg="策略删除成功")


@router.get("/deleteTestResult", name="策略结果删除")
async def strategy_delete(uid: str):
    """
    :param uid:  策略uid
    :return:
    """

    async with async_db_session() as db:
        # 查询策略表
        strategy_result_query = await db.execute(select(
            DqlStrategyTestResult).where(DqlStrategyTestResult.uid == uid,
                                         DqlStrategyTestResult.is_delete == 0))

        result = strategy_result_query.scalars().first()

        if result is None:
            return await response_base.fail(msg="策略结果不存在")

        result.is_delete = 1
        await db.commit()

        return await response_base.success(msg="策略删除成功")


@router.post("/saveTestResult", name="策略结果入库")
async def save_test_result(request: Request):
    """
    返回：
    200： 直接入库
    400：与待入库存在时间交叉的其他回测结果
    """
    try:
        data_json = await request.json()
        uid = data_json.get("uid", None)  # 策略结果ID
        weight = data_json.get("weight", 0)  # 权重
        weightNotes = data_json.get("weightNotes", None)  # 权重备注
        print("请求参数：{}".format(data_json))

        async with async_db_session() as db:
            # 打开第一个表
            select_strategys1 = await db.execute(
                select(DqlStrategyTestResult)
                .where(DqlStrategyTestResult.uid == uid)
            )
            result1 = select_strategys1.scalars().first()

            if not result1:
                return await response_base.fail(msg="策略结果uid：{}不存在".format(uid))

            # 查询同策略、品种、周期、参数的其他回测结果
            select_strategys2 = await db.execute(
                select(DqlStrategyTestResult)
                .where(DqlStrategyTestResult.status == 1)
                .where(DqlStrategyTestResult.uid != uid)
                .where(DqlStrategyTestResult.strategyUid == result1.strategyUid)  # 策略相同
                .where(DqlStrategyTestResult.goodsId == result1.goodsId)  # 品种相同
                .where(DqlStrategyTestResult.period == result1.period)  # 周期相同
                .where(DqlStrategyTestResult.parameter == result1.parameter)  # 参数相同
            )
            result2 = select_strategys2.scalars().all()

            result_data = []
            if result2:
                for data in result2:
                    if (result1.endTime >= data.startTime) and (result1.startTime <= data.endTime):
                        result_data.append({"uid": data.uid,
                                            "tradeCount": data.tradeCount,
                                            "isBursted": data.isBursted,
                                            "yieldRate": data.yieldRate,
                                            "mdr": data.mdr,
                                            "parameter": json.loads(data.parameter),
                                            "createTime": data.createTime.strftime('%Y-%m-%d %H:%M:%S'),
                                            "winRate": data.winRate,
                                            "plr": data.plr,
                                            "maxProfit": data.maxProfit,
                                            "maxLoss": data.maxLoss,
                                            "avgProfit": data.avgProfit,
                                            "maxFUR": data.maxFUR,
                                            "score": data.score,
                                            "weight": weight,
                                            "weightNotes": weightNotes})

                        if data == result2[-1]:
                            return await response_base.fail(msg="存在可以合并回测结果", data=result_data)

                    else:  # 没有和已有数据重复就入库
                        result1.status = 1
                        result1.weight = weight
                        result1.weightNotes = weightNotes
                        await db.commit()
                        print("true1")
                        return {"code": 200, "msg": "Success", "uid": str(uid)}

            else:  # 没有重复直接入库
                result1.status = 1
                result1.weight = weight
                result1.weightNotes = weightNotes
                await db.commit()
                print("true2")
                return {"code": 200, "msg": "Success", "uid": str(uid)}

    except Exception as e:
        info = traceback.format_exc()
        log.error("策略结果入库数据库失败信息：{}".format(info))
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@router.post("/saveAllTestResult", name="策略结果全部入库")
async def save_all_test_result(request: Request):
    """
    接收策略结果ID列表和更新的权重信息，批量更新策略结果。
    :param request: 请求对象，包含策略结果ID列表和权重信息
    :return: 成功返回200，失败返回500
    """
    try:
        data_json = await request.json()
        uid_list = data_json.get("uids", [])  # 策略结果ID列表
        weight = data_json.get("weight", 1)  # 权重
        weightNotes = data_json.get("weightNotes", None)  # 权重备注

        async with async_db_session() as db:

            strategy_test_results = await db.execute(
                select(DqlStrategyTestResult)
                .where(DqlStrategyTestResult.uid.in_(uid_list),
                       DqlStrategyTestResult.status == 0)
            )

            results = strategy_test_results.scalars().all()

            if not results:
                return await response_base.fail(msg="策略结果存在入库状态!")

            for result in results:
                result.status = 1
                result.weight = weight
                result.weightNotes = weightNotes

            await db.commit()

            return {"code": 200, "msg": "Success", "uids": [result.uid for result in results]}

    except Exception as e:
        info = traceback.format_exc()
        log.error("策略结果全部入库数据库失败信息：{}".format(info))
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@router.post("/directlySaveTestResult", name="策略结果直接入库")
async def directly_test_result(request: Request):
    """
    返回：
    200： 直接入库
    400：与待入库存在时间交叉的其他回测结果
    """
    data_json = await request.json()
    uid = data_json.get("uid", None)
    weight = data_json.get("weight", 0)  # 权重
    weightNotes = data_json.get("weightNotes", None)  # 权重备注

    async with async_db_session() as db:
        # 打开第一个表
        select_strategys1 = await db.execute(
            select(DqlStrategyTestResult)
            .where(DqlStrategyTestResult.uid == uid)
        )

        result1 = select_strategys1.scalars().first()

        if not result1:
            return await response_base.fail(msg="策略结果uid：{}不存在".format(uid))

        result1.status = 1
        result1.weight = weight
        result1.weightNotes = weightNotes
        await db.commit()

        return {"code": 200, "msg": "Success", "uid": str(uid)}


@router.post("/combineTestResult", name="策略合并")
async def combine_test_result(request: Request):

    return await response_base.success()


@router.post("/traderReportUpload", name="策略交易报告上传")
async def trader_report_upload(file: UploadFile = File(...)):
    """
    策略交易报告上传
    """
    # 指定文件保存路径
    upload_directory = os.path.join("utils", "trader_report")
    os.makedirs(upload_directory, exist_ok=True)  # 确保保存目录存在

    # 检查文件类型（可根据需要自定义）
    allowed_extensions = {"htm"}
    file_extension = file.filename.split(".")[-1].lower()

    if file_extension not in allowed_extensions:
        return await response_base.fail(msg="不支持的文件类型")

    # 生成唯一文件名
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")  # 格式化当前时间为YYYYMMDDHHMMSS
    unique_filename = f"{file.filename.split('.')[0]}_{current_time}.{file_extension}"

    # 保存文件
    file_path = os.path.join(upload_directory, unique_filename)
    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())
    except Exception as e:
        return await response_base.fail(msg="文件保存失败!")

    return await response_base.success(data={"path": file_path})


@router.post("/submitTraderReport", name="提交交易报告")
async def submit_trader_report(request: Request, background_tasks: BackgroundTasks):
    """
    :param request:
    :return:
    """
    try:
        data_json = await request.json()
        file_path = data_json.get("file_path", None)  # 文件名
        uid = data_json.get("uid", None)  # 策略uid
        goods = data_json.get("goods", None)  # 交易品种
        period = data_json.get("period", None)  # 周期
        startTime = data_json.get("startTime", None)  # 开始时间
        endTime = data_json.get("endTime", None)  # 结束时间
        startTime = parser.parse(startTime).strftime('%Y-%m-%d %H:%M:%S')
        endTime = parser.parse(endTime).strftime('%Y-%m-%d %H:%M:%S')

        upload_type = data_json.get("uploadType", "0")  # 上传类型

        # 检查文件是否存在
        if not os.path.exists(file_path):
            return await response_base.fail(msg="文件路径不存在")

        # 检测文件编码
        with open(file_path, 'rb') as file:
            raw_data = file.read()
            encoding = chardet.detect(raw_data)['encoding']

        # 解析HTML
        with open(file_path, 'r', encoding=encoding) as file:
            soup = BeautifulSoup(file, 'html.parser')
        async with async_db_session() as db:
            account_list = []
            # 提取账户信息
            account_info_row = soup.find('tr', align='left')
            # 账户信息（保留部分）
            if account_info_row:
                account_info_columns = account_info_row.find_all('td')
                account = account_info_columns[0].text.replace('Account:', '').strip()
                name = account_info_columns[2].text.replace('Name:', '').strip()
                currency = account_info_columns[4].text.replace('Currency:', '').strip()

                leverage = '1'
                if len(account_info_columns) > 6:
                    leverage_text = account_info_columns[6].text.replace('Leverage:', '').strip()
                    if leverage_text:
                        leverage = leverage_text

                datetime_value = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if len(account_info_columns) > 12:
                    datetime_text = account_info_columns[12].text.strip()
                    if datetime_text:
                        parsed_datetime = datetime.strptime(datetime_text, '%Y %B %d, %H:%M')
                        datetime_value = parsed_datetime.strftime('%Y-%m-%d %H:%M:%S')

            # 查询策略
            if upload_type == "2":  # 手动上传需要判断！
                strategy = await fetch_indicators(db, uid)
                if not strategy:
                    return await response_base.fail(code=400, msg=f"提交失败,未找到存在策略！", data=[])

                closed_transactions_header = soup.find('b', string='Closed Transactions:')
                open_transactions_header = soup.find('b', string='Open Trades:')

                closed_transactions = extract_transactions(closed_transactions_header, stop_text='Closed P/L:')
                open_transactions = extract_transactions(open_transactions_header, stop_text='Floating P/L:')

                account_list.extend(closed_transactions)
                account_list.extend(open_transactions)

                filtered_result = data_filters(account_list, startTime, endTime)

                # 提取报告数据
                trader_report, additional_metrics, newReportTemplate = generate_trader_report(soup, filtered_result)

                try:
                    # 创建策略结果记录
                    add_strategy_record = DqlStrategyTestResult(
                        uid=generate_random_string("TR"),
                        title=strategy.name,
                        notes=strategy.description,
                        strategyUid=uid,
                        goodsId=goods,
                        period=period,
                        startTime=startTime,
                        endTime=endTime,
                        traderResult=json.dumps(
                            {
                                "traderResult": filtered_result,
                                "traderReport": trader_report,
                                "floatingPointValues": [],
                                "netAssetValues": []
                            }
                        ),
                        parameter=json.dumps(data_json.get("parameter", {})),
                        isBursted=0, status=0, yieldRate=trader_report["yieldRate"],
                        mdr=trader_report["mdr"], winRate=trader_report["winRate"],
                        plr=trader_report["plr"], tradeCount=additional_metrics["tradeCount"],
                        pnl=additional_metrics["pnl"], maxProfit=additional_metrics["maxProfit"],
                        maxLoss=additional_metrics["maxLoss"], avgProfit=trader_report["avgProfit"],
                        maxFUR=trader_report["max_fur"], score=0,
                        is_delete=0, spread=0,
                        leverage=leverage,
                        calculationStatus=1,
                        newReportTemplate=json.dumps(newReportTemplate),
                        traderReportType=2
                    )
                    db.add(add_strategy_record)
                    await db.commit()
                    log.info("手动上传交易报告入库成功：策略UID {}".format(strategy.uid))

                except Exception as e:
                    info = traceback.format_exc()
                    log.error("交易报告提交失败：{}".format(info))
                    await db.rollback()  # 如果发生异常，回滚事务
                    await db.close()
                    return await response_base.fail(msg="提交失败！错误信息：{}".format(e))

            else:
                # 自动解析HTML部分
                transactions = []
                grouped_transactions = defaultdict(list)
                rows = soup.find_all('tr', align='right')
                identifiers = []
                # 遍历所有交易行，提取交易信息
                for row in rows:
                    cols = row.find_all('td')
                    order_type = cols[2].text.strip().lower() if len(cols) > 2 else ''
                    if len(cols) >= 14 and order_type in ['buy', 'sell']:  # 检查列数，确保是交易数据行
                        if 'title' in cols[0].attrs:
                            transaction = {
                                'tradeid': cols[0].text.strip() if len(cols) > 0 else 0,
                                'timestamp': format_datetime(cols[1].text.strip()) if len(cols) > 1 else None,
                                'openTime': format_datetime(cols[1].text.strip()) if len(cols) > 1 else None,
                                'orderType': cols[2].text.strip() if len(cols) > 2 else '0',
                                'goodsId': cols[4].text.strip() if len(cols) > 4 else None,
                                'size': to_float(cols[3].text.strip()) if len(cols) > 3 else 0.0,
                                'openPrice': to_float(cols[5].text.strip()) if len(cols) > 5 else 0.0,
                                'stopLoss': to_float(cols[6].text.strip()) if len(cols) > 6 else 0.0,
                                'takeProfit': to_float(cols[7].text.strip()) if len(cols) > 7 else 0.0,
                                'closeTime': format_datetime(cols[8].text.strip()) if len(cols) > 8 else None,
                                'price': to_float(cols[9].text.strip()) if len(cols) > 9 else 0.0,
                                'commission': to_float(cols[10].text.strip()) if len(cols) > 10 else 0.0,
                                'taxes': to_float(cols[11].text.strip()) if len(cols) > 11 else 0.0,
                                'swap': to_float(cols[12].text.strip()) if len(cols) > 12 else 0.0,
                                'pnl': to_float(cols[13].text.strip()) if len(cols) > 13 else 0.0,
                                "keyid": cols[2].text.strip()
                            }
                            transactions.append(transaction)

                    elif len(cols) == 3:  # 如果是标识符行，保存标识符
                        identifiers.append(cols[2].text.strip())

                # 一一对应交易和标识符
                for transaction, identifier in zip(transactions, identifiers):
                    key = identifier.split('@')[0]  # 提取 @ 前面的部分 例如: NTROILM5S0001@1737024960@
                    transaction['identifier'] = identifier
                    grouped_transactions[key].append(transaction)

                if not grouped_transactions:
                    return await response_base.fail(msg="该文件不支持自动上传提交，未提取到关键信息部分")

                async with db.begin():  # 开启事务
                    # print("grouped_transactions:{}".format(grouped_transactions))
                    for identifier, orders in grouped_transactions.items():
                        filtered_result = data_filters(orders, startTime, endTime)

                        # 提取报告数据
                        trader_report, additional_metrics, newReportTemplate = generate_trader_report(soup, filtered_result)
                        # 添加入库
                        try:
                            # 自动上传，根据 trading_strategy_uid_list 进行查询交易策略表的uid
                            trading_strategy_db = await db.execute(select(TradingStrategy).filter(
                                TradingStrategy.tradeUid == identifier))

                            trading_strategy_datas = trading_strategy_db.scalars().first()
                            if not trading_strategy_datas:
                                continue
                            try:
                                # 计算回测指标
                                # ------回测指标部分--------
                                # 查询策略
                                strategys = await fetch_indicators(db, trading_strategy_datas.strategyUid)
                                # 查询范围数据
                                trading_data = await fetch_trading_data(
                                    db, trading_strategy_datas.goods,trading_strategy_datas.period, model_classes,
                                    begin_time=startTime,end_time=endTime, class_name=json.loads(strategys.className))
                                if not trading_data:
                                    continue

                                # 创建backtrader大脑实例
                                cerebro = bt.Cerebro()
                                # 数据源处理
                                df = pd.DataFrame(trading_data)
                                df['datetime'] = pd.to_datetime(df['datetime'])
                                df.set_index('datetime', inplace=True)
                                data = PandasData(dataname=df)

                                # 添加数据源
                                cerebro.adddata(data)

                                Indicators_subType = None
                                # 指标数据
                                indicator_params = {}
                                if indicator_classes.get(strategys.indicatorsClassName):
                                    query = await db.execute(select(DqlIndicators).where(
                                        DqlIndicators.className == strategys.indicatorsClassName))

                                    DqlIndicators_result = query.scalars().first()
                                    Indicators_subType = DqlIndicators_result.subType

                                    cerebro.addstrategy(indicator_classes.get(strategys.indicatorsClassName),
                                                        indicator_params, indicator_name=None, comments=None,
                                                        begin_time=startTime)

                                print("indicator_classes.get(strategys.indicatorsClassName):{}".format(indicator_classes.get(strategys.indicatorsClassName)))
                                # 综合分析器
                                cerebro.addanalyzer(ComprehensiveAnalyzer, _name='comprehensive')
                                # 添加最大回撤分析器
                                cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

                                # 运行backtrack
                                result = cerebro.run(stdstats=True, tradehistory=True)

                                # 指标回测数据
                                indicator_result_data = result[0].get_analysis()
                                indicator_data_dict = {
                                    "startPoint": indicator_result_data[1],
                                    "endPoint": indicator_result_data[2],
                                    "buyselldata": indicator_result_data[3] if len(
                                        indicator_result_data[3:4]) > 0 else {},
                                    "data": indicator_result_data[0],
                                    "subType": Indicators_subType
                                }
                            except Exception as e:
                                info = traceback.format_exc()
                                log.error("计算指标错误：{} 指标className:{}".format(
                                    info, indicator_classes.get(strategys.indicatorsClassName)))
                                indicator_data_dict = {}

                            # -------创建策略结果记录-------
                            add_strategy_record = DqlStrategyTestResult(
                                uid=generate_random_string("TR"),
                                title=strategys.name,
                                notes=strategys.description,
                                strategyUid=trading_strategy_datas.strategyUid,
                                goodsId=trading_strategy_datas.goods,
                                period=trading_strategy_datas.period,
                                startTime=startTime,
                                endTime=endTime,
                                traderResult=json.dumps(
                                    {
                                        "traderResult": filtered_result,
                                        "traderReport": trader_report,
                                        "floatingPointValues": [],
                                        "netAssetValues": []
                                    }
                                ),
                                indicatorResult=json.dumps(indicator_data_dict),
                                parameter=trading_strategy_datas.parameter,
                                isBursted=0, status=0, yieldRate=trader_report["yieldRate"],
                                mdr=trader_report["mdr"], winRate=trader_report["winRate"],
                                plr=trader_report["plr"], tradeCount=additional_metrics["tradeCount"],
                                pnl=additional_metrics["pnl"], maxProfit=additional_metrics["maxProfit"],
                                maxLoss=additional_metrics["maxLoss"], avgProfit=trader_report["avgProfit"],
                                maxFUR=trader_report["max_fur"], score=0,
                                is_delete=0, spread=0,
                                leverage=leverage,
                                calculationStatus=1,
                                newReportTemplate=json.dumps(newReportTemplate),
                                traderReportType=1

                            )
                            db.add(add_strategy_record)
                        except Exception as e:
                            info = traceback.format_exc()
                            log.error("交易报告提交失败：{}".format(info))
                            await db.rollback()  # 如果发生异常，回滚事务
                            await db.close()
                            return await response_base.fail(msg="提交失败！错误信息：{}".format(e))

            log.info("自动上传交易报告入库成功")
            return await response_base.success()

    except Exception as e:
        info = traceback.format_exc()
        log.error("提交交易报告入库数据库失败信息：{}".format(info))
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
