import asyncio
import datetime
import threading

import backtrader as bt
import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.bt.indicators.wm_data_extractor import WMExtractorStrategy
from services.wm_pattern_result_service import WMPatternResultService


class PandasDataPlus(bt.feeds.PandasData):
    lines = ("pkId", "klineId")
    params = (
        ("pkId", -1),
        ("open", -1),
        ("high", -1),
        ("low", -1),
        ("close", -1),
        ("volume", -1),
        ("openinterest", None),
        ("klineId", -1),
    )


class WMExtractor:
    """
    用于计算过往和增量WM形态并入库
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def _get_common_dependencies():
        from common.common import model_classes, select_goods_common
        return select_goods_common, model_classes

    @staticmethod
    def _calc_overlap_start_time(history_split_time: str, periods: str, bar_count: int = 1000) -> str:
        """
        按周期向前回溯约 bar_count 根K线。
        支持:
        - M1 / M5 / M15 / M30
        - H1 / H4
        - D1
        - W1
        - MN1
        """
        split_dt = pd.to_datetime(history_split_time)
        period = periods.upper().strip()

        try:
            if period.startswith("MN"):
                step = int(period[2:])
                overlap_start_dt = split_dt - pd.DateOffset(months=step * bar_count)
            elif period.startswith("M"):
                step = int(period[1:])
                overlap_start_dt = split_dt - datetime.timedelta(minutes=step * bar_count)
            elif period.startswith("H"):
                step = int(period[1:])
                overlap_start_dt = split_dt - datetime.timedelta(hours=step * bar_count)
            elif period.startswith("D"):
                step = int(period[1:])
                overlap_start_dt = split_dt - datetime.timedelta(days=step * bar_count)
            elif period.startswith("W"):
                step = int(period[1:])
                overlap_start_dt = split_dt - datetime.timedelta(weeks=step * bar_count)
            else:
                logger.warning(f"无法识别周期 {periods}，回退为 60 天重叠区间")
                overlap_start_dt = split_dt - datetime.timedelta(days=60)

            return overlap_start_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            logger.exception(f"周期解析失败: periods={periods}，回退为 60 天重叠区间")
            return (split_dt - datetime.timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")

    async def _fetch_to_df(self, db: AsyncSession, sql: str, params: dict):
        result = await db.execute(text(sql), params)
        rows = result.fetchall()
        columns = result.keys()
        return pd.DataFrame(rows, columns=columns)

    async def _load_history_patterns(self, goods: str, periods: str, history_split_time: str):
        """
        只在查询阶段占用数据库连接，查询完成立即释放。
        """
        async with self.session_factory() as db:
            history_rows = await WMPatternResultService.get_data(db, goods, periods, history_split_time)
            history_patterns = [
                pattern for row in history_rows
                if (pattern := WMPatternResultService._deserialize_pattern(row)) is not None
            ]
        return history_patterns

    async def _save_patterns(
        self,
        goods: str,
        periods: str,
        patterns: list,
        cleanup_start_time: str | None = None,
        cleanup_end_time: str | None = None,
    ):
        """
        计算完成后重新开连接保存结果。
        """
        if not patterns:
            return 0

        async with self.session_factory() as db:
            try:
                if cleanup_start_time and cleanup_end_time:
                    await WMPatternResultService.clean_range(
                        db,
                        goods,
                        periods,
                        cleanup_start_time,
                        cleanup_end_time,
                    )

                saved_count = await WMPatternResultService.save_bulks(db, goods, periods, patterns)
                await db.commit()
                logger.info(f"形态结果保存完成，共 {saved_count} 条 ({goods}/{periods})")
                return saved_count
            except Exception:
                await db.rollback()
                logger.exception(f"形态结果保存失败 ({goods}/{periods})")
                raise

    async def _save_history_patterns(self, goods: str, periods: str, patterns: list):
        return await self._save_patterns(goods, periods, patterns)

    async def load_backtest_kline_df(self, goods, periods, endTime, beginTime):
        """
        快速加载K线数据
        查询完成后立即释放数据库连接
        """
        try:
            async with self.session_factory() as db:
                select_goods_common, model_classes = self._get_common_dependencies()
                select_model_class, goods_row = await select_goods_common(db, goods, model_classes)
                if not select_model_class:
                    logger.error(f"查询品种失败: {goods}")
                    return None

                good_table = select_model_class.__tablename__
                trading_goods = goods_row.trading_goods

                logger.info(f"[{trading_goods}] 数据加载请求: {beginTime} -> {endTime}")

                sql = f"""
                    SELECT
                        tradeDateTime as datetime,
                        opening as open,
                        high,
                        low,
                        closed as close,
                        vol as volume,
                        pkId,
                        pkId as klineId,
                        digits,
                        spread
                    FROM {good_table}
                    WHERE type = :period
                      AND tradingGoods = :goods
                      AND tradeDateTime >= :begin
                      AND tradeDateTime <= :end
                    ORDER BY tradeDateTime ASC
                """
                params = {
                    "period": periods,
                    "goods": trading_goods,
                    "begin": beginTime,
                    "end": endTime,
                }

                df = await self._fetch_to_df(db, sql, params)

            # 这里开始数据库连接已经释放
            if df.empty:
                logger.error(f"该区间未查询到数据 ({beginTime} - {endTime})")
                return None

            float_cols = ["open", "high", "low", "close", "volume"]
            df[float_cols] = df[float_cols].astype("float")
            df["klineId"] = df["klineId"].astype(int)
            df["pkId"] = df["pkId"].astype(int)
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)

            data = PandasDataPlus(dataname=df)
            logger.info("K线数据已加载到内存，数据库连接已释放")
            return data

        except Exception as e:
            logger.exception(f"数据加载出错: {e}")
            return None

    async def _run_strategy(self, goods, periods, endTime, beginTime):
        """
        数据先查出到内存，再进行计算，不占用数据库连接。
        """
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
        history_split_time: str,  # "2026-01-01 00:00:00"
        current_end_time: str,
        history_begin_time: str = "2000-01-01 00:00:00",
    ):
        """
        增量运行策略：
        1. 读取历史缓存后立即释放连接
        2. 若无缓存，则读取历史K线后立即释放连接，再执行计算
        3. 读取增量区间K线后立即释放连接，再执行计算
        4. 计算完成后重新连接数据库保存结果
        """
        history_patterns = await self._load_history_patterns(goods, periods, history_split_time)

        if not history_patterns:
            logger.warning(f"未检测到缓存，正在全量计算历史数据 ({history_begin_time} -> {history_split_time})")
            history_patterns = await self._run_strategy(goods, periods, history_split_time, history_begin_time)

            if history_patterns:
                await self._save_history_patterns(goods, periods, history_patterns)

        overlap_start_str = self._calc_overlap_start_time(history_split_time, periods, bar_count=1000)

        logger.info(f"开始增量计算区间: {overlap_start_str} -> {current_end_time}")

        new_patterns_raw = await self._run_strategy(goods, periods, current_end_time, overlap_start_str)

        if not history_patterns:
            if new_patterns_raw:
                await self._save_patterns(
                    goods,
                    periods,
                    new_patterns_raw,
                    cleanup_start_time=history_begin_time,
                    cleanup_end_time=current_end_time,
                )
            return new_patterns_raw

        last_hist_pattern = history_patterns[-1]
        last_hist_ts = pd.to_datetime(last_hist_pattern.end_timestamp)
        cleanup_start_time = (last_hist_ts + datetime.timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")

        valid_new_patterns = [
            p for p in new_patterns_raw
            if pd.to_datetime(p.end_timestamp) > last_hist_ts
        ]

        logger.info(
            f"数据合并完成 | 历史基准: {len(history_patterns)} | 纯增量: {len(valid_new_patterns)}"
        )

        if valid_new_patterns:
            await self._save_patterns(
                goods,
                periods,
                valid_new_patterns,
                cleanup_start_time=cleanup_start_time,
                cleanup_end_time=current_end_time,
            )

        return history_patterns + valid_new_patterns


# 这里替换成你项目真实的数据库连接串
DATABASE_URL = "mysql+aiomysql://cmdb:cmdb123456@192.168.1.126:3306/dql?charset=utf8mb4"


def _build_session_factory():
    """
    每次任务在当前事件循环内创建独立 engine / session_factory,
    避免全局连接池跨事件循环、跨线程复用。
    """
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


async def run_strategy_incremental_async(
    goods: str,
    periods: str,
    history_split_time: str,  # "2026-01-01 00:00:00"
    current_end_time: str,
    history_begin_time: str = "2000-01-01 00:00:00",
):
    engine, session_factory = _build_session_factory()
    try:
        extractor = WMExtractor(session_factory)
        return await extractor.run_strategy_incremental(
            goods=goods,
            periods=periods,
            history_split_time=history_split_time,
            current_end_time=current_end_time,
            history_begin_time=history_begin_time,
        )
    finally:
        await engine.dispose()


def run_strategy_incremental_sync(
    goods: str,
    periods: str,
    history_split_time: str,  # "2026-01-01 00:00:00"
    current_end_time: str,
    history_begin_time: str = "2000-01-01 00:00:00",
):
    async def _runner():
        return await run_strategy_incremental_async(
            goods=goods,
            periods=periods,
            history_split_time=history_split_time,
            current_end_time=current_end_time,
            history_begin_time=history_begin_time,
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_runner())

    result_holder = {}
    error_holder = {}

    def _thread_target():
        try:
            result_holder["value"] = asyncio.run(_runner())
        except Exception as exc:
            error_holder["error"] = exc

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_holder:
        raise error_holder["error"]

    return result_holder.get("value", [])


async def async_main():
    test_goods = "FPG-XAUUSD"
    test_periods = "M5"
    history_split_point = "2025-01-01 00:00:00"
    current_end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    engine, session_factory = _build_session_factory()
    try:
        extractor = WMExtractor(session_factory)

        data = await extractor.load_backtest_kline_df(
            test_goods,
            test_periods,
            history_split_point,
            "2024-01-01 00:00:00",
        )
        logger.info(f"测试数据加载结果: {'成功' if data else '失败'}")

        final_patterns = await extractor.run_strategy_incremental(
            goods=test_goods,
            periods=test_periods,
            history_split_time=history_split_point,
            current_end_time=current_end_time,
            history_begin_time="2024-01-01 00:00:00",
        )

        print(f"🎉 最终结果总数: {len(final_patterns)}")
        if final_patterns and getattr(final_patterns[0], "target_klines", None):
            print(f"✅ 数据校验: 第一条形态包含 {len(final_patterns[0].target_klines)} 条K线详情")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(async_main())
