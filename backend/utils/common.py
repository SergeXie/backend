import datetime
# from numba import cuda
import json
import random
import re
import string
import time
import traceback
import pandas as pd
from cachetools import TTLCache
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response
from common.log import log
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.dql_platform import DplGoodsTest, DqlIndicators, TradingFPG, TradingBRC5, TradingOnda, TradingFXTM5, \
    TradingIndex, TradingIndex2, TradingFPG2, DqlStrategy, DqlOrder
from utils.indicators import *
# from utils.indicators.atr_kmeans import ResponseATRKmeansData
from utils.indicators.deeplearn_v2 import ResponseDL2Data
from utils.indicators.deeplearn import ResponseDLData
from utils.indicators.BBTrend import ResponseBBTrendData
from utils.indicators.acp import ResponseACPData
from utils.indicators.smcp import ResponseSMCPData
from utils.indicators.cci import ResponseCCIData
from utils.indicators.dma import ResponseDMAData
from utils.indicators.ma import ResponseMAMovingAverageIndicator
from utils.indicators.macd import ResponseMACDData
from utils.indicators.macd_v1 import ResponseMACDData_v1
from utils.indicators.bollinger import ResponseBollingerData
from utils.indicators.ema import ResponseEMAData
from utils.indicators.btatr import ResponseATRData
from utils.indicators.rsi import ResponseRSIData
from pypinyin import lazy_pinyin, Style
from typing import List, Dict, Any
from utils.strategys import reload_strategies
from utils.timezone import timezone
from dateutil import parser
from utils.public_strategy import ComprehensiveAnalyzer

# 创建一个带有过期时间的缓存，设置每个缓存条目的过期时间为 60 秒
cache = TTLCache(maxsize=10000, ttl=3600)

limit_num = 1000


# 创建模型类字典
model_classes = {
    'dql_trading_fpg': TradingFPG,
    'dql_trading_fpg_tests': TradingFPG2,
    'dql_trading_bcr5': TradingBRC5,
    "dql_trading_onda": TradingOnda,
    "dql_trading_fxtm5": TradingFXTM5,
    "dql_trading_index": TradingIndex,
    "dql_trading_index2": TradingIndex2
    # 在这里添加更多的模型类
}

indicator_classes = {
    # "ATR_KMEANS": ResponseATRKmeansData,
    "DL2": ResponseDL2Data,
    "DL": ResponseDLData,
    "BBTrend": ResponseBBTrendData,
    "ACP": ResponseACPData,
    "AverageTrueRange": ResponseATRStopLossData,
    "PeakConnection": ResponsePCData,
    "CCI": ResponseCCIData,
    "DMA": ResponseDMAData,
    "MACD": ResponseMACDData,
    "MACD_v1": ResponseMACDData_v1,
    "MA": ResponseMAMovingAverageIndicator,
    "Bollinger": ResponseBollingerData,
    "EMA": ResponseEMAData,
    "btATR": ResponseATRData,
    "RSI": ResponseRSIData,
    "SMCP": ResponseSMCPData,
}


strategy_classes = {}
strategy_classes = reload_strategies()


def match_ratio(data):
    # 使用正则表达式提取百分比
    match = re.search(r'\((\d+\.\d+)%\)', data)
    if match:
        match = float(match.group(1))  # 提取并转换为浮动数值
    else:
        match = 0.0  # 如果没有匹配到，默认值为 0

    return match


def match_filter_data(data):
    # 使用正则表达式提取数字
    match = re.search(r'(\d+)', data)
    if match:
        match = int(match.group(1))  # 提取并转换为整数
    else:
        match = 0  # 默认值

    return match


def to_float(value):
    try:
        # 移除常见的千位分隔符：空格和逗号
        cleaned_value = value.replace(' ', '').replace(',', '')
        # 尝试转换为浮点数
        return float(cleaned_value)
    except ValueError:
        # 如果转换失败，返回默认值 0
        print(f"无法将 '{value}' 转换为浮点数。")
        return 0

def datetimesp(dt_float):
    # 将浮点数转换为日期时间格式
    dt_datetime = datetime.datetime.fromordinal(int(dt_float)) + datetime.timedelta(days=dt_float % 1)
    dt_datetime = dt_datetime.replace(microsecond=0)  # 将微秒部分设置为0

    return str(dt_datetime)


def format_datetime(date_str):
    try:
        # 将 "2024.04.22 11:40:25" 格式转换为 "2024-04-22 11:40:25"
        return datetime.datetime.strptime(date_str, '%Y.%m.%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None  # 如果格式不正确，返回 '0'


def generate_order_id():
    return random.randint(1000000, 9999999)


class MyCommissionScheme(bt.CommInfoBase):
    def _getcommission(self, size, price, pseudoexec):
        # 计算固定点差为64点（即0.64%）
        spread = 0.0064
        return abs(size) * price * spread


def datetimesp(dt_float):
    # 将浮点数转换为日期时间格式
    dt_datetime = datetime.datetime.fromordinal(int(dt_float)) + datetime.timedelta(days=dt_float % 1)
    dt_datetime = dt_datetime.replace(microsecond=0)  # 将微秒部分设置为0

    return str(dt_datetime)


def generate_random_string(name, length=12):
    # 定义可用字符的集合
    characters = string.ascii_letters + string.digits
    # 随机选择字符并生成指定长度的字符串
    random_string = name + ''.join(random.choice(characters) for _ in range(length))
    return random_string


def generate_lazy_pinyin(name):
    pinyinname = lazy_pinyin(name, style=Style.TONE3)

    pinyinname_change = ''

    for i in pinyinname:
        pinyinname_change = pinyinname_change + i[:-1]

    return pinyinname_change


# 对select_kline_data函数进行缓存处理
async def select_kline_data(db, query, period_dict=None):
    result_data = cache.get(period_dict)

    if result_data:
        print("缓存响应")
        return result_data

    else:
        current_time = datetime.datetime.now()
        print("起始时间：{}".format(current_time))

        detail = await db.execute(query)

        tradeing_datas = detail.scalars().all()

        print("结束时间：{}".format(datetime.datetime.now()))

        # 批量处理数据
        result_list = [
            {
                "pkId": x.pkId,
                "timestamp": x.tradeDateTime.strftime('%Y-%m-%d %H:%M:%S'),
                "unxTimestamp": int(x.tradeDateTime.timestamp()),
                "digits": x.digits,
                "spread": x.spread,
                "swapLong": x.swapLong,
                "swapShort": x.swapShort,
                "open": x.opening,
                "high": x.high,
                "low": x.low,
                "close": x.closed,
                "vol": x.vol
            }
            for x in tradeing_datas
        ]

        if period_dict:
            cache[period_dict] = result_list

        return result_list


async def select_goods_common(db, goods, model_classes):

    dp_goods_data = await db.execute(select(DplGoodsTest).where(
        DplGoodsTest.goods == goods))

    result = dp_goods_data.scalars().first()

    print(result)

    if not result:
        return False, False

    # 第二步查询-查询
    # 根据table_name参数确定要查询的模型
    model_class = model_classes.get(result.table_name)

    if not model_class:
        return False,False

    return model_class, result


class RandomIDGenerator:
    def generate_random_id(self):
        # 生成一个随机数
        current_time = time.strftime("%Y%m%d%H%M%S", time.localtime())  # 获取当前时间并格式化为年月日时分秒
        random_number = str(random.randint(10000, 99999))  # 生成一个随机五位数并转换为字符串

        random_id = current_time + random_number

        return random_id


# 交易品种类
class Trader:
    goods_data_list = []
    trader_id = 0  # 生成一个ID 返回前端
    goods_data_dict = []
    trader_goods_strategy_data = {}

    def __init__(self):
        pass

    @classmethod
    def add_goods_trader(cls, goods_data, trader_id):
        # goods_data 多个商品品种, 可添加多个重复的品种周期时间

        # 将tradeId和goodsTradeArray添加到goods_data_dict列表中
        cls.goods_data_dict.append({
            'tradeId': trader_id,
            'goodsTradeArray': goods_data,
        })

        cls.trader_id = trader_id

    def del_goods_trader(self):
        goods_id = self.trader_goods_strategy_data['goodsTradeArray'][0]['goodsTraderId']
        for item in self.goods_data_dict:
            for goods_trade in item['goodsTradeArray']:
                if 'goodsTraderId' in goods_trade and goods_trade['goodsTraderId'] == goods_id:
                    item['goodsTradeArray'].remove(goods_trade)

        return self.trader_goods_strategy_data


# 下单回测类
class GoodTrader(Trader):
    ticks = []

    def __init__(self, ticks=None):
        super().__init__()
        self.ticks = ticks if ticks is not None else []

    def select_trade_id(self, tradeId):
        # 查询goods_data_dict列表中是否存在特定的tradeId
        tradeId_exists = any(item['tradeId'] == tradeId for item in self.goods_data_dict)
        if tradeId_exists:
            return True
        else:
            return False

    def add_ticks(self, goodsTradeArray, select_traderId):
        for item in self.goods_data_dict:
            if item['tradeId'] == select_traderId:
                # 标记是否找到匹配的goodsId
                found = False
                for goods_item in item['goodsTradeArray']:
                    if goods_item['goodsTraderId'] == goodsTradeArray['goodsTraderId']:
                        # 加入新在字典中
                        self.trader_goods_strategy_data["tradeId"] = select_traderId
                        self.trader_goods_strategy_data["goodsTradeArray"] = [
                            {
                                "goodsTraderId": goodsTradeArray['goodsTraderId'],
                                "leverage": goods_item.get("leverage", 1),
                                "initialCash": goods_item["initialCash"],
                                "goods":goods_item["goods"],
                                "period": goods_item["period"],
                                "beginTime":goods_item["beginTime"],
                                "endTime": goods_item["endTime"],
                                "ticks": sorted(goodsTradeArray["ticks"], key=lambda x: x["klineId"])
                            }
                        ]

                        # # 对ticks按照kLineId从小到大排序
                        # goods_item["ticks"] = sorted(goodsTradeArray["ticks"], key=lambda x: x["klineId"])
                        # # 找到匹配的goodsId，将ticks数据挂载到goods_data_dict中
                        found = True
                        break

                if not found:
                    return None
        return True

    def del_ticket(self):
        pass


# 创建backtrader数据源
class PandasData(bt.feeds.PandasData):
    lines = ('pkId', 'open', 'high', 'low', 'close', 'volume', 'openinterest', 'klineId', "digits", "spread")
    params = (
        ('pkId', -1),
        ('open', -1),
        ('high', -1),
        ('low', -1),
        ('close', -1),
        ('volume', -1),
        ('openinterest', None),
        ('klineId', -1),
        ('digits', -1),
        ('spread', -1),
    )


class DynamicSpreadCommission(bt.CommInfoBase):
    params = (
        ('mult', 100),  # 每手包含的单位数量
    )

    def __init__(self):
        self.current_spread = 0
        super(DynamicSpreadCommission, self).__init__()

    def update_spread(self, spread):
        self.current_spread = spread

    def _getcommission(self, size, price, pseudoexec):
        # 将 spread 计算为点差的百分比
        spread_percentage = self.current_spread
        # 计算点差成本
        print(spread_percentage / 100)
        return 0


async def get_entities_list(entity_type, pageNo=1, pageSize=100, orderBy=0, keyWord='%'):
    try:
        # 定义排序方式
        orderDict = {
            0: entity_type.name,  # 默认排序
            -1: desc(entity_type.pinyinname),
            1: entity_type.pinyinname,
            -2: desc(entity_type.weights),
            2: entity_type.weights,
        }

        async with async_db_session() as db:
            # 计算偏移量
            offset = (pageNo - 1) * pageSize
            # 模糊搜索
            keyword = keyWord + '%'

            print("entity_type")
            order = orderDict[orderBy]
            if entity_type.__tablename__ == "dql_strategy":
                select_entities = await db.execute(
                    select(entity_type)
                    .where(entity_type.name.like(keyword),
                           entity_type.is_delete == 0)
                    .order_by(order)
                    .offset(offset)
                    .limit(pageSize)
                )
            else:
                select_entities = await db.execute(
                    select(entity_type)
                    .where(entity_type.name.like(keyword))
                    .order_by(order)
                    .offset(offset)
                    .limit(pageSize)
                )

            result = select_entities.scalars().all()

            result_data = [{"uid": data.uid,
                            "name": data.name,
                            "description": data.description,
                            "subType": data.subType if entity_type.__tablename__ == "dql_indicators" else None,
                            "type": data.type,
                            "owner": data.owner,
                            "parameter": json.loads(data.parameters),
                            "createTime": data.createTime.strftime('%Y-%m-%d %H:%M:%S'),
                            } for data in result]

            return await response_base.success(data=result_data)

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"获取所有{entity_type.__name__}列表错误：{info}")
        print(f"获取所有{entity_type.__name__}列表错误信息：{info}")
        return Response(status_code=500, content="系统错误!")


# 封装成一个异步函数，然后在需要使用的地方直接调用该函数
async def fetch_trading_data(db, goods, period, model_classes,
                             begin_time=None, end_time=None,
                             lineId=0, name=None, period_tuple=None, class_name=None):
    # 需要使用到begintime的策略，即数据开始时间会影响
    need_begintime_class = ['atr_strategy.ATRStrategy',
                            'atr_strategyv1.ATRStrategy',
                            'bbtrend.BBTrendStrategy']

    try:
        result_data = cache.get(period_tuple)

        if result_data:
            print("缓存数据响应")
            return result_data

        # 1 查询中间表 交易品种表
        select_model_class, result = await select_goods_common(db, goods, model_classes)

        if not select_model_class:
            return False

        if begin_time and end_time:
            print("时段数据 开始执行时间：{}".format(datetime.datetime.now()))
            # 根据交易品种表的 table_name 字段查找主表，拿到交易历史数据后加入到backtrader的数据源中（开始时间 - 结束时间）
            if class_name is None:
                class_name = ['None']
            if class_name[0] in need_begintime_class:
                print('提前时间检测')
                # backtrader ATR回测特定查询，从起始时间再剪一天
                start_time = parser.parse(begin_time)
                end_time = parser.parse(end_time)

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
                print('正常时间检测')
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
            if name == "history":  # 历史数据
                print("历史数据")
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

                    details = await db.execute(select(select_model_class).where(
                        select_model_class.tradingGoods == result.trading_goods,
                                    select_model_class.platform == result.platform,
                                    select_model_class.type == period,
                                    select_model_class.tradeDateTime < formatted_datetime).order_by(
                                    select_model_class.tradeDateTime.desc()).limit(limit_num))

                    # 组织数据结构
                    results = details.scalars().all()

                else:
                    # 指标历史数据或最新数据查询
                    details = await db.execute(select(select_model_class).where(
                        select_model_class.tradingGoods == result.trading_goods,
                                    select_model_class.platform == result.platform,
                                    select_model_class.type == period).order_by(
                                    select_model_class.tradeDateTime.desc()).limit(limit_num))

                    # 组织数据结构
                    results = details.scalars().all()

            elif name == "latest":  # 最新数据
                print("最新数据")
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

                # 计算偏移量
                # 查询指定模型的数据
                details_data = select(select_model_class).where(
                    select_model_class.tradingGoods == result.trading_goods,
                    select_model_class.platform == result.platform,
                    select_model_class.type == period,
                    select_model_class.tradeDateTime > formatted_datetime).order_by(
                    select_model_class.tradeDateTime.desc()).limit(limit_num)

                detail = await db.execute(details_data)

                # 组织数据结构
                results = detail.scalars().all()

            elif name == "latest_new":  # 最新数据
                details_data = select(select_model_class).where(
                    select_model_class.tradingGoods == result.trading_goods,
                    select_model_class.platform == result.platform,
                    select_model_class.type == period
                ).order_by(desc(select_model_class.tradeDateTime)).limit(3000)

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

            # 保存缓存
            if period_tuple:
                cache[period_tuple] = result_list

            return result_list

    except Exception as e:
        info = traceback.format_exc()
        log.error("查询技术指标K线历史数据错误出错：{}".format(info))
        print("查询技术指标K线历史数据错误出错：{}".format(info))
        return []


async def get_indicator_data(request, data_type, name):
    try:
        indicator_request = await request.json()
        async with async_db_session() as db:
            result_data = []
            for request_item in indicator_request:
                if not request_item.get("lineId", 0) and data_type == "AfterKline":
                    # 只有 AfterKline 才是必须要lineId
                    return await response_base.fail(msg="lineId not found !", data=[])

                select_indicators = await db.execute(select(DqlIndicators).where(
                    DqlIndicators.uid == request_item.get("uid", 0)))

                indicators = select_indicators.scalars().first()
                if not indicators:
                    return await response_base.fail(msg="uids not found !", data=[])

                indicator_params = request_item.get("parameter", {})
                # 在参数中增加k线的品种和周期
                indicator_params['Kline_period'] = request_item.get("period", None)
                indicator_params['Kline_goods'] = request_item.get("goods", None)

                period = request_item.get("period", None)
                if period and period[0] in ['H', 'W', 'D', 'M']:
                    period_dict = {
                        "period": period,
                        "tradingGoods": request_item.get("goods"),
                        "IndicatorName": indicators.name,
                        "lineId": request_item.get("lineId"),
                        "indicatortype": data_type,
                        "begin_time": request_item.get("beginTime", None),
                        "end_time": request_item.get("endTime", None)
                    }
                    period_tuple = tuple(period_dict.items())
                else:
                    period_tuple = None

                trading_data = await fetch_trading_data(db, request_item.get("goods", None),
                                                        period,
                                                        model_classes, lineId=request_item.get("lineId", 0),
                                                        name=name,
                                                        begin_time=request_item.get("beginTime", None),
                                                        end_time=request_item.get("endTime", None),
                                                        period_tuple=period_tuple)

                if not trading_data:
                    continue

                cerebro = bt.Cerebro()
                df = pd.DataFrame(trading_data)
                df['datetime'] = pd.to_datetime(df['datetime'])
                df.set_index('datetime', inplace=True)
                data = PandasData(dataname=df)
                cerebro.adddata(data)
                try:
                    cerebro.addstrategy(indicator_classes.get(indicators.className),
                                        indicator_params, indicators.name, indicators.description)

                    result = cerebro.run(stdstats=True, tradehistory=True)

                    print("result:{}".format(result))

                    result_data_list = result[0].get_analysis()

                    data_dict = {
                        "uid": indicators.uid,
                        "pId": request_item.get("pId", None),
                        "index": request_item.get("index", 0),
                        "parameter": indicator_params,
                        "subType": indicators.subType,
                        "startPoint": result_data_list[1],
                        "endPoint": result_data_list[2],
                        "buyselldata": result_data_list[3] if len(result_data_list[3:4]) > 0 else {},
                        "data": result_data_list[0]
                    }
                    result_data.append(data_dict)
                except Exception as e:
                    info = traceback.format_exc()
                    log.error(f"技术指标K线{data_type} 数据错误：{info}  request_item:{request_item}")

        return await response_base.success(data=result_data)

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"获取技术指标K线{data_type}数据错误：{info}")
        print(f"获取技术指标K线{data_type}数据错误信息：{info}")
        return Response(status_code=500, content="系统错误!")


async def fetch_indicators(db: AsyncSession, uid: str):
    select_indicators = await db.execute(select(DqlStrategy).where(
        DqlStrategy.uid == uid, DqlStrategy.is_delete == 0))
    return select_indicators.scalars().first()


async def save_trader_result(traderResult, db, strategyUid, period):
    for row in traderResult:
        order = DqlOrder(
            tradingGoods=row.get('goodsId', ''),  # tradingGoods 和 goodsId 用同一个
            goodsId=row.get('goodsId', ''),
            period=period,
            tradeId=row.get('tradeid', 0),
            openPrice=row.get('openPrice', 0.0),
            openTime=row.get('openTime', ''),
            timestamp=row.get('timestamp', ''),
            closeTime=row.get('closeTime', None),
            orderType=row.get('orderType', ''),
            placeType=row.get('placeType', ''),
            size=row.get('size', 0.0),
            price=row.get('price', 0.0),
            stopLoss=row.get('stopLoss', 0.0),
            takeProfit=row.get('takeProfit', 0.0),
            taxes=row.get('taxes', 0.0),
            swap=row.get('swap', 0.0),
            commission=row.get('commission', 0.0),
            pnl=row.get('pnl', 0.0),
            spread=row.get('spread', 0.0),
            initialCash=row.get('initialCash', 0.0),
            klineId=row.get('klineId', 0),
            strategyUid=strategyUid,
        )
        db.add(order)

    await db.commit()
    log.info("新增订单信息成功！")



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


def calculate_consecutive_win_loss(account_list):
    consecutive_wins = 0
    consecutive_losses = 0
    win_count = 0
    loss_count = 0
    max_consecutive_wins = 0
    max_consecutive_losses = 0

    for trade in account_list:
        if trade["closeTime"]:
            if trade['pnl'] > 0:
                win_count += 1
                consecutive_wins += 1
                max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
                consecutive_losses = 0  # Reset consecutive losses
            elif trade['pnl'] < 0:
                loss_count += 1
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                consecutive_wins = 0  # Reset consecutive wins

    average_consecutive_wins = consecutive_wins / win_count if win_count > 0 else 0
    average_consecutive_losses = consecutive_losses / loss_count if loss_count > 0 else 0

    return {
        'averageConsecutiveWins': round(average_consecutive_wins, 2),
        'averageConsecutiveLosses': round(average_consecutive_losses, 2),
    }


# 计算 yieldRate, winRate, avgProfit
def calculate_trade_metrics(account_list, initial_cash):
    total_profit = sum(trade['pnl'] for trade in account_list if trade["closeTime"])
    total_trades = len(account_list)
    win_trades = len([trade for trade in account_list if trade['pnl'] > 0 and trade["closeTime"]])

    yield_rate = (total_profit / initial_cash) * 100 if initial_cash else 0
    win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
    avg_profit = total_profit / total_trades if total_trades > 0 else 0

    return {
        'yieldRate': round(yield_rate, 3),
        'winRate': round(win_rate, 3),
        'avgProfit': round(avg_profit, 3)
    }


# 计算 plr (盈亏比)
def calculate_plr(account_list):
    positive_pnl = [trade['pnl'] for trade in account_list if trade['pnl'] > 0 and trade["closeTime"]]
    negative_pnl = [trade['pnl'] for trade in account_list if trade['pnl'] < 0 and trade["closeTime"]]

    avg_profit = sum(positive_pnl) / len(positive_pnl) if positive_pnl else 0
    avg_loss = abs(sum(negative_pnl) / len(negative_pnl)) if negative_pnl else 0

    # 如果 avg_profit 或 avg_loss 为0，则替换为1
    avg_profit = avg_profit if avg_profit != 0 else 1
    avg_loss = avg_loss if avg_loss != 0 else 1

    plr = avg_profit / avg_loss

    return round(plr, 3)


# 计算最大回撤率 (mdr)
def calculate_mdr(account_list, initial_cash):
    max_drawdown = 0
    peak_value = initial_cash
    for trade in account_list:
        if trade["closeTime"]:
            peak_value = max(peak_value, peak_value + trade['pnl'])
            drawdown = (peak_value - (initial_cash + trade['pnl'])) / peak_value
            max_drawdown = max(max_drawdown, drawdown)

    return round(max_drawdown, 3)


# 计算最大资金使用率 (maxFUR)
def calculate_max_fur(account_list):
    max_fur = 0
    for trade in account_list:
        if trade["closeTime"]:
            # 假设 'size' 表示交易量, openPrice 表示开盘价格, closePrice 表示平仓价格
            margin_used = abs(trade['size'] * (trade['openPrice'] - trade['price']))
            max_fur = max(max_fur, margin_used)

    return round(max_fur, 3)


def statistics_from_orders(data: List[Dict[str, Any]], starting_cash=100000):
    # 只取orderType为close的订单，按timestamp升序
    orders = [x for x in data if x["orderType"] == "close"]
    orders.sort(key=lambda x: x["timestamp"])
    if not orders:
        return {}

    total_trades = len(orders)
    pnls = [o["pnl"] for o in orders]
    profits = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    # 基本盈亏相关
    total_net_profit = sum(pnls)
    total_profit = sum(profits)
    total_loss = abs(sum(losses))
    expected_payoff = total_net_profit / total_trades if total_trades else 0
    largest_profit = max(profits) if profits else 0
    largest_loss = min(losses) if losses else 0
    average_profit_trade = sum(profits) / len(profits) if profits else 0
    average_loss_trade = sum(losses) / len(losses) if losses else 0

    # 胜率、盈利比、盈亏比
    profit_trades = len(profits)
    loss_trades = len(losses)
    win_rate = profit_trades / total_trades if total_trades else 0
    profit_factor = total_profit / abs(total_loss) if total_loss else float('inf')
    plr = average_profit_trade / abs(average_loss_trade) if average_loss_trade else float('inf')
    avg_profit = total_net_profit / total_trades if total_trades else 0

    # 资金曲线、最大回撤、绝对回撤
    cash_curve = []
    cash = starting_cash
    min_cash = starting_cash
    max_cash = starting_cash
    max_drawdown = 0
    absolute_drawdown = 0
    peak = starting_cash

    for o in orders:
        cash += o["pnl"]
        cash_curve.append(cash)
        if cash > peak:
            peak = cash
        drawdown = peak - cash
        if drawdown > max_drawdown:
            max_drawdown = drawdown
        if cash < min_cash:
            min_cash = cash
        if starting_cash - cash > absolute_drawdown:
            absolute_drawdown = starting_cash - cash
        if cash > max_cash:
            max_cash = cash

    mdr = max_drawdown / max_cash if max_cash else 0   # 最大回撤率
    relative_losses = max_drawdown / peak if peak else 0

    # 连续统计
    cons_profit, cons_loss = 0, 0
    max_cons_profit, max_cons_loss = 0, 0
    max_cons_win, max_cons_loss_num = 0, 0
    tmp_cons_win, tmp_cons_loss = 0, 0
    cons_win_list, cons_loss_list = [], []
    for p in pnls:
        if p > 0:
            cons_profit += p
            cons_loss = 0
            tmp_cons_win += 1
            if tmp_cons_loss > 0:
                cons_loss_list.append(tmp_cons_loss)
                tmp_cons_loss = 0
        elif p < 0:
            cons_loss += p
            cons_profit = 0
            tmp_cons_loss += 1
            if tmp_cons_win > 0:
                cons_win_list.append(tmp_cons_win)
                tmp_cons_win = 0
        else:
            cons_profit = 0
            cons_loss = 0
            if tmp_cons_win > 0:
                cons_win_list.append(tmp_cons_win)
                tmp_cons_win = 0
            if tmp_cons_loss > 0:
                cons_loss_list.append(tmp_cons_loss)
                tmp_cons_loss = 0
        if cons_profit > max_cons_profit:
            max_cons_profit = cons_profit
        if cons_loss < max_cons_loss:
            max_cons_loss = cons_loss
        if tmp_cons_win > max_cons_win:
            max_cons_win = tmp_cons_win
        if tmp_cons_loss > max_cons_loss_num:
            max_cons_loss_num = tmp_cons_loss
    # 补最后一段
    if tmp_cons_win > 0:
        cons_win_list.append(tmp_cons_win)
    if tmp_cons_loss > 0:
        cons_loss_list.append(tmp_cons_loss)
    average_consecutive_wins = sum(cons_win_list) / len(cons_win_list) if cons_win_list else 0
    average_consecutive_losses = sum(cons_loss_list) / len(cons_loss_list) if cons_loss_list else 0

    # 多空单
    short_positions = [o for o in orders if o["size"] < 0]
    long_positions = [o for o in orders if o["size"] > 0]
    short_positions_num = len(short_positions)
    long_positions_num = len(long_positions)
    short_positions_ratio = short_positions_num / total_trades if total_trades else 0
    long_positions_ratio = long_positions_num / total_trades if total_trades else 0

    # 获利单百分比、亏损单百分比
    profit_trades_ratio = profit_trades / total_trades if total_trades else 0
    loss_trades_ratio = loss_trades / total_trades if total_trades else 0

    # 收益率
    yield_rate = total_net_profit / starting_cash if starting_cash else 0

    # 是否爆仓
    is_bursted = any(c <= 0 for c in cash_curve)

    trade_metrics = calculate_trade_metrics(data, starting_cash)
    result = {
        "startingCash": starting_cash,
        "FreeMargin": round(starting_cash + total_net_profit, 2),
        "totalProfit": round(total_profit, 2),
        "totalLoss": round(total_loss, 2),
        "expectedPayoff": round(expected_payoff, 2),
        "absoluteDrawdown": round(absolute_drawdown, 2),
        "maximalDrawdown": round(max_drawdown, 2),
        "relativeLosses": round(relative_losses, 4),
        "totalTrades": total_trades,
        "shortPositions": short_positions_num,
        "longPositions": long_positions_num,
        "profitTrades": profit_trades,
        "lossTrades": loss_trades,
        "largestProfit": largest_profit,
        "largestLoss": largest_loss,
        "averageProfitTrade": round(average_profit_trade, 2),
        "averageLossTrade": average_loss_trade,
        "maximalConsecutiveProfit": max_cons_profit,
        "maximalConsecutiveLoss": max_cons_loss,
        "maximumConsecutiveWins": max_cons_win,
        "maximumConsecutiveLosses": max_cons_loss_num,
        "averageConsecutiveWins": average_consecutive_wins,
        "averageConsecutiveLosses": average_consecutive_losses,
        "ProfitFactor": round(profit_factor, 2),
        "shortPositionsRatio": round(short_positions_ratio, 2),
        "longPositionsRatio": round(long_positions_ratio, 2),
        "profitTradesRatio": round(profit_trades_ratio, 2),
        "lossTradesRatio": round(loss_trades_ratio, 2),
        "yieldRate": trade_metrics["yieldRate"],
        "winRate": trade_metrics["winRate"],
        "plr": calculate_plr(data),
        "avgProfit": trade_metrics["avgProfit"],
        "mdr": calculate_mdr(data, starting_cash),
        "isBursted": is_bursted,
        "maxFUR": calculate_max_fur(data),
    }
    return result

