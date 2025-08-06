from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func, delete
from datetime import datetime, timedelta, time

from common.log import log
from database.db_mysql import async_db_session
from models.dql_platform import TradingFPG, DplGoodsTest, DqlOrder
from utils.common import fetch_indicators, run_backtest, save_trader_result, task_run_backtest

CYCLES = ['M15', "M30", "H1", "H4"]

strategyUid = {"趋势止损策略": "SSWiwM6dp5FgE8"}
goods = ["FPG-XAUUSD", "FPG-USOUSD"]


def get_last_workday(date=None):
    """返回指定日期的上一个工作日（不含今天）"""
    if date is None:
        date = datetime.now().date()
    else:
        date = date if isinstance(date, datetime.date) else date.date()
    while True:
        date -= timedelta(days=1)
        if date.weekday() < 5:
            return date


async def get_next_begin_and_last_workday_end(db, period, _goods):
    stmt = select(func.max(DqlOrder.timestamp)).where(DqlOrder.period == period and DqlOrder.goodsId == _goods)
    result = await db.execute(stmt)
    latest_time_str = result.scalar()
    if latest_time_str:
        begin_time_dt = datetime.strptime(latest_time_str, '%Y-%m-%d %H:%M:%S')
        next_day = begin_time_dt.date() + timedelta(days=1)
        begin_time_dt = datetime.combine(next_day, time(0, 0, 0))
        if period == "H4":
            begin_time_dt = begin_time_dt - timedelta(days=4)
    else:
        # 没有数据时，自定义最早起点
        begin_time_dt = datetime(2024, 1, 1, 0, 0, 0)

    # 结束时间是当前日期的上一个工作日的 23:59:59
    last_workday = get_last_workday()
    end_time_dt = datetime.combine(last_workday, time(23, 59, 59))

    begin_time = begin_time_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_time = end_time_dt.strftime('%Y-%m-%d %H:%M:%S')
    return begin_time, end_time


def get_last_workday(date=None):
    if date is None:
        date = datetime.now().date()
    else:
        date = date if isinstance(date, datetime.date) else date.date()
    while True:
        date -= timedelta(days=1)
        if date.weekday() < 5:  # 0=Monday, 4=Friday
            return date


async def fetch_period_data(db, period, _goods, strategyUid, begin_time, end_time):
    if begin_time >= end_time:
        log.info(f"[{period}] {begin_time} >= {end_time}，无需回测。")
        return

    strategy = await fetch_indicators(db, strategyUid["趋势止损策略"])
    dpl_goods = await db.execute(select(DplGoodsTest).where(DplGoodsTest.goods == _goods))
    goods_data = dpl_goods.scalars().first()

    backtesting_param = {
        "period": period, "goods": _goods, "startTime": begin_time,
        "endTime": end_time, "leverage": 500, "initialCash": 100000, "spread": 0
    }

    log.info(f"品种:{_goods} 开始回测周期：{period} 开始时间：{begin_time}  结束时间：{end_time}")
    backtest_result = await task_run_backtest(db, backtesting_param, strategy, 0, goods_data, task_name="sync")

    if backtest_result:
        traderResult = backtest_result["traderResult"]
        log.info(f"订单数据：traderResult:{traderResult}")
        await save_trader_result(traderResult, db, strategyUid["趋势止损策略"], period)
    else:
        log.info(f"定时任务回测数据为空，周期:{period}")


async def daily_task():
    today = datetime.now().date()
    if today.weekday() >= 5:
        log.info("今天是周末，不执行定时任务")
        return
    log.info(f"定时回测任务启动: {datetime.now()}")
    end_time_dt = datetime.combine(get_last_workday(), time(23, 59, 59))
    end_time = end_time_dt.strftime('%Y-%m-%d %H:%M:%S')
    async with async_db_session() as db:
        # 清空 DqlOrder 表
        await db.execute(delete(DqlOrder))
        await db.commit()
        log.info("DqlOrder 表已清空")

        for period in CYCLES:
            for _goods in goods:
                begin_time = "2024-01-01 00:00:00"
                log.info(f"周期：{period} 开始时间：{begin_time}  结束时间：{end_time}")
                await fetch_period_data(db, period, _goods, strategyUid, begin_time, end_time)

        print("完成")

scheduler = AsyncIOScheduler()
scheduler.add_job(daily_task, "cron", hour=6, minute=15, day_of_week='mon-fri')
