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
import json
import ast
from dataclasses import dataclass, field, fields, asdict
from typing import List, Dict, Optional

# ====================== 自定义模块导入 ======================
# 请确保这些模块路径在你的项目中是正确的
from utils.module.zigzag_calculator_byclass import ZigZagCalculator
from utils.module.wm_pattern_recognizer import WMPatternRecognizer2
from utils.module.wm_pattern_recognizer import StandardMPattern, StandardWPattern, StandardPattern, PatternBase

# ====================== 数据库配置 ======================
db_url = 'mysql+pymysql://cmdb:cmdb123456@192.168.1.126/dql'
engine = create_engine(db_url, pool_recycle=3600, echo=False)

# ====================== ORM 模型定义 ======================
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Float, and_
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class WMPatternResult(Base):
    """
    用于存储计算出的 WM 形态结果
    """
    __tablename__ = 'dql_wm_patterns_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    goods = Column(String(50), index=True, nullable=False)
    period = Column(String(20), index=True, nullable=False)

    # 形态的关键时间点
    start_timestamp = Column(String(30))
    end_timestamp = Column(String(30), index=True)

    # 形态名称 (如: M形态, W1形态)
    pattern_title = Column(String(100))

    # 使用 JSON 类型存储完整的形态数据 (包含 points, target_klines 等)
    # MySQL 5.7+ 的 JSON 类型会自动处理序列化/反序列化
    detail_data = Column(JSON)

    created_at = Column(DateTime, default=datetime.datetime.now)


Session = sessionmaker(bind=engine)


# ====================== 数据库缓存管理器 (核心修改) ======================
class DatabaseCacheManager:
    def __init__(self):
        pass

    def _serialize_pattern(self, p: StandardPattern) -> dict:
        """
        将 StandardPattern 对象转换为可存入数据库的字典。
        现在包含 target_klines。
        """
        # 1. 将 dataclass 转为字典
        p_dict = asdict(p)

        # 2. 数据清理/检查
        # 之前我们删除了 target_klines，现在保留它。
        # target_klines 是 List[Dict]，可以直接被 MySQL JSON 字段支持。

        # 可选：如果 target_klines 为 None，可以初始化为空列表，方便后续处理
        if p_dict.get('target_klines') is None:
            p_dict['target_klines'] = []

        return {
            "start_timestamp": p.start_timestamp,
            "end_timestamp": p.end_timestamp,
            "pattern_title": p.value,
            "detail_data": p_dict  # 包含 target_klines 的完整数据
        }

    def _deserialize_pattern(self, db_row: WMPatternResult) -> StandardPattern:
        """
        将数据库行数据还原为 StandardMPattern 或 StandardWPattern 对象。
        """
        # 1. 获取 JSON 数据 (SQLAlchemy 会自动将 JSON 列转为 Python 字典)
        data = db_row.detail_data if db_row.detail_data else {}

        # 2. 确定目标类
        pattern_title = db_row.pattern_title or data.get('value', '')

        if 'W' in pattern_title:
            target_cls = StandardWPattern
        else:
            target_cls = StandardMPattern  # 默认为 M

        # 3. 过滤有效字段并构造参数
        valid_fields = {f.name for f in fields(target_cls)}
        init_kwargs = {}

        for k, v in data.items():
            if k in valid_fields:
                init_kwargs[k] = v

        # 4. 确保 target_klines 存在
        # 如果数据库里的 JSON 这一项是 null 或不存在，我们给它补一个空列表或 None
        if 'target_klines' in valid_fields and 'target_klines' not in init_kwargs:
            init_kwargs['target_klines'] = []

        # 5. 实例化
        try:
            return target_cls(**init_kwargs)
        except Exception as e:
            # 增加一些容错日志
            print(f"⚠️ [DB反序列化] 转换失败 ID: {db_row.id}, 类型: {pattern_title}, 错误: {e}")
            return None

    def load_history(self, goods, periods, split_time) -> List[StandardPattern]:
        """
        从数据库加载 <= split_time 的所有历史形态
        """
        session = Session()
        try:
            results = session.query(WMPatternResult).filter(
                WMPatternResult.goods == goods,
                WMPatternResult.period == periods,
                WMPatternResult.end_timestamp <= split_time
            ).order_by(WMPatternResult.end_timestamp.asc()).all()

            if not results:
                return []

            patterns = []
            for r in results:
                p_obj = self._deserialize_pattern(r)
                if p_obj:
                    patterns.append(p_obj)

            # 可以在这里打印一下第一条数据的 target_klines 长度，确认是否加载成功
            if patterns:
                first_len = len(patterns[0].target_klines) if patterns[0].target_klines else 0
                print(f"📂 [DB读取] 已加载 {len(patterns)} 条历史数据 (首条K线数: {first_len})")

            return patterns
        except Exception as e:
            print(f"⚠️ [DB读取] 失败: {e}")
            return []
        finally:
            session.close()

    def save_bulk(self, goods, periods, patterns: List[StandardPattern]):
        """
        批量保存形态数据
        """
        if not patterns:
            return

        session = Session()
        try:
            orm_objects = []
            for p in patterns:
                data = self._serialize_pattern(p)

                obj = WMPatternResult(
                    goods=goods,
                    period=periods,
                    start_timestamp=data['start_timestamp'],
                    end_timestamp=data['end_timestamp'],
                    pattern_title=data['pattern_title'],
                    detail_data=data['detail_data']
                )
                orm_objects.append(obj)

            session.add_all(orm_objects)
            session.commit()
            print(f"💾 [DB保存] 已写入数据库: {len(orm_objects)} 条 (含target_klines)")
        except Exception as e:
            session.rollback()
            print(f"❌ [DB保存] 失败: {e}")
        finally:
            session.close()


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
    # ... (保持不变，省略以节省空间) ...
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

        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer2()

        self.addminperiod(self.inp_depth)

        self.next_total_time = 0.0
        self.ts_list = []

        self.d_klineId = self.data.klineId
        self.d_open = self.data.open
        self.d_high = self.data.high
        self.d_low = self.data.low
        self.d_close = self.data.close
        self.d_volume = self.data.volume

        self.all_date_strings = [
            bt.num2date(x).strftime('%Y-%m-%d %H:%M:%S')
            for x in self.data.datetime.array
        ]

    def next(self):
        if len(self) < self.inp_depth:
            return

        idx = len(self) - 1
        current_ts_str = self.all_date_strings[idx]
        k_id = int(self.d_klineId[0])

        self.Id_TS_dict[k_id] = current_ts_str

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

        self.zigzag_calculator.process_kline(current_kline_data)

    def stop(self):
        zigzag_points = self.zigzag_calculator.get_zigzag_points(as_dict=False)
        min_points = 5
        if len(zigzag_points) >= min_points:
            for i in range(min_points, len(zigzag_points) + 1):
                window = zigzag_points[i - min_points: i]
                self.pattern_recognizer.analyze_zigzag_points(window)

    def get_analysis(self):
        wm_pattern = self.pattern_recognizer.get_pattern_titles()
        ts_list = self.ts_list
        kline_data = self.all_kline_data

        for pattern in wm_pattern:
            # 填充 target_klines
            start_idx = bisect.bisect_left(ts_list, pattern.start_timestamp)
            end_idx = bisect.bisect_right(ts_list, pattern.end_timestamp)

            # 这是一个 List[Dict]，会被保存到 detail_data 中
            pattern.target_klines = kline_data[start_idx:end_idx]

        return wm_pattern


# ====================== 基础运行函数  ======================
def run_strategy(goods, periods, endTime, beginTime):
    cerebro = bt.Cerebro()
    data = get_kline_data_optimized(goods, periods, endTime, beginTime)
    if data is None:
        return []

    cerebro.adddata(data)
    cerebro.addstrategy(ResWMpredictByMathData)
    result = cerebro.run(stdstats=False, runonce=True)
    return result[0].get_analysis()


# ====================== 增量运行函数 ======================
def run_strategy_incremental(goods, periods, history_split_time, current_end_time,
                             history_begin_time="2000-01-01 00:00:00"):
    db_manager = DatabaseCacheManager()

    # 1. 尝试从数据库加载历史 (现在包含 target_klines)
    history_patterns = db_manager.load_history(goods, periods, history_split_time)

    if not history_patterns:
        print(f"⚡ 未检测到数据库历史记录，开始全量计算历史部分...")
        history_patterns = run_strategy(goods, periods, history_split_time, history_begin_time)
        if history_patterns:
            db_manager.save_bulk(goods, periods, history_patterns)

    # 2. 增量计算
    split_dt = pd.to_datetime(history_split_time)
    overlap_start_dt = split_dt - datetime.timedelta(days=60)
    overlap_start_str = overlap_start_dt.strftime('%Y-%m-%d %H:%M:%S')

    print(f"⚡ 开始增量计算: {overlap_start_str} -> {current_end_time}")
    new_patterns_raw = run_strategy(goods, periods, current_end_time, overlap_start_str)

    # 3. 合并逻辑
    if not history_patterns:
        if new_patterns_raw:
            db_manager.save_bulk(goods, periods, new_patterns_raw)
        return new_patterns_raw

    last_hist_pattern = history_patterns[-1]
    last_hist_ts = pd.to_datetime(last_hist_pattern.end_timestamp)

    valid_new_patterns = []

    for p in new_patterns_raw:
        current_p_ts = pd.to_datetime(p.end_timestamp)
        if current_p_ts > last_hist_ts:
            valid_new_patterns.append(p)

    print(f"📊 合并统计: 历史 {len(history_patterns)} + 新增 {len(valid_new_patterns)}")

    if valid_new_patterns:
        db_manager.save_bulk(goods, periods, valid_new_patterns)

    # 返回全部对象
    return history_patterns + valid_new_patterns


# ====================== 测试入口 ======================
if __name__ == "__main__":
    test_goods = "FPG-XAUUSD"
    test_periods = "M5"
    HISTORY_SPLIT_POINT = "2025-01-01 00:00:00"
    CURRENT_NOW = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    final_patterns = run_strategy_incremental(
        goods=test_goods,
        periods=test_periods,
        history_split_time=HISTORY_SPLIT_POINT,
        current_end_time=CURRENT_NOW,
        history_begin_time="2000-01-01 00:00:00"
    )

    print(f"🎉 最终结果总数: {len(final_patterns)}")
    if final_patterns and final_patterns[0].target_klines:
        print(f"✅ 数据校验: 第一条形态包含 {len(final_patterns[0].target_klines)} 条K线详情")