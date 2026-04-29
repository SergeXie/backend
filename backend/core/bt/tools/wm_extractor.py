import asyncio
import datetime
import backtrader as bt
import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from common.common import select_goods_common
from core.bt.indicators.wm_data_extractor import WMExtractorStrategy
from services.wm_pattern_result_service import WMPatternResultService


class PandasDataPlus(bt.feeds.PandasData):
    """
    自定义数据馈送类：允许 Backtrader 读取非标准字段 klineId 和 pkId
    """
    lines = ('pkId', 'klineId',)
    params = (
        ('pkId', -1),    # -1 表示自动匹配 DataFrame 中名为 'pkId' 的列
        ('klineId', -1), # 匹配名为 'klineId' 的列
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', None),
    )

class WMExtractor:
    """
    用于计算过往和增量WM形态并入库
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        pass

    async def _fetch_to_df(self, sql: str, params: dict):
        # 异步查询
        result = await self.db.execute(text(sql), params)

        # 获取原始数据和列名
        rows = result.fetchall()
        columns = result.keys()

        # 转换为 DataFrame
        df = pd.DataFrame(rows, columns=columns)
        return df

    async def load_backtest_kline_df(self, goods, periods, endTime, beginTime):
        """
        快速加载k线数据
        """
        try:
            good_table, tradingGoods = select_goods_common(goods)
        except Exception as e:
            logger.error(f"查询品种失败: {e}")
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
            # df = pd.read_sql(sql, engine, params=params)
            df = await WMExtractor._fetch_to_df(self.db, sql, params)
            if df.empty:
                logger.error(f"该区间未查询到数据 ({beginTime} - {endTime})")
                return None

            float_cols = ['open', 'high', 'low', 'close', 'volume']
            df[float_cols] = df[float_cols].astype('float')

            # 转换 ID 列为整型
            df['klineId'] = df['klineId'].astype(int)
            df['pkId'] = df['pkId'].astype(int)

            # 转换时间并设为索引
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)

            # 5. 实例化自定义的 PandasDataPlus
            # 这步是关键！它能把 pkId 和 klineId 注入到策略的 self.data 中
            data = PandasDataPlus(dataname=df)

            return data

        except Exception as e:
            logger.error(f"数据加载出错: {e}")
            return None

    async def _run_strategy(self, goods, periods, endTime, beginTime):
        cerebro = bt.Cerebro()
        data = await self.load_backtest_kline_df(goods, periods, endTime, beginTime)
        if data is None:
            return []

        cerebro.adddata(data)
        cerebro.addstrategy(WMExtractorStrategy)
        result = cerebro.run(stdstats=False, runonce=True)
        return result[0].get_analysis()

    async def run_strategy_incremental(
            self,
            goods: str,
            periods: str,
            history_split_time: str,
            current_end_time: str,
            history_begin_time: str = "2000-01-01 00:00:00"
    ):
        """
        增量运行策略：
        1. 从数据库读取已缓存的历史形态。
        2. 如果无缓存，全量计算历史并持久化。
        3. 增量计算重叠区间，确保形态连续性。
        """

        # 1. 尝试从数据库加载历史 (注意：如果 load_history 是异步的，请加 await)
        # 这里假设 load_history 已经适配了异步或使用的是内部连接池
        history_patterns = await WMPatternResultService.get_data(self.db, goods, periods, history_split_time)

        if not history_patterns:
            logger.warning(f"未检测到缓存，正在全量计算历史数据 ({history_begin_time} -> {history_split_time})")
            # 建议：这里的 run_strategy 内部应该调用我们优化后的 get_kline_data_optimized
            history_patterns = await self._run_strategy(goods, periods, history_split_time, history_begin_time)

            if history_patterns:
                # 只有初次全量计算的结果才存入数据库，作为后续的“基准历史”
                await WMPatternResultService.save_bulks(self.db, goods, periods, history_patterns)

        # 2. 准备增量计算范围
        # 为了防止形态在分割点被截断，向前回溯（如60天），确保 ZigZag 逻辑能正确“接上”
        split_dt = pd.to_datetime(history_split_time)
        overlap_start_str = (split_dt - datetime.timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')

        logger.info(f"开始增量计算区间: {overlap_start_str} -> {current_end_time}")

        # 获取包含重叠区间的最新形态
        new_patterns_raw = await self._run_strategy(goods, periods, current_end_time, overlap_start_str)

        # 3. 精确去重与合并
        if not history_patterns:
            return new_patterns_raw

        # 获取历史记录中最后一条形态的时间戳和类型，作为去重参照
        last_hist_pattern = history_patterns[-1]
        # 使用结束时间作为基准，也可以增加 pattern_type 联合校验更稳妥
        last_hist_ts = pd.to_datetime(last_hist_pattern.end_timestamp)

        # 过滤掉所有在历史记录中已经存在的形态
        # 优化点：使用列表推导式，提高性能
        valid_new_patterns = [
            p for p in new_patterns_raw
            if pd.to_datetime(p.end_timestamp) > last_hist_ts
        ]

        logger.info(f"数据合并完成 | 历史基准: {len(history_patterns)} | 纯增量: {len(valid_new_patterns)}")

        # 4. 根据需求决定是否将这部分“新鲜”增量也持久化
        # 如果 history_split_time 会随着每次运行更新，则开启此项
        # if valid_new_patterns:
        #     db_manager.save_bulk(goods, periods, valid_new_patterns)

        return history_patterns + valid_new_patterns

async def async_main():
    async with AsyncSession() as db:
        test_goods = "FPG-XAUUSD"
        test_periods = "M5"
        HISTORY_SPLIT_POINT = "2025-01-01 00:00:00"
        dt = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        extractor = WMExtractor(db)
        df = await extractor.load_backtest_kline_df(test_goods, test_periods, HISTORY_SPLIT_POINT)
        final_patterns = extractor.run_strategy_incremental(
            goods=test_goods,
            periods=test_periods,
            history_split_time=HISTORY_SPLIT_POINT,
            current_end_time=dt,
            history_begin_time="2000-01-01 00:00:00"
        )

        print(f"🎉 最终结果总数: {len(final_patterns)}")
        if final_patterns and final_patterns[0].target_klines:
            print(f"✅ 数据校验: 第一条形态包含 {len(final_patterns[0].target_klines)} 条K线详情")

if __name__ == "__main__":
    asyncio.run(async_main())
