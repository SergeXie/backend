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

    async def _fetch_to_df(self, db: AsyncSession, sql: str, params: dict):
        result = await db.execute(text(sql), params)
        rows = result.fetchall()
        columns = result.keys()
        return pd.DataFrame(rows, columns=columns)

    async def _load_history_patterns(self, goods: str, periods: str):
        """
        只在查询阶段占用数据库连接，查询完成立即释放。
        """
        async with self.session_factory() as db:
            history_rows = await WMPatternResultService.get_data(db, goods, periods)
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

    async def load_patterns(self, goods: str, periods: str):
        """
        只查询数据库中已落库的全部 WM 形态，不触发任何增量计算。
        主要用于预测场景直接消费历史 WM 结果。
        """
        patterns = await self._load_history_patterns(goods, periods)
        logger.info(f"已查询 WM 形态 {len(patterns)} 条 ({goods}/{periods})")
        return patterns

    @staticmethod
    def _resolve_incremental_window(
        history_patterns: list,
        history_begin_time: str,
    ) -> tuple[str, str, pd.Timestamp | None]:
        """
        计算增量区间的起点与清理起点。

        规则：
        1. 有历史形态时，增量计算起点统一使用“倒数第二条形态的起始时间”；
           如果历史不足两条，则退化为最后一条形态结束后的下一秒。
        2. 无历史形态时，直接使用历史起始时间作为增量计算起点与清理起点。
        3. 返回最后一条历史形态的结束时间，用于过滤纯增量结果。
        """
        if not history_patterns:
            return history_begin_time, history_begin_time, None

        last_hist_ts = pd.to_datetime(history_patterns[-1].end_timestamp)

        if len(history_patterns) >= 2:
            second_last_pattern = history_patterns[-2]
            incremental_begin_time = pd.to_datetime(second_last_pattern.start_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        else:
            incremental_begin_time = (last_hist_ts + datetime.timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")

        return incremental_begin_time, incremental_begin_time, last_hist_ts

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
            # logger.info("K线数据已加载到内存，数据库连接已释放")
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
        current_end_time: str,
        history_begin_time: str = "2000-01-01 00:00:00",
    ):
        """
        WM 形态更新流程：
        1. 没有历史数据时，先做一次全量历史计算并入库。
        2. 有历史数据时，从倒数第二条形态的起始时间开始重新计算增量区间。
        3. 计算过程只在查询阶段占用数据库连接，保存结果时再重新开连接。
        """
        history_patterns = await self._load_history_patterns(goods, periods)

        if not history_patterns:
            logger.warning(f"未检测到缓存，正在全量计算历史数据 ({history_begin_time} -> {current_end_time})")
            history_patterns = await self._run_strategy(goods, periods, current_end_time, history_begin_time)

            if history_patterns:
                await self._save_history_patterns(goods, periods, history_patterns)

        incremental_begin_time, cleanup_start_time, last_hist_ts = self._resolve_incremental_window(
            history_patterns,
            history_begin_time,
        )

        logger.info(f"开始增量计算区间: {incremental_begin_time} -> {current_end_time}")

        new_patterns_raw = await self._run_strategy(goods, periods, current_end_time, incremental_begin_time)

        if not history_patterns:
            if new_patterns_raw:
                await self._save_patterns(
                    goods,
                    periods,
                    new_patterns_raw,
                    cleanup_start_time=cleanup_start_time,
                    cleanup_end_time=current_end_time,
                )
            return new_patterns_raw

        # 仅保留历史最后一条形态之后真正新增的结果，避免重复入库。
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
    current_end_time: str,
    history_begin_time: str = "2000-01-01 00:00:00",
):
    engine, session_factory = _build_session_factory()
    try:
        extractor = WMExtractor(session_factory)
        return await extractor.run_strategy_incremental(
            goods=goods,
            periods=periods,
            current_end_time=current_end_time,
            history_begin_time=history_begin_time,
        )
    finally:
        await engine.dispose()


async def load_patterns_async(
    goods: str,
    periods: str,
):
    engine, session_factory = _build_session_factory()
    try:
        extractor = WMExtractor(session_factory)
        return await extractor.load_patterns(
            goods=goods,
            periods=periods,
        )
    finally:
        await engine.dispose()


def _run_sync_coroutine(coro_factory):
    """
    兼容“当前线程无事件循环”和“当前线程已有事件循环”两种场景。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    result_holder = {}
    error_holder = {}

    def _thread_target():
        try:
            result_holder["value"] = asyncio.run(coro_factory())
        except Exception as exc:
            error_holder["error"] = exc

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_holder:
        raise error_holder["error"]

    return result_holder.get("value")


def run_strategy_incremental_sync(
    goods: str,
    periods: str,
    current_end_time: str,
    history_begin_time: str = "2000-01-01 00:00:00",
):
    async def _runner():
        return await run_strategy_incremental_async(
            goods=goods,
            periods=periods,
            current_end_time=current_end_time,
            history_begin_time=history_begin_time,
        )

    return _run_sync_coroutine(_runner) or []


def load_patterns_sync(
    goods: str,
    periods: str,
):
    async def _runner():
        return await load_patterns_async(
            goods=goods,
            periods=periods,
        )

    return _run_sync_coroutine(_runner) or []


async def async_main():
    test_goods = "FPG-XAUUSD"
    test_periods = "M5"
    current_end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    engine, session_factory = _build_session_factory()
    try:
        extractor = WMExtractor(session_factory)

        data = await extractor.load_backtest_kline_df(
            test_goods,
            test_periods,
            current_end_time,
            "2024-01-01 00:00:00",
        )
        logger.info(f"测试数据加载结果: {'成功' if data else '失败'}")

        final_patterns = await extractor.run_strategy_incremental(
            goods=test_goods,
            periods=test_periods,
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
