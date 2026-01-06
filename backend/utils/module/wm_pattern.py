import datetime
import backtrader as bt
import numpy as np
import pandas as pd
import pymysql
import utils.common
from sqlalchemy import select
import backtrader.indicators as btind
# from utils.module.zigzag_calculator import ZigZagCalculator
from utils.module.zigzag_calculator_byclass import ZigZagCalculator

from utils.module.wm_pattern_recognizer import WMPatternRecognizer2
from database.db_mysql import async_db_session

from models.dql_platform import DplGoodsTest

# ====================== 内存缓存核心配置 ======================
# 缓存结构：{缓存键: (过期时间, trader_return结果)}
CACHE = {}
# 缓存有效期（可自定义，示例：1小时）
CACHE_EXPIRE_SECONDS = 3600


def get_cache_key(goods, periods, endTime):
    """
    生成唯一缓存键（仅基于goods、periods、endTime）
    满足：这三个参数相同即复用缓存，忽略beginTime
    """
    return f"{goods}_{periods}_{endTime}"


def get_cached_result(goods, periods, endTime):
    """读取缓存，若过期/不存在则返回None"""
    key = get_cache_key(goods, periods, endTime)
    if key not in CACHE:
        return None

    expire_time, result = CACHE[key]
    # 检查缓存是否过期
    if datetime.datetime.now() > expire_time:
        del CACHE[key]  # 删除过期缓存
        return None
    return result


def set_cache_result(goods, periods, endTime, result):
    """设置缓存（带过期时间）"""
    key = get_cache_key(goods, periods, endTime)
    expire_time = datetime.datetime.now() + datetime.timedelta(seconds=CACHE_EXPIRE_SECONDS)
    CACHE[key] = (expire_time, result)

def get_klines_in_range(all_klines, start_timestamp, end_timestamp):
    """
    获取指定时间范围内的所有K线

    参数:
        all_klines: 所有K线数据列表，每个元素为包含'timestamp'键的字典
        start_timestamp: 起始时间字符串（如'2025-08-11 01:00:00'）
        end_timestamp: 结束时间字符串（如'2025-08-12 10:30:00'）

    返回:
        时间范围内的K线列表
    """
    # 筛选出时间在[start, end]范围内的K线
    return [
        kline for kline in all_klines
        if start_timestamp <= kline['timestamp'] <= end_timestamp
    ]

def select_goods_common(goods):
    conn = pymysql.connect(
        host='192.168.1.126',
        user='cmdb',
        password='cmdb123456',
        database='dql'
    )
    cursor = conn.cursor()
    # 执行查询
    query = (
        f"SELECT * FROM dql_goods WHERE goods='{goods}' "
    )
    cursor.execute(query)
    results = cursor.fetchall()

    cursor.close()
    conn.close()
    single_record = results[0]
    print('测试',single_record[3])
    return single_record[3], single_record[4]


# ====================== 原有数据读取与策略逻辑 ======================
def get_kline_data(goods, periods, endTime, beginTime):
    # 周期（注：原代码中硬编码为M30，若需适配periods参数可修改）
    period = periods
    # 交易品种（注：原代码中硬编码为XAUUSD，若需适配goods参数可修改）
    good_tabel, tradingGoods= select_goods_common(goods)
    print(good_tabel, tradingGoods)
    # tradingGoods = "XAUUSD"
    conn = pymysql.connect(
        host='192.168.1.126',
        user='cmdb',
        password='cmdb123456',
        database='dql'
    )
    cursor = conn.cursor()
    # 执行查询
    query = (
        f"SELECT * FROM {good_tabel} WHERE type='{period}' AND "
        f"tradingGoods='{tradingGoods}' AND "
        f"tradeDateTime >= '{beginTime}' AND tradeDateTime <= '{endTime}' "
        f"ORDER BY tradeDateTime DESC"
    )
    cursor.execute(query)
    results = cursor.fetchall()
    results = reversed(results)  # 恢复时间正序

    # 关闭数据库连接
    cursor.close()
    conn.close()

    # 构造数据列表
    results_data_list = [
        {
            "pkId": x[0],
            "datetime": x[4].strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(x[9]),
            "high": float(x[11]),
            "low": float(x[12]),
            "close": float(x[10]),
            "volume": x[13],
            "openinterest": 0,
            "klineId": x[0],
            "digits": x[5],
            "spread": x[6]
        }
        for x in results
    ]

    # 转换为DataFrame并适配backtrader
    df = pd.DataFrame(results_data_list)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    data = PandasData(dataname=df)
    return data


class PandasData(bt.feeds.PandasData):
    lines = ('pkId', 'open', 'high', 'low', 'close', 'volume', 'openinterest', 'klineId')
    params = (
        ('pkId', -1),
        ('open', -1),
        ('high', -1),
        ('low', -1),
        ('close', -1),
        ('volume', -1),
        ('openinterest', None),
        ('klineId', -1),
    )


class ResWMpredictByMathData(bt.Strategy):
    def __init__(self):
        self.result_data_dict = dict()
        self.Id_TS_dict = {}
        self.Ts_to_hloc = {}
        self.inp_depth = 12

        self.BarState = []
        self.BarStateText = []
        self.W_sum = 0
        self.M_sum = 0
        self.all_kline_data = []

        # 实例化算法类
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer2()

        # 确保数据长度足够
        self.addminperiod(self.inp_depth)

    def next(self):
        self.Id_TS_dict[int(self.data.klineId[0])] = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')

        if len(self) < self.inp_depth:
            return

        # 构造当前K线数据
        current_kline_data = {
            "kLineId": self.data.klineId[0],
            "timestamp": self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "open": self.data.open[0],
            "high": self.data.high[0],
            "low": self.data.low[0],
            "close": self.data.close[0],
            "volume": self.data.volume[0],
        }
        self.all_kline_data.append(current_kline_data)
        self.Ts_to_hloc[self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')] = [
            self.data.high[0], self.data.low[0], self.data.open[0], self.data.close[0]
        ]

        # 处理ZigZag点
        self.zigzag_calculator.process_kline(current_kline_data)

    def stop(self):
        # 分析ZigZag形态
        zigzag_points = self.zigzag_calculator.get_zigzag_points(as_dict=False)
        zigzag_list = []
        for zig in zigzag_points:
            zigzag_list.append(zig)
            self.pattern_recognizer.analyze_zigzag_points(zigzag_list)



    def get_analysis(self):
        # 返回形态识别结果
        wm_pattern = self.pattern_recognizer.get_pattern_titles()

        for pattern in wm_pattern:
            # print('pattern', pattern)
            # 获取该模式时间范围内的所有K线
            target_klines = get_klines_in_range(
                all_klines=self.all_kline_data,  # 替换为实际的全量K线数据
                start_timestamp=pattern.start_timestamp,
                end_timestamp=pattern.end_timestamp
            )
            pattern.target_klines = target_klines



        return self.pattern_recognizer.get_pattern_titles()


# ====================== 核心策略执行函数（适配缓存规则） ======================
def run_strategy(goods, periods, endTime, beginTime, force_refresh=False):
    """
    执行策略，优先使用缓存（仅匹配goods、periods、endTime）
    :param goods: 交易品种
    :param periods: 周期
    :param endTime: 结束时间
    :param beginTime: 开始时间（不参与缓存匹配）
    :param force_refresh: 是否强制刷新缓存（忽略现有缓存，重新计算）
    :return: trader_return 形态识别结果
    """
    print('查看参数',goods, periods, endTime, beginTime)
    # 1. 优先读取缓存（强制刷新时跳过）
    if not force_refresh:
        cached_result = get_cached_result(goods, periods, endTime)
        if cached_result is not None:
            print(f"✅ 使用缓存（键：{get_cache_key(goods, periods, endTime)}）")
            return cached_result

    # 2. 无缓存/强制刷新时，执行原逻辑
    print(f"🔄 无缓存，开始计算（goods={goods}, periods={periods}, endTime={endTime}）")
    cerebro = bt.Cerebro()
    data = get_kline_data(goods, periods, endTime, beginTime)
    cerebro.adddata(data)
    cerebro.addstrategy(ResWMpredictByMathData)
    result = cerebro.run()

    # 3. 获取计算结果
    trader_return = result[0].get_analysis()

    # 4. 写入缓存
    set_cache_result(goods, periods, endTime, trader_return)
    print(f"💾 计算结果已写入缓存（键：{get_cache_key(goods, periods, endTime)}）")

    return trader_return


# ====================== 测试示例 ======================
if __name__ == "__main__":
    # 测试参数
    test_goods = "FPG-XAUUSD"
    test_periods = "M5"
    test_endTime = "2025-01-10"
    test_beginTime1 = "2020-01-01"
    test_beginTime2 = "2025-01-05"  # 不同的beginTime，应复用缓存

    # 第一次调用：无缓存，执行计算并写入
    res1 = run_strategy(test_goods, test_periods, test_endTime, test_beginTime1)
    # # 第二次调用：相同goods/periods/endTime，不同beginTime → 复用缓存
    # res2 = run_strategy(test_goods, test_periods, test_endTime, test_beginTime2)
    # # 第三次调用：强制刷新缓存
    # res3 = run_strategy(test_goods, test_periods, test_endTime, test_beginTime1, force_refresh=True)
    #
    # print("\n结果验证：")
    # print(f"res1与res2是否一致（缓存复用）：{res1 == res2}")
    # print(f"res1与res3是否一致（强制刷新）：{res1 == res3}")