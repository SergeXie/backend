import asyncio
from datetime import datetime, time, timedelta

from common.log import log
from core.bt.tools.wm_extractor import run_strategy_incremental_sync

TARGET_GOODS = "FPG-XAUUSD"
TARGET_PERIODS = ["M5", "M15", "M30", "H1", "H4"]
DEFAULT_HISTORY_BEGIN_TIME = "2000-01-01 00:00:00"


def get_last_friday(date_value=None):
    target_date = date_value or datetime.now().date()
    days_since_friday = (target_date.weekday() - 4) % 7
    if days_since_friday == 0:
        days_since_friday = 7
    return target_date - timedelta(days=days_since_friday)


def get_last_friday_end_time() -> str:
    last_friday = get_last_friday()
    return datetime.combine(last_friday, time(23, 59, 59)).strftime("%Y-%m-%d %H:%M:%S")


async def weekly_wm_incremental_task():
    today = datetime.now().date()
    if today.weekday() != 5:
        log.info("今天不是周六，跳过 WM 周度增量任务")
        return

    current_end_time = get_last_friday_end_time()
    log.info(f"WM 周度增量任务启动: {datetime.now()}，截止时间: {current_end_time}")

    for period in TARGET_PERIODS:
        try:
            log.info(
                f"开始执行 WM 增量更新 | 品种: {TARGET_GOODS} | 周期: {period} | "
                f"截止时间: {current_end_time}"
            )
            patterns = await asyncio.to_thread(
                run_strategy_incremental_sync,
                goods=TARGET_GOODS,
                periods=period,
                current_end_time=current_end_time,
                history_begin_time=DEFAULT_HISTORY_BEGIN_TIME,
            )
            log.info(
                f"WM 增量更新完成 | 品种: {TARGET_GOODS} | 周期: {period} | 结果总数: {len(patterns)}"
            )
        except Exception:
            log.exception(f"WM 增量更新失败 | 品种: {TARGET_GOODS} | 周期: {period}")

    log.info("WM 周度增量任务执行结束")


async def minute_h1_task():
    """每分钟触发一次，仅对 H1 周期执行增量更新。"""
    period = "H1"
    current_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        log.info(
            f"每分钟 H1 任务启动 | 品种: {TARGET_GOODS} | 周期: {period} | "
            f"截止时间: {current_end_time}"
        )

        patterns = await asyncio.to_thread(
            run_strategy_incremental_sync,
            goods=TARGET_GOODS,
            periods=period,
            current_end_time=current_end_time,
            history_begin_time=DEFAULT_HISTORY_BEGIN_TIME,
        )

        log.info(f"每分钟 H1 任务完成 | 品种: {TARGET_GOODS} | 周期: {period} | 结果: {len(patterns)}")
    except Exception:
        log.exception(f"每分钟 H1 任务失败 | 品种: {TARGET_GOODS} | 周期: {period}")
