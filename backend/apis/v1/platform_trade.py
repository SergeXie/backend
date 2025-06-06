import json
import os
import traceback
import datetime
import traceback
import uuid
import pickle
import random
from enum import Enum

import holidays
from utils.timezone import timezone
import asyncio
import pandas as pd
from fastapi import APIRouter
from sqlalchemy import select
from starlette.requests import Request
from common.log import log
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.dql_platform import TradingStrategy, DqlStrategy, DplGoodsTest
from utils.common import generate_random_string
from fastapi import APIRouter, Query
from urllib.parse import parse_qs
from sqlalchemy import select, and_
from starlette.requests import Request
from starlette.responses import Response
from common.log import log
from database.db_mysql import async_db_session
from sqlalchemy import select, desc, update, func
from utils.common import select_goods_common, RandomIDGenerator, select_kline_data, Trader, \
    GoodTrader, PandasData, cache, get_indicator_data, model_classes, \
    get_entities_list
from models.dql_platform import DqlStrategyTestResult
from models.dql_platform import TradingStrategy
from sqlalchemy.ext.asyncio import AsyncSession
from utils.indicators import *
from typing import List, Dict, Optional
from datetime import datetime, timedelta, time
from utils.strategys import reload_strategies
from fastapi import BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import OperationalError
from apis.v1.platform_strategy import fetch_indicators, create_strategy_record
router = APIRouter()

file_path = './order_point.txt'


@router.post("/tradeStrategyCreate", name="交易策略生成")
async def trade_strategy_create(request: Request):
    """
    :param request:
    :return:
    """
    try:
        # 接收请求参数
        data_json = await request.json()
        strategyUid = data_json.get("strategyUid")
        data_json["parameter"] = json.dumps(data_json["parameter"])
        async with async_db_session() as db:
            # 查询策略
            result = await db.execute(select(DqlStrategy).where(DqlStrategy.uid == strategyUid))
            strategy = result.scalars().first()
            data_json["name"] = strategy.name

            # 生成到库中
            add_trading_strategy = TradingStrategy(**data_json)
            add_trading_strategy.tradeUid = generate_random_string("NTR")
            db.add(add_trading_strategy)
            await db.commit()

            data_json["parameter"] = json.loads(data_json["parameter"])

            return await response_base.success(data=dict(data_json))

    except Exception as e:
        info = traceback.format_exc()
        log.error("交易策略生成入库数据库失败信息：{}".format(info))
        return await response_base.fail(msg=f"An error occurred: {str(e)}")


@router.get("/tradeStrategyList", name="获取交易策略列表")
async def trade_result_list(request: Request):
    """
    :param request:
    :return:
    """
    try:
        async with async_db_session() as db:
            query = select(TradingStrategy)
            dql_strategy_all = await db.execute(query)
            results_list = dql_strategy_all.scalars().all()
            data_list = list()
            # 返回结果
            for data in results_list:
                data_dict = dict()
                data_dict["tradeUid"] = data.tradeUid
                data_dict["strategyUid"] = data.strategyUid
                data_dict["name"] = data.name
                data_dict["goods"] = data.goods
                data_dict["period"] = data.period
                # print(data.parameter)
                data_dict["parameter"] = json.loads(data.parameter)
                data_dict["createTime"] = data.createTime.strftime('%Y-%m-%d %H:%M:%S')

                data_list.append(data_dict)

        data = {"code": 200, "message": "Success", "data": data_list, "total": len(data_list)}

        return data

    except Exception as e:
        info = traceback.format_exc()
        return await response_base.fail(msg=f"An error occurred: {str(e)}", data=[])


# 控制后台任务是否继续运行的全局变量
keep_running = True
strategy_classes = {}
strategy_classes = reload_strategies()

strategy_clientid_dict = dict()  # 策略与订阅者的对应字典
# 更新订阅者

diaoqucishu = 500
period_Conversion_Seconds_dict = {
    'M1': 5,
    'M5': 5,
    'M15': 5,
    'M30': 5,
    'H1': 10,
    'H4': 10,
    'D1': 8640,
    'W1': 60480,
    'MN': 259200
}
async def run_backtest(db: AsyncSession, indicator_data_request, strategys, tester_uid, goods_data, task_name=None, ismoni=False):
    """
    :param db: 会话
    :param indicator_data_request: 请求参数
    :param strategys: 策略对象
    :param tester_uid: 策略接口uid
    :param task_name: 任务名称
    :return:
    """
    try:
        indicator_params = indicator_data_request.get("parameter", {})
        goods = indicator_data_request.get("goods", None)
        period = indicator_data_request.get("period", None)
        tradeUid = indicator_data_request.get("tradeUid", 0)

        trading_data = await fetch_trading_data(db, goods, period, model_classes, name="latest_new", tradeUid=tradeUid)
        if not trading_data:
            return

        cerebro = bt.Cerebro()
        cerebro.broker.setcommission(leverage=indicator_data_request.get("leverage", 1))
        df = pd.DataFrame(trading_data)
        if ismoni:
            global diaoqucishu
            df = df.iloc[0:diaoqucishu]
            diaoqucishu += 1
            # print('diaoqucishu', diaoqucishu)
            print(df.tail(1)['datetime'])


        df['datetime'] = pd.to_datetime(df['datetime'])
        last_datetime = df['datetime'].iloc[-1]
        df.set_index('datetime', inplace=True)
        data = PandasData(dataname=df)
        cerebro.adddata(data)
        for class_name in json.loads(strategys.className):
            # 加载策略goodsId
            cerebro.addstrategy(strategy_classes.get(class_name), indicator_params,
                                goodsId=indicator_data_request.get("goods", None),
                                begin_time=indicator_data_request.get("startTime", None),
                                baseLots=goods_data.baseLots)


        cerebro.broker.set_cash(indicator_data_request.get("initialCash", 10000000))
        result = cerebro.run(stdstats=True, tradehistory=True)

        # traderResult, traderReport = result[0].get_analysis()
        trader_return = result[0].get_analysis()
        traderResult = trader_return.get('trader_result')
        traderReport = trader_return.get('trader_report')
        order_point = trader_return.get('order_point', [])

        if task_name == "async":
            await db.execute(
                update(DqlStrategyTestResult).where(DqlStrategyTestResult.uid == tester_uid).values(
                    traderResult=json.dumps({"traderResult": traderResult, "traderReport": traderReport}),
                    yieldRate=traderReport.get("yieldRate", 0),
                    isBursted=traderReport.get("isBursted", 0),
                    mdr=traderReport.get("mdr", 0),
                    winRate=traderReport.get("winRate", 0),
                    pnl=traderReport.get("totalNetProfit", 0),
                    plr=traderReport.get("plr", 0),
                    tradeCount=traderReport.get("totalTrades", 0),
                    maxProfit=traderReport.get("largestProfit", 0),
                    maxLoss=traderReport.get("largestLoss", 0),
                    avgProfit=traderReport.get("AverageProfitLossPerorder", 0),
                    maxFUR=traderReport.get("maxFUR", 0),
                    score=traderReport.get("totalTrades", 0),
                )
            )
            await db.commit()
        else:
            return {"traderResult": traderResult,
                    "traderReport": traderReport,
                    "order_point": order_point,
                    "last_datetime": last_datetime}

    except Exception as e:
        info = traceback.format_exc()
        log.error("策略结果插入数据库失败：{}".format(info))
        await db.rollback()  # 如果发生异常，回滚事务
        await db.close()
        return None



def inverse(original_dict):
    # 转换后的字典
    converted_dict = {}
    # 遍历原始字典
    for class_label, objects in original_dict.items():
        for obj in objects:
            # 如果对象已经在转换后的字典中，追加类标签
            if obj in converted_dict:
                converted_dict[obj].append(class_label)
            # 如果对象不在转换后的字典中，创建新的键值对
            else:
                converted_dict[obj] = [class_label]
    return converted_dict


def generate_unique_12_digit_number():
    return ''.join([str(random.randint(0, 9)) for _ in range(12)])


original_dict: Dict[str, list] = {}
inverse_dict = {}
# 管理活跃的WebSocket连接和客户端唯一的clientid标识
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    # 链接函数
    async def connect(self, websocket: WebSocket, # ws对象
                      modified_tradeUid: str):  # 交易策略uid
        print("触发连接", modified_tradeUid)
        creat_pooling = False
        if not modified_tradeUid in original_dict.keys():  # 如果交易id不在字典中
            # 创建新的键值
            original_dict[modified_tradeUid] = [websocket]
            # 发送连接反馈
            unique_number = generate_unique_12_digit_number()
            # await websocket.send_text(f"id={unique_number}&cmd=connect&code=200")
            creat_pooling = True
        else:  # 如果交易id已经存在
            value = original_dict.get(modified_tradeUid)
            value.append(websocket)
            original_dict[modified_tradeUid] = list(set(value))
        global inverse_dict
        inverse_dict = inverse(original_dict)
        return creat_pooling

    # 对连接进行判断，断链接
    # 修改为取消订阅
    async def disconnect_clientId(self, modified_tradeUid: str):
        if modified_tradeUid in self.active_connections:
            # 通知断链了
            unique_number = generate_unique_12_digit_number()
            # await self.send_personal_message(f"id={unique_number}&cmd=connect&code=200", modified_tradeUid)
            del self.active_connections[modified_tradeUid]
            print("通知断链成功：ID是{}".format(unique_number))
        else:
            print("通知失败，已不在websocket连接通道里面")

    async def disconnect(self, websocket: WebSocket, modified_tradeUid: str):
        if modified_tradeUid == "all":
            tradeUids = inverse_dict.get(websocket)
            if tradeUids:
                for tradeUid in tradeUids:
                    original_dict[tradeUid].remove(websocket)
        else:
            try:
                original_dict[modified_tradeUid].remove(websocket)
            except:
                pass
        print(original_dict)


    # 发消息函数(通过tradeUid)
    async def send_message_tradeUid(self, message: str, modified_tradeUid: str):
        global inverse_dict
        connections = original_dict.get(modified_tradeUid)
        if connections:
            for connection in connections:
                await connection.send_text(message)

    # 发消息函数(通过ws连接)
    async def send_message_websocket(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)


manager = ConnectionManager()
async def send_tradeUid(clientid, data):
    if data is not None:
        with open(file_path, 'a') as file:
            file.write(f"{data}\n")
        data = "<<" + data + ">>"
        await manager.send_message_tradeUid(data, clientid)

async def send_websocket(websocket, data):
    if data is not None:
        data = "<<" + data + ">>"
        await manager.send_message_websocket(data, websocket)


# 保存历史订单
def strategy_history_order(tradeUid, order_point=None):
    if order_point is None:
        # 如果存在就加载文件
        if os.path.exists('static/strategy_history_order_pickle.pkl'):
            with open('static/strategy_history_order_pickle.pkl', 'rb') as f:
                strategy_history_order_pickle = pickle.load(f)
        return strategy_history_order_pickle

    else:
        strategy_history_order_pickle = {}
        # 如果存在就加载文件
        if os.path.exists('static/strategy_history_order_pickle.pkl'):
            with open('static/strategy_history_order_pickle.pkl', 'rb') as f:
                strategy_history_order_pickle = pickle.load(f)
        if tradeUid in strategy_history_order_pickle.keys():
            old_order_point = strategy_history_order_pickle[tradeUid]
            index = find_last_index(order_point, old_order_point)
            # index = order_point.index(old_order_point[-1])
            new_order_points = order_point[index + 1:]
            old_order_point = old_order_point + new_order_points
            strategy_history_order_pickle[tradeUid] = old_order_point
        else:
            strategy_history_order_pickle[tradeUid] = order_point
        # 更新
        with open('static/strategy_history_order_pickle.pkl', 'wb') as f:
            pickle.dump(strategy_history_order_pickle, f)

# 保存持有订单
def strategy_hold_order(tradeUid, order_point, goods):
    strategy_hold_order_pickle = {}
    # 如果存在就加载文件
    if os.path.exists('static/strategy_hold_order_pickle.pkl'):
        with open('static/strategy_hold_order_pickle.pkl', 'rb') as f:
            strategy_hold_order_pickle = pickle.load(f)
    history_order = {}
    if tradeUid in strategy_hold_order_pickle.keys():
        history_order = strategy_hold_order_pickle[tradeUid]
    # 使用tmp，来补充订单id和产品名称
    tmp = order_point[-1].copy()
    tmp['goods'] = goods

    if len(history_order) != 0:
        for order in order_point:
            if order.get('orderId') == history_order.get('orderId') and order.get('order_type') == 'close':
                strategy_hold_order_pickle[tradeUid] = {}
                break
        strategy_hold_order_pickle[tradeUid] = tmp
    else:
        strategy_hold_order_pickle[tradeUid] = tmp

    with open('static/strategy_hold_order_pickle.pkl', 'wb') as f:
        pickle.dump(strategy_hold_order_pickle, f)

class OrderType(Enum):
    buy = 'Buy'
    sell = 'Sell'
    buylimit = 'BuyLimit'
    selllimit = 'SellLimit'


# 用于管理返回的信息
def get_strategy_str(tradeUid, new_order_point, new_data, CMD=None):
    type = new_order_point.get('order_type','')
    replacement_rules = {"sell": "Sell",
                         "buy": "Buy",
                         "buy_limit": "BuyLimit", "sell_limit": "SellLimit",
                         "modify_buy":'BuyLimit', "modify_sell":'SellLimit'}
    type = replacement_rules.get(type, type)

    base = (f"TradeUid={tradeUid}&"  # 交易策略uid
            f"Cmd={CMD}&"
            f"TimeStamp={int(datetime.now().timestamp())}&"
            )
    data = 'Data='
    orderId = new_order_point.get('orderId','')  # 订单id
    opentime = new_order_point.get('datatime','')  # k线时间
    exp = '' # 过期时间
    symbol = new_data.get("goods", '')  # 产品
    price = new_order_point.get('price','')  # 价格
    sl = 0  # 止损
    tp = 0  # 止盈
    lots = new_order_point.get('size',0)  # 手数
    lots = str(lots).replace("-", "")
    mc = new_order_point.get('orderId','')  # 原订单id，备注

    #CMD 目前包含Connect、Opne、Close、TradingOrders
    if CMD == 'Open':
        print('new_order_point',new_order_point)
        return base + data + ','.join(str(i) for i in [orderId, symbol, type, price, lots, sl, tp, exp, mc, opentime]) + 'a'
    elif CMD == 'Close':
        return base + data + ','.join(str(i) for i in [orderId, symbol, 'Close', price, opentime])+'b'
    elif CMD == 'Modify':
        return base + data + ','.join(str(i) for i in [orderId, symbol, type ,price, sl, tp, exp, opentime])+'c'
    elif CMD == 'HeartBeat':
        return base + data + ','.join(str(i) for i in [orderId, symbol, type, price, lots, sl, tp, exp, mc, opentime])+'d'
    elif CMD == 'Connect':
        return base + 'Code=200'


# 买卖点轮询计算
async def send_forex_updates(data):
    try:
        last_order_point = []
        last_latest_Kline_datetime = ''
        # data = json.loads(data)

        tradeUid = data.get("tradeUid", 0)
        parameter = data.get("parameter", None)
        period = data.get("period", None)
        goods = data.get("goods", None)
        strategyUid = data.get("uid", None)

        MagicCode = random.randint(10000000, 99999999)

        new_data = {"parameter":parameter,
                    "period":period,
                    "goods": goods,
                    "tradeUid": data.get("tradeUid", 0)}

        if tradeUid == 'NTRXAUM1S000':
            moni = True
        else:
            moni = False
        while keep_running:
            try:
                async with async_db_session() as db:
                    # 根据品种或者品种表的手数和盈亏倍率
                    dp_goods_data = await db.execute(select(DplGoodsTest).where(
                        DplGoodsTest.goods == goods))
                    goods_data = dp_goods_data.scalars().first()
                    # 根据uid寻找策略
                    strategy = await fetch_indicators(db, strategyUid)
                    print('strategys.className',strategy.className)
                    # 计算策略结果
                    backtest_result = await run_backtest(db, new_data, strategy, 0, goods_data, task_name="sync", ismoni=moni)
                    order_point = backtest_result.get('order_point', [])  # 获取买卖点的字典
                    latest_Kline_datetime = str(backtest_result.get('last_datetime', []))  # 最新k线时间
                    latest_Kline_datetime = datetime.strptime(latest_Kline_datetime, '%Y-%m-%d %H:%M:%S')

                # print('@@@@@@', last_order_point)
                # print('@@@@@@', order_point)
                # print(order_point)
                strategy_hold_order(tradeUid, order_point, goods)
                # 判断有没有买卖点
                if order_point_judge(last_order_point, order_point):
                    index = find_last_index(order_point, last_order_point)
                    # index = order_point.index(last_order_point[-1])
                    new_order_points = order_point[index+1:]
                    # 保存出现的买卖点
                    strategy_history_order(tradeUid, order_point)
                    for new_order_point in new_order_points:
                        # print('*'*5,new_order_point)
                        if new_order_point.get('order_type') == 'buy' or new_order_point.get('order_type') == 'sell': # 开仓
                            tmp = get_strategy_str(tradeUid, new_order_point, new_data, CMD='Open')
                            # print('开仓',tmp)
                            await send_tradeUid(tradeUid, tmp)

                        elif new_order_point.get('order_type') == 'close':  # 关仓
                            tmp = get_strategy_str(tradeUid, new_order_point, new_data, CMD='Close')
                            # print('关仓', tmp)
                            await send_tradeUid(tradeUid, tmp)

                        elif new_order_point.get('order_type') == 'buy_limit' or new_order_point.get('order_type') == 'sell_limit':  # 关仓
                            tmp = get_strategy_str(tradeUid, new_order_point, new_data, CMD='Open')
                            # print('挂单', tmp)
                            await send_tradeUid(tradeUid, tmp)

                        elif new_order_point.get('order_type') == 'modify_buy' or new_order_point.get('order_type') == 'modify_sell':  # 关仓
                            tmp = get_strategy_str(tradeUid, new_order_point, new_data, CMD='Modify')
                            # print('挂单', tmp)
                            await send_tradeUid(tradeUid, tmp)


                        print('产生买卖点')
                        # 持单的保存


                sleep_seconds = period_Conversion_Seconds_dict.get(period)  # 通过周期获取休眠时间
                # 判断数据有没有更新
                if last_latest_Kline_datetime != '':

                    dt_object = latest_Kline_datetime + timedelta(seconds=sleep_seconds)  # 用于判断当前时间的下一个k线是不是节假日
                    # 检查是否周末
                    is_weekend = dt_object.weekday() >= 5
                    # 检查是否假日(美国)
                    is_holiday = dt_object in holidays.US()
                    # 检查是否休市
                    start_time = time(0, 0, 0)  # 00:00:00
                    end_time = time(1, 0, 0)  # 01:00:00
                    is_close = start_time <= dt_object.time() < end_time

                    # 如果不是节假日 且 两次最后k线的相同
                    if latest_Kline_datetime == last_latest_Kline_datetime and not any([is_weekend, is_holiday, is_close]):
                        # await send_tradeUid(tradeUid, "数据未更新")
                        print("数据未更新")

                # 记录上一个买卖点 和 上一个策略计算种的最后一根K线
                last_order_point = order_point
                last_latest_Kline_datetime = latest_Kline_datetime
            except OperationalError as e:
                log.error(f"数据库断开，捕获到 OperationalError: {e}")

            # 设置轮询间隔
            if tradeUid == 'NTRXAUM1S0002':
                for i in order_point:
                    if i.get('order_type') != 'close': # 开仓
                        tmp = get_strategy_str(tradeUid, i, new_data, CMD='Open')
                        await send_tradeUid(tradeUid, tmp)
                    else:  # 关仓
                        tmp = get_strategy_str(tradeUid, i, new_data, CMD='Close')

                        await send_tradeUid(tradeUid, tmp)
                    await asyncio.sleep(15)
                await asyncio.sleep(0)
            else:
                if tradeUid == 'NTRXAUM1S000':
                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(sleep_seconds)
    except:
        info = traceback.format_exc()
        log.error("策略轮询出错：{}".format(info))
        print("错误信息：{}".format(info))
        return Response(status_code=500, content="系统错误!")




@router.websocket("/wss")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    global diaoqucishu
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            print(data)

            # 解析-参数
            parsed_params = parse_qs(data)

            # 接收参数
            tradeUid = parsed_params.get('tradeUid', [''])[0]  # 交易策略Uid
            cmd = parsed_params.get('cmd', [''])[0]
            # cmd=connect表示连接指令 quit=关闭连接  heartbeat 表示心跳检测
            if cmd == "connect":
                # 拿到tradeUid 后，进行数据库查询出品种-交易周期-参数-策略Uid
                async with async_db_session() as db:
                    query = select(TradingStrategy).where(TradingStrategy.tradeUid == tradeUid)
                    strategy = await db.execute(query)
                    results = strategy.scalars().first()
                    if results:
                        # 将每一个订阅者加入到websocket连接池中
                        creat = await manager.connect(websocket, results.tradeUid)
                        tmp = get_strategy_str(tradeUid, {}, {}, CMD='Connect')
                        await send_websocket(websocket, tmp)
                        # await send_websocket(websocket,f"tradeUid={tradeUid}&cmd=connect&code=200&timeStamp={int(datetime.now().timestamp())}")

                        if creat:
                            data_dict = {"parameter": json.loads(results.parameter), "period": results.period,
                                         "goods": results.goods, "uid": results.strategyUid,
                                         "tradeUid": results.tradeUid}
                            print("创建轮询")
                            # 调用计算函数
                            # 直接 await 异步函数
                            if tradeUid == 'NTRXAUM1S000':
                                diaoqucishu = 3000

                            asyncio.create_task(send_forex_updates(data_dict))
                            # await send_forex_updates(data_dict)
                            print("&"*30)
                        else:
                            print("已经存在")
                        # print(original_dict)
                    else:
                        await send_websocket(websocket, f"tradeUid={tradeUid}&cmd=connect&code=404&message=策略不存在&timeStamp={int(datetime.now().timestamp())}")

            elif cmd == 'heartbeat':
                with open('static/strategy_hold_order_pickle.pkl', 'rb') as f:
                    strategy_hold_order_pickle = pickle.load(f)
                print('心跳', inverse_dict.get(websocket))
                if not inverse_dict.get(websocket) is None:
                    # 用户订阅的策略列表 形状为['NTRXAUM1S000', 'NTRXAUM1S0001']
                    User_Subscription_Strategy = inverse_dict.get(websocket)
                    hold = []
                    print(User_Subscription_Strategy)
                    for i in User_Subscription_Strategy:
                        if i in strategy_hold_order_pickle.keys():
                            tmp = get_strategy_str(i, strategy_hold_order_pickle[i], strategy_hold_order_pickle[i], CMD='HeartBeat')
                            await send_websocket(websocket,  tmp)

                    # await send_websocket(websocket, base+'|'.join(str(i) for i in hold))
                # else:
                #     await send_websocket(websocket, f"")
                # manager.disconnect_clientId(websocket=websocket, clientId=clientId)
                pass
            elif cmd == "quit":
                print("接到断开请求")
                await manager.disconnect(websocket, tradeUid)

            # print(original_dict)
            # print(inverse_dict)

    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected with code: {e.code}")
        await manager.disconnect(websocket, "all")
        # await websocket.close()  # 关闭 WebSocket 连接
    except OperationalError as e:
        log.error(f"捕获到 OperationalError: {e}")
    except Exception as e:
        log.error(f"捕获到异常: {e}")


#-------------------------------- 毒属于该文件的函数-------------------------------#

# 封装成一个异步函数，然后在需要使用的地方直接调用该函数
async def fetch_trading_data(db, goods, period, model_classes,
                             begin_time=None, end_time=None,
                             lineId=0, name=None, period_tuple=None, class_name=None, tradeUid=None):
    # 需要使用到begintime的策略，即数据开始时间会影响
    need_begintime_class = ['atr_strategy.ATRStrategy',
                            'atr_strategyv1.ATRStrategy',
                            'bbtrend.BBTrendStrategy']

    try:
        # 1 查询中间表 交易品种表
        select_model_class, result = await select_goods_common(db, goods, model_classes)

        if not select_model_class:
            return False

        if begin_time and end_time:
            print("时段数据 开始执行时间：{}".format(datetime.datetime.now()))
            # 根据交易品种表的 table_name 字段查找主表，拿到交易历史数据后加入到backtrader的数据源中（开始时间 - 结束时间）
            # if class_name in ["atr_strategy.ATRStrategy"] or class_name in ["atr_strategyv1.ATRStrategy"]:
            if class_name in need_begintime_class:
                # backtrader ATR回测特定查询，从起始时间再剪一天
                start_time = datetime.datetime.strptime(begin_time, '%Y-%m-%d %H:%M:%S')

                # 减去一个工作日
                previous_working_day = (pd.Timestamp(start_time) - pd.offsets.BDay()).to_pydatetime()

                # 格式化回字符串
                previous_working_day_str = previous_working_day.strftime('%Y-%m-%d')

                query = select(select_model_class).where(
                    select_model_class.tradingGoods == result.trading_goods,
                    select_model_class.platform == result.platform,
                    select_model_class.type == period,
                    select_model_class.tradeDateTime.between(previous_working_day_str, end_time)
                ).order_by(select_model_class.tradeDateTime.desc())

            else:
                # 正常根据起始时间至结束时间查询
                query = select(select_model_class).where(
                    select_model_class.tradingGoods == result.trading_goods,
                    select_model_class.platform == result.platform,
                    select_model_class.type == period,
                    select_model_class.tradeDateTime.between(begin_time, end_time)
                    ).order_by(select_model_class.tradeDateTime.desc())

            details = await db.execute(query)

            # 组织数据结构
            result_list = details.scalars().all()

            results_data_list = [
                {"pkId": x.pkId, "datetime": timezone.str_f(x.tradeDateTime), "open": x.opening,
                 "high": x.high, "low": x.low, "close": x.closed,
                 "volume": x.vol, "openinterest": 0, "klineId": x.pkId,
                 "digits": x.digits, "spread": x.spread} for x in result_list]

            result_list_data = sorted(results_data_list, key=lambda x: x['datetime'])

            print("时段数据 结束执行时间：{}".format(datetime.datetime.now()))

            return result_list_data

        else:
            if name == "latest_new":  # 最新数据
                details_data = select(select_model_class).where(
                    select_model_class.tradingGoods == result.trading_goods,
                    select_model_class.platform == result.platform,
                    select_model_class.type == period,
                ).order_by(desc(select_model_class.tradeDateTime)).limit(3000)

                detail = await db.execute(details_data)
                # 组织数据结构
                results = detail.scalars().all()
                if os.path.exists('static/strategy_history_order_pickle.pkl'):
                    with open('static/strategy_history_order_pickle.pkl', 'rb') as f:
                        strategy_history_order_pickle = pickle.load(f)
                    if tradeUid in strategy_history_order_pickle.keys():
                        order_point = strategy_history_order_pickle[tradeUid]
                        begin_time = order_point[-1].get('datatime')
                        print('begin_time', begin_time)
                        # start_time = datetime.datetime.strptime(begin_time, '%Y-%m-%d %H:%M:%S')
                        # previous_working_day = (pd.Timestamp(start_time)).to_pydatetime()
                        # previous_working_day_str = previous_working_day.strftime('%Y-%m-%d')
                        details_data1 = select(select_model_class).where(
                            select_model_class.tradingGoods == result.trading_goods,
                            select_model_class.platform == result.platform,
                            select_model_class.type == period,
                            select_model_class.tradeDateTime < begin_time
                        ).order_by(desc(select_model_class.tradeDateTime)).limit(3000)

                        detail1 = await db.execute(details_data1)
                        # 组织数据结构
                        results1 = detail1.scalars().all()
                        details_data2 = select(select_model_class).where(
                            select_model_class.tradingGoods == result.trading_goods,
                            select_model_class.platform == result.platform,
                            select_model_class.type == period,
                            select_model_class.tradeDateTime >= begin_time
                        ).order_by(desc(select_model_class.tradeDateTime))

                        detail2 = await db.execute(details_data2)
                        # 组织数据结构
                        results2 = detail2.scalars().all()
                        results = results1 + results2
                    # else:
                    #     details_data = select(select_model_class).where(
                    #         select_model_class.tradingGoods == result.trading_goods,
                    #         select_model_class.platform == result.platform,
                    #         select_model_class.type == period,
                    #     ).order_by(desc(select_model_class.tradeDateTime)).limit(3000)
                    #
                    #     detail = await db.execute(details_data)
                    #     # 组织数据结构
                    #     results = detail.scalars().all()

            else:
                results = []

            results_data_list = [
                {"pkId": x.pkId, "datetime": timezone.str_f(x.tradeDateTime), "open": x.opening,
                 "high": x.high, "low": x.low, "close": x.closed,
                 "volume": x.vol, "openinterest": 0,
                 "klineId": x.pkId, "spread": x.spread, "digits": x.digits} for x in results]

            result_list = sorted(results_data_list, key=lambda x: x['datetime'])
            print(len(result_list))

            return result_list

    except Exception as e:
        info = traceback.format_exc()
        log.error("查询技术指标K线历史数据错误出错：{}".format(info))
        print("查询技术指标K线历史数据错误出错：{}".format(info))
        return []


def find_last_index(order_point, last_order_point):
    """
    :param order_point: 新买卖点记录
    :param last_order_point: 旧买卖点记录
    :return: 返回last_order_point最后一个在，新的买卖点记录中的位置，如果没有返回-1
    """
    last_order_point = last_order_point[-1]

    order_point_l = [[i['datatime'], i['order_type']] for i in order_point]
    last_order_point_l = [last_order_point['datatime'], last_order_point['order_type']]
    try:
        return order_point_l.index(last_order_point_l)
    except:
        return -1


def order_point_judge(last_order_point, order_point):
    # print(last_order_point, order_point)
    if len(last_order_point) == 0:
        return False
    # 条件2可以覆盖条件1的场景
    condition1 = last_order_point[-1]['datatime'] != order_point[-1]['datatime']
    condition2 = last_order_point[-1]['datatime'] < order_point[-1]['datatime']
    print('条件', condition1, condition2)
    if condition1 and condition2:
        return True
    else:
        return False