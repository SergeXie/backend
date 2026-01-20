import datetime
import pymysql
import bisect
from sqlalchemy import select, create_engine
import backtrader.indicators as btind
import backtrader as bt
from backtrader.feeds import PandasData
import time
import pandas as pd
import os
import pickle

# ====================== 自定义模块导入 ======================
# 请确保这些文件在你的 utils/module 目录下
from utils.module.zigzag_calculator_byclass import ZigZagCalculator
from utils.module.wm_pattern_recognizer import WMPatternRecognizer2

# ====================== 数据库配置 ======================
db_url = 'mysql+pymysql://cmdb:cmdb123456@192.168.1.126/dql'
engine = create_engine(db_url, pool_recycle=3600, echo=False)

# ====================== 内存缓存配置 (用于短时缓存) ======================
CACHE = {}
CACHE_EXPIRE_SECONDS = 3600


def get_cache_key(goods, periods, endTime):
    return f"{goods}_{periods}_{endTime}"


def get_cached_result(goods, periods, endTime):
    key = get_cache_key(goods, periods, endTime)
    if key not in CACHE:
        return None
    expire_time, result = CACHE[key]
    if datetime.datetime.now() > expire_time:
        del CACHE[key]
        return None
    return result


def set_cache_result(goods, periods, endTime, result):
    key = get_cache_key(goods, periods, endTime)
    expire_time = datetime.datetime.now() + datetime.timedelta(seconds=CACHE_EXPIRE_SECONDS)
    CACHE[key] = (expire_time, result)


# ====================== 磁盘存档管理器 (新增) ======================
class DiskCacheManager:
    """
    负责将长周期的历史计算结果持久化到磁盘 (Pickle格式)
    """

    def __init__(self, cache_dir='./dataset/wm'):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir)
            except Exception as e:
                print(f"创建缓存目录失败: {e}")

    def _get_path(self, goods, periods, split_time):
        # 将时间字符串转换为安全的文件名
        safe_time = str(split_time).replace(':', '').replace(' ', '_').replace('-', '')
        filename = f"{goods}_{periods}_{safe_time}.pkl"
        return os.path.join(self.cache_dir, filename)

    def save(self, goods, periods, split_time, data):
        path = self._get_path(goods, periods, split_time)
        try:
            with open(path, 'wb') as f:
                pickle.dump(data, f)
            print(f"💾 [磁盘存档] 已保存至: {path}, 数据条数: {len(data)}")
        except Exception as e:
            print(f"❌ [磁盘存档] 保存失败: {e}")

    def load(self, goods, periods, split_time):
        path = self._get_path(goods, periods, split_time)
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                print(f"📂 [磁盘存档] 已加载: {path}, 数据条数: {len(data)}")
                return data
            except Exception as e:
                print(f"⚠️ [磁盘存档] 读取失败 (可能文件损坏): {e}")
                return None
        return None


# ====================== 数据库查询辅助 ======================
def select_goods_common(goods):
    conn = pymysql.connect(
        host='192.168.1.126',
        user='cmdb',
        password='cmdb123456',
        database='dql'
    )
    cursor = conn.cursor()
    query = f"SELECT * FROM dql_goods WHERE goods='{goods}' "
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    conn.close()

    if not results:
        raise ValueError(f"未找到商品: {goods}")

    single_record = results[0]
    return single_record[3], single_record[4]


# ====================== 数据加载 ======================
def get_kline_data_optimized(goods, periods, endTime, beginTime):
    start_time = time.perf_counter()
    try:
        good_table, tradingGoods = select_goods_common(goods)
    except Exception as e:
        print(e)
        return None

    print(f"[{tradingGoods}] 数据加载请求: {beginTime} -> {endTime}")

    sql = f"""
        SELECT 
            tradeDateTime as datetime,
            opening as open,
            high,
            low,
            closed as close,
            vol as volume,
            pkId as klineId,
            digits,
            spread
        FROM {good_table}
        WHERE type = %(period)s
          AND tradingGoods = %(goods)s
          AND tradeDateTime >= %(begin)s 
          AND tradeDateTime <= %(end)s
        ORDER BY tradeDateTime ASC
    """
    params = {
        "period": periods,
        "goods": tradingGoods,
        "begin": beginTime,
        "end": endTime
    }

    try:
        df = pd.read_sql(sql, engine, params=params)
        if df.empty:
            print(f"⚠️ 警告: 该区间未查询到数据 ({beginTime} - {endTime})")
            return None

        numeric_cols = ['open', 'high', 'low', 'close']
        df[numeric_cols] = df[numeric_cols].astype(float)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)

        data = PandasDataPlus(dataname=df)
        print(f"数据加载完成，行数: {len(df)}，用时: {time.perf_counter() - start_time:.4f}秒")
        return data

    except Exception as e:
        print(f"❌ 数据加载出错: {e}")
        return None


class PandasDataPlus(bt.feeds.PandasData):
    lines = ('pkId', 'klineId')
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


# ====================== 策略类 ======================
class ResWMpredictByMathData(bt.Strategy):
    def __init__(self):
        self.result_data_dict = dict()
        self.Id_TS_dict = {}
        self.Ts_to_hloc = {}
        self.inp_depth = 12
        self.all_kline_data = []

        # 实例化算法类
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer2()

        # 确保数据长度足够
        self.addminperiod(self.inp_depth)

        # 耗时统计
        self.next_total_time = 0.0
        self.ts_list = []

        # 【优化1】预先缓存 Data Lines 的引用，减少 next 中的属性查找开销
        self.d_klineId = self.data.klineId
        self.d_open = self.data.open
        self.d_high = self.data.high
        self.d_low = self.data.low
        self.d_close = self.data.close
        self.d_volume = self.data.volume

        # 【优化2】预先计算所有时间字符串
        # 警告：这是基于 runonce=True (默认) 的假设，数据已全部加载
        # 这消除了 next() 中极慢的 strftime 操作
        print("正在预处理时间索引...")
        t0 = time.perf_counter()
        self.all_date_strings = [
            bt.num2date(x).strftime('%Y-%m-%d %H:%M:%S')
            for x in self.data.datetime.array
        ]
        print(f"时间预处理完成，耗时: {time.perf_counter() - t0:.4f}秒")

    def next(self):
        t_start = time.perf_counter()

        # 检查长度
        if len(self) < self.inp_depth:
            self.next_total_time += time.perf_counter() - t_start
            return

        # 【优化3】直接通过索引获取预处理好的时间字符串
        # len(self) 返回的是当前已处理的总长度，-1 即为当前索引
        idx = len(self) - 1
        current_ts_str = self.all_date_strings[idx]

        # 获取当前 klineId (转int)
        k_id = int(self.d_klineId[0])

        self.Id_TS_dict[k_id] = current_ts_str

        # 【优化4】构造字典时直接使用缓存的 line 引用，不再调用 self.data.xxx
        current_kline_data = {
            "kLineId": k_id,
            "timestamp": current_ts_str,
            "open": self.d_open[0],
            "high": self.d_high[0],
            "low": self.d_low[0],
            "close": self.d_close[0],
            "volume": self.d_volume[0],
        }

        self.all_kline_data.append(current_kline_data)
        self.ts_list.append(current_ts_str)

        self.Ts_to_hloc[current_ts_str] = [
            self.d_high[0], self.d_low[0], self.d_open[0], self.d_close[0]
        ]

        # 处理ZigZag点
        self.zigzag_calculator.process_kline(current_kline_data)

        self.next_total_time += time.perf_counter() - t_start

    def stop(self):
        start_time = time.perf_counter()
        # print(f"⏱️ next() 方法总耗时: {self.next_total_time:.6f} 秒")

        zigzag_points = self.zigzag_calculator.get_zigzag_points(as_dict=False)

        # 批量处理
        min_points = 5
        if len(zigzag_points) >= min_points:
            # 这里如果 zigzag 点很多，循环切片依然耗时，但比 next 里的开销小
            for i in range(min_points, len(zigzag_points) + 1):
                window = zigzag_points[i - min_points: i]
                self.pattern_recognizer.analyze_zigzag_points(window)

        # print(f"stop后处理用时: {time.perf_counter() - start_time:.6f}秒")

    def get_analysis(self):
        start_time = time.perf_counter()

        wm_pattern = self.pattern_recognizer.get_pattern_titles()
        ts_list = self.ts_list
        kline_data = self.all_kline_data

        # 二分查找快速匹配 K线数据
        for pattern in wm_pattern:
            start_idx = bisect.bisect_left(ts_list, pattern.start_timestamp)
            end_idx = bisect.bisect_right(ts_list, pattern.end_timestamp)
            pattern.target_klines = kline_data[start_idx:end_idx]

        # print(f"get_analysis匹配用时: {time.perf_counter() - start_time:.6f}秒")
        return wm_pattern


# ====================== 基础运行函数 ======================
def run_strategy(goods, periods, endTime, beginTime, force_refresh=False):
    """
    基础策略运行函数，执行一次 Backtrader 回测
    """
    # 1. 内存缓存检查 (仅在非强制刷新时)

    cerebro = bt.Cerebro()

    # 加载数据
    data = get_kline_data_optimized(goods, periods, endTime, beginTime)
    if data is None:
        return []

    cerebro.adddata(data)
    cerebro.addstrategy(ResWMpredictByMathData)

    # 运行策略
    # print(f"🚀,{goods},{periods} 开始计算: {beginTime} 至 {endTime}")
    t_start = time.perf_counter()
    result = cerebro.run(stdstats=False, runonce=True)

    # 获取结果
    trader_return = result[0].get_analysis()

    # 写入内存缓存
    set_cache_result(goods, periods, endTime, trader_return)
    # print(f"✅ 计算完成，耗时: {time.perf_counter() - t_start:.4f}秒，发现形态数: {len(trader_return)}")

    return trader_return


# ====================== 增量运行函数 (核心逻辑) ======================
def run_strategy_incremental(goods, periods, history_split_time, current_end_time,
                             history_begin_time="2000-01-01 00:00:00"):
    """
    增量运行策略：
    1. 检查是否有截止到 history_split_time 的磁盘存档。
    2. 如果没有，计算历史数据并保存。
    3. 如果有，加载存档，并计算 [history_split_time - buffer] 到 [current_end_time] 的新数据。
    4. 合并结果。
    """
    disk_manager = DiskCacheManager()

    # --- 1. 获取历史存档 ---
    history_patterns = disk_manager.load(goods, periods, history_split_time)

    if history_patterns is None:
        print(f"⚡ 未检测到历史存档，开始全量计算历史部分 ({history_begin_time} -> {history_split_time})...")
        history_patterns = run_strategy(goods, periods, history_split_time, history_begin_time, force_refresh=True)
        # 保存到磁盘
        disk_manager.save(goods, periods, history_split_time, history_patterns)

    # --- 2. 准备增量计算区间 (包含回溯缓冲) ---
    # 我们不能只从 split_time 开始算，因为 ZigZag 需要上下文。
    # 这里我们往前推 30 天 (针对 M5/H1 周期足够，日线可适当增加)

    split_dt = pd.to_datetime(history_split_time)
    buffer_days = 60  # 缓冲期，保证ZigZag计算稳定
    overlap_start_dt = split_dt - datetime.timedelta(days=buffer_days)
    overlap_start_str = overlap_start_dt.strftime('%Y-%m-%d %H:%M:%S')

    print(f"⚡ 开始增量计算 (含回溯缓冲): {overlap_start_str} -> {current_end_time}")

    # 强制刷新计算新的一段，不走内存缓存
    new_patterns_raw = run_strategy(goods, periods, current_end_time, overlap_start_str, force_refresh=True)

    # --- 3. 结果过滤与合并 ---
    if not history_patterns:
        # 如果历史为空（虽然前面已经处理了，但防万一），直接返回新的
        return new_patterns_raw

    # 获取历史记录中最后一个形态的结束时间
    # 假设 pattern 对象有 end_timestamp 属性，且格式为字符串 'YYYY-MM-DD HH:MM:SS'
    last_hist_pattern = history_patterns[-1]
    last_hist_ts = last_hist_pattern.end_timestamp

    print(f"🔍 正在拼接... 历史最后形态时间: {last_hist_ts}")

    valid_new_patterns = []
    skipped_count = 0

    for p in new_patterns_raw:
        # 字符串比较：保留结束时间晚于历史最后一条记录的形态
        # 这样避免了重复记录，也解决了边界不一致的问题
        if p.end_timestamp > last_hist_ts:
            valid_new_patterns.append(p)
        else:
            skipped_count += 1

    print(
        f"📊 合并统计: 历史存档 {len(history_patterns)} 条 + 新增有效 {len(valid_new_patterns)} 条 (重叠过滤掉 {skipped_count} 条)")

    # 列表拼接
    final_result = history_patterns + valid_new_patterns

    return final_result


# ====================== 测试入口 ======================
if __name__ == "__main__":
    # 配置参数
    test_goods = "FPG-XAUUSD"
    test_periods = "M5"

    # 定义“历史”和“现在”的分割线
    # 第一次运行时，会计算 2000-01-01 到 2025-01-01 的数据并存为pkl文件
    # 下次运行时，直接读取pkl，只计算 2025-01-01 往后的数据
    HISTORY_SPLIT_POINT = "2025-01-01 00:00:00"

    # 当前最新时间 (实际使用中可以用 datetime.datetime.now().strftime...)
    # CURRENT_NOW = "2025-10-20 00:00:00"
    CURRENT_NOW = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    start_t = time.perf_counter()

    # 调用增量运行函数
    final_patterns = run_strategy_incremental(
        goods=test_goods,
        periods=test_periods,
        history_split_time=HISTORY_SPLIT_POINT,
        current_end_time=CURRENT_NOW,
        history_begin_time="2000-01-01 00:00:00"  # 这里为了测试快一点写了2020，你可以改成2000
    )

    print(f"🎉 最终结果总数: {len(final_patterns)}")
    print(f"🎉 全流程总耗时: {time.perf_counter() - start_t:.4f}秒")

    # 简单打印最后几个结果验证
    if final_patterns:
        print("--- 最新生成的3个形态 ---")
        for p in final_patterns[-3:]:

            print(f"形态: {p.value} | 开始: {p.start_timestamp} | 结束: {p.end_timestamp}")