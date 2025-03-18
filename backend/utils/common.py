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
    TradingIndex, TradingIndex2, TradingFPG2, DqlStrategy
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
from utils.timezone import timezone
from dateutil import parser


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


async def fetch_indicators(db: AsyncSession, uid: int):
    select_indicators = await db.execute(select(DqlStrategy).where(
        DqlStrategy.uid == uid, DqlStrategy.is_delete == 0))
    return select_indicators.scalars().first()