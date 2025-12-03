import copy
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
from models.dql_platform import TradingStrategy, DqlStrategy, DplGoodsTest, DqlOrderholdpoint, DqlOrderhistorypoint
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
from apis.v1.platform_strategy import create_strategy_record
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

import socket
# 创建一个临时socket连接外部服务器来获取主要IPv4
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    # 不会实际建立连接，仅用于获取本地IP
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
    print("本机IPv4地址:", local_ip)
except Exception:
    print("无法获取IP地址，默认使用回环地址: 127.0.0.1")
finally:
    s.close()

diaoqucishu = 3770
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
async def run_backtest(indicator_data_request, strategys, tester_uid, goods_data, task_name=None, simulated=False):
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

        df, last_datetime= await get_k_line_data(goods, period, model_classes, name="latest_new", tradeUid=tradeUid, simulated=simulated)

        cerebro = bt.Cerebro()
        cerebro.broker.setcommission(leverage=indicator_data_request.get("leverage", 1))
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
        # print('查看结果',result)

        # traderResult, traderReport = result[0].get_analysis()
        trader_return = result[0].get_analysis()
        traderResult = trader_return.get('trader_result')
        traderReport = trader_return.get('trader_report')
        order_point = trader_return.get('order_point', [])

        return {"traderResult": traderResult,
                "traderReport": traderReport,
                "order_point": order_point,
                "last_datetime": last_datetime}

    except Exception as e:
        info = traceback.format_exc()
        log.error("策略结果插入数据库失败：{}".format(info))
        # await db.rollback()  # 如果发生异常，回滚事务
        # await db.close()
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
async def strategy_history_order(tradeUid, order_point=None):
    tmp = order_point.copy()
    tmp['datatime'] = tmp['datatime'].isoformat()
    async with async_db_session() as db:
        new_order = DqlOrderhistorypoint(
            tradeuid=tradeUid,
            cmd=json.dumps(tmp),
            ip=local_ip,
            createTime=datetime.now()  # 传入当前时间
        )
        db.add(new_order)
        await db.flush()
        await db.commit()

# 保存持有订单
async def strategy_hold_order(tradeUid, order_point, goods):
    async with async_db_session() as db:
        # 查询策略
        result = await db.execute(
            select(DqlOrderholdpoint)
            .where(DqlOrderholdpoint.tradeuid == tradeUid)
            .where(DqlOrderholdpoint.ip == local_ip)
        )
        history_orders = result.scalars().all()  # 获取所有结果
        history_order = history_orders[-1] if history_orders else None  # 取最后一条
        # print('数据库', history_order)
        tmp = order_point[-1].copy()
        tmp['goods'] = goods
        tmp['datatime'] = tmp['datatime'].isoformat()
        if history_order:
            history_order.cmd = json.dumps(tmp)
            history_order.createTime = datetime.now()
            # 提交事务以保存到数据库
            await db.commit()
        else:
            # 创建实例
            new_order = DqlOrderholdpoint(
                tradeuid=tradeUid,
                cmd=json.dumps(tmp),
                ip=local_ip,
                createTime=datetime.now()  # 传入当前时间
            )
            db.add(new_order)
            await db.commit()


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
    # price = new_order_point.get('price','')  # 价格
    price = 0
    sl = 0  # 止损
    tp = 0  # 止盈
    lots = new_order_point.get('size',0)  # 手数
    lots = str(lots).replace("-", "")
    mc = new_order_point.get('orderId','')  # 原订单id，备注

    #CMD 目前包含Connect、Opne、Close、TradingOrders
    if CMD == 'Open':
        return base + data + ','.join(str(i) for i in [orderId, symbol, type, price, lots, sl, tp, exp, mc, opentime])
    elif CMD == 'Close':
        return base + data + ','.join(str(i) for i in [orderId, symbol, 'Close', price, opentime])
    elif CMD == 'Modify':
        return base + data + ','.join(str(i) for i in [orderId, symbol, type, price, sl, tp, exp, opentime])
    elif CMD == 'HeartBeat':
        return base + data + ','.join(str(i) for i in [orderId, symbol, type, price, lots, sl, tp, exp, mc, opentime])
    elif CMD == 'Connect':
        return base + 'Code=200'

sigal = False
async def fetch_indicators(uid: str):
    async with async_db_session() as db:
        select_indicators = await db.execute(select(DqlStrategy).where(
            DqlStrategy.uid == uid, DqlStrategy.is_delete == 0))
    return select_indicators.scalars().first()
# 买卖点轮询计算
async def send_forex_updates(data):
    try:
        last_order_point = []
        last_latest_Kline_datetime = ''
        tradeUid = data.get("tradeUid", 0)
        parameter = data.get("parameter", None)
        period = data.get("period", None)
        goods = data.get("goods", None)
        strategyUid = data.get("uid", None)

        MagicCode = random.randint(10000000, 99999999)

        new_data = {
            "parameter": parameter,
            "period": period,
            "goods": goods,
            "tradeUid": data.get("tradeUid", 0)
        }

        if tradeUid == 'NTRXAUM5S000':
            moni = True
            print('模拟')
        else:
            moni = False

        async with async_db_session() as db:
            dp_goods_data = await db.execute(select(DplGoodsTest).where(
                DplGoodsTest.goods == goods))
            goods_data = dp_goods_data.scalars().first()
            strategy = await fetch_indicators(uid=strategyUid)

        while keep_running:
            try:
                print('轮询中', tradeUid, sigal)

                backtest_result = await run_backtest(new_data, strategy, 0, goods_data, task_name="sync",
                                                     simulated=moni)
                order_point = backtest_result.get('order_point', [])
                latest_Kline_datetime = str(backtest_result.get('last_datetime', []))
                latest_Kline_datetime = datetime.strptime(latest_Kline_datetime, '%Y-%m-%d %H:%M:%S')

                await strategy_hold_order(tradeUid, order_point, goods)

                if order_point_judge(last_order_point, order_point):
                    index = find_last_index(order_point, last_order_point, from_w='轮询计算')
                    print('索引：',index, '  order_point长度', len(order_point),'  last_order_point长度', len(last_order_point))

                    if index == -1:
                        last_order_point = order_point
                        continue
                    if index != len(last_order_point):
                        index += 1
                    new_order_points = order_point[index:]
                    print('买卖点',len(new_order_points), new_order_points)

                    for new_order_point in new_order_points:
                        await strategy_history_order(tradeUid, new_order_point)
                        if new_order_point.get('order_type') in ['buy', 'sell']:
                            tmp = get_strategy_str(tradeUid, new_order_point, new_data, CMD='Open')
                            await send_tradeUid(tradeUid, tmp)
                        elif new_order_point.get('order_type') == 'close':
                            tmp = get_strategy_str(tradeUid, new_order_point, new_data, CMD='Close')
                            await send_tradeUid(tradeUid, tmp)
                        elif new_order_point.get('order_type') in ['buy_limit', 'sell_limit']:
                            tmp = get_strategy_str(tradeUid, new_order_point, new_data, CMD='Open')
                            await send_tradeUid(tradeUid, tmp)
                        elif new_order_point.get('order_type') in ['modify_buy', 'modify_sell']:
                            tmp = get_strategy_str(tradeUid, new_order_point, new_data, CMD='Modify')
                            await send_tradeUid(tradeUid, tmp)

                sleep_seconds = period_Conversion_Seconds_dict.get(period)
                last_order_point = order_point
                last_latest_Kline_datetime = latest_Kline_datetime

            except OperationalError as e:
                log.error(f"数据库错误，需要重启轮询: {tradeUid}, 错误: {e}")
            except RuntimeError as e:
                if "Unexpected ASGI message 'websocket.send'" in str(e):
                    log.error(f"WebSocket连接错误，需要重启轮询: {tradeUid}, 错误: {e}")
                else:
                    log.error(f"其他运行时错误: {e}")
            except Exception as e:
                info = traceback.format_exc()
                log.error(f"本轮轮询出错：{info}")
            finally:
                if 'sleep_seconds' in locals():
                    await asyncio.sleep(sleep_seconds)
                else:
                    await asyncio.sleep(1)

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"函数初始化阶段出错：{info}")
        # 初始化失败也尝试重启
        # await restart_polling(tradeUid)

# 在现有全局变量基础上添加
active_tasks = {}  # 存储 tradeUid 与对应轮询任务的映射

@router.post("/restartPolling", name="重启轮询任务")
async def restart_polling(trade_uid: str):
    """通过 tradeUid 重启对应的轮询任务"""
    try:
        # 1. 停止现有任务（如果存在）
        if trade_uid in active_tasks:
            task = active_tasks[trade_uid]
            if not task.done():
                task.cancel()  # 取消任务
                await asyncio.sleep(0.1)  # 等待任务终止
            del active_tasks[trade_uid]
            log.info(f"已停止轮询任务: {trade_uid}")

        # 2. 查询策略信息，准备重启参数
        async with async_db_session() as db:
            query = select(TradingStrategy).where(TradingStrategy.tradeUid == trade_uid)
            strategy = await db.execute(query)
            result = strategy.scalars().first()
            if not result:
                return await response_base.fail(msg="策略不存在")

            # 3. 重启轮询任务
            data_dict = {
                "parameter": json.loads(result.parameter),
                "period": result.period,
                "goods": result.goods,
                "uid": result.strategyUid,
                "tradeUid": result.tradeUid
            }
            new_task = asyncio.create_task(send_forex_updates(data_dict))
            active_tasks[trade_uid] = new_task
            log.info(f"已重启轮询任务: {trade_uid}")
            return await response_base.success(msg="轮询已重启")

    except Exception as e:
        log.error(f"重启轮询失败: {traceback.format_exc()}")
        return await response_base.fail(msg=f"重启失败: {str(e)}")


@router.get("/stop", name="出问题")
def stop():
    print('停止轮询')
    global sigal
    sigal = True

@router.get("/open", name="出问题")
def stop():
    print('继续轮询')
    global sigal
    sigal = False

@router.websocket("/wss")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    global diaoqucishu
    current_trade_uid = None  # 记录当前处理的tradeUid
    try:
        while True:
            data = await websocket.receive_text()
            parsed_params = parse_qs(data)
            tradeUid = parsed_params.get('tradeUid', [''])[0]
            cmd = parsed_params.get('cmd', [''])[0]
            current_trade_uid = tradeUid  # 更新当前tradeUid

            if cmd == "connect":
                async with async_db_session() as db:
                    try:
                        # 增加数据库连接检测
                        await db.execute(select(1))
                    except OperationalError:
                        await send_websocket(websocket, f"tradeUid={tradeUid}&cmd=error&code=503&message=数据库连接失败")
                        continue

                    query = select(TradingStrategy).where(TradingStrategy.tradeUid == tradeUid)
                    strategy = await db.execute(query)
                    results = strategy.scalars().first()
                    if results:
                        creat = await manager.connect(websocket, results.tradeUid)
                        tmp = get_strategy_str(tradeUid, {}, {}, CMD='Connect')
                        await send_websocket(websocket, tmp)

                        if creat:
                            data_dict = {"parameter": json.loads(results.parameter), "period": results.period,
                                         "goods": results.goods, "uid": results.strategyUid,
                                         "tradeUid": results.tradeUid}
                            print("创建轮询")
                            if tradeUid == 'NTRXAUM1S000':
                                diaoqucishu = 3000

                            new_task = asyncio.create_task(send_forex_updates(data_dict))
                            active_tasks[data_dict["tradeUid"]] = new_task
                        else:
                            print("已经存在")
                    else:
                        await send_websocket(websocket, f"tradeUid={tradeUid}&cmd=connect&code=404&message=策略不存在")

            elif cmd == 'heartbeat':
                # print('心跳', inverse_dict.get(websocket))
                if not inverse_dict.get(websocket) is None:
                    # 用户订阅的策略列表 形状为['NTRXAUM1S000', 'NTRXAUM1S0001']
                    User_Subscription_Strategy = inverse_dict.get(websocket)
                    for i in User_Subscription_Strategy:
                        async with async_db_session() as db:
                            result = await db.execute(
                                select(DqlOrderholdpoint)
                                .where(DqlOrderholdpoint.tradeuid == i)
                                .where(DqlOrderholdpoint.ip == local_ip)
                            )
                            history_orders = json.loads(result.scalars().all()[-1].cmd)  # 获取所有结果
                            # print('这里',history_orders)
                            if history_orders:
                                tmp = get_strategy_str(i, history_orders, history_orders, CMD='HeartBeat')
                                await send_websocket(websocket, tmp)


                    # await send_websocket(websocket, base+'|'.join(str(i) for i in hold))
                # else:
                #     await send_websocket(websocket, f"")
                # manager.disconnect_clientId(websocket=websocket, clientId=clientId)
                pass
            elif cmd == "quit":
                print("接到断开请求")
                await manager.disconnect(websocket, tradeUid)

    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected with code: {e.code}")
        await manager.disconnect(websocket, "all")
    except OperationalError as e:
        log.error(f"WebSocket中的数据库错误: {e}")
        # 如果有当前处理的tradeUid，重启其任务
        if current_trade_uid:
            await restart_polling(current_trade_uid)
    except Exception as e:
        log.error(f"WebSocket异常: {e}")
        if current_trade_uid:
            await restart_polling(current_trade_uid)


#-------------------------------- 毒属于该文件的函数-------------------------------#

# 封装成一个异步函数，然后在需要使用的地方直接调用该函数
async def get_k_line_data(goods, period, model_classes,
                             begin_time=None, end_time=None,
                             lineId=0, name=None, period_tuple=None, class_name=None, tradeUid=None, simulated=False):
    # 需要使用到begintime的策略，即数据开始时间会影响
    need_begintime_class = ['atr_strategy.ATRStrategy',
                            'atr_strategyv1.ATRStrategy',
                            'bbtrend.BBTrendStrategy']

    try:
        async with async_db_session() as db:
            # 1 查询中间表 交易品种表
            select_model_class, result = await select_goods_common(db, goods, model_classes)
            if not select_model_class:
                return False

            if name == "latest_new":  # 最新数据
                details_data = select(select_model_class).where(
                    select_model_class.tradingGoods == result.trading_goods,
                    select_model_class.platform == result.platform,
                    select_model_class.type == period,
                ).order_by(desc(select_model_class.tradeDateTime)).limit(1000)

                detail = await db.execute(details_data)
                # 组织数据结构
                results = detail.scalars().all()
            else:
                results = []

        results_data_list = [
            {"pkId": x.pkId, "datetime": timezone.str_f(x.tradeDateTime), "open": x.opening,
             "high": x.high, "low": x.low, "close": x.closed,
             "volume": x.vol, "openinterest": 0,
             "klineId": x.pkId, "spread": x.spread, "digits": x.digits} for x in results]

        result_list = sorted(results_data_list, key=lambda x: x['datetime'])

        df = pd.DataFrame(result_list)
        if simulated:
            # print('模拟数据')
            global diaoqucishu
            df = df.iloc[diaoqucishu - 3000:diaoqucishu]
            diaoqucishu += 1
            # print('diaoqucishu', diaoqucishu)

        df['datetime'] = pd.to_datetime(df['datetime'])
        last_datetime = df['datetime'].iloc[-1]
        df.set_index('datetime', inplace=True)

        return df, last_datetime

    except Exception as e:
        info = traceback.format_exc()
        log.error("查询技术指标K线历史数据错误出错：{}".format(info))
        print("查询技术指标K线历史数据错误出错：{}".format(info))
        return [None, None]



def find_last_index(order_point, last_order_point, from_w=None):
    """
    :param order_point: 新买卖点记录
    :param last_order_point: 旧买卖点记录
    :return: 返回last_order_point最后一个在，新的买卖点记录中的位置，如果没有返回-1
    """
    last_order_point = last_order_point[-1]
    # print(f'find_last_index这里,来自{from_w}',last_order_point,)

    order_point_l = [[i['datatime'], i['order_type']] for i in order_point]
    last_order_point_l = [last_order_point['datatime'], last_order_point['order_type']]

    print('当前',order_point_l[-5:])
    print('上一个',last_order_point_l)
    # return order_point_l.index(last_order_point_l)
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
    # print('条件', condition1, condition2,len(order_point))
    if condition1 and condition2:
        return True
    else:
        return False