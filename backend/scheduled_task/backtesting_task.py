import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func
from datetime import datetime, timedelta, time

from common.log import log
from database.db_mysql import async_db_session
from models.dql_platform import TradingFPG, DplGoodsTest, DqlOrder
from utils.common import fetch_indicators, run_backtest, save_trader_result

CYCLES = ['M15', 'M30', 'H1', 'H4']

strategyUid = {"趋势止损策略": "SSWiwM6dp5FgE8"}

goods = "FPG-XAUUSD"

def get_next_workday(date):
    # date: datetime.date
    while True:
        date += timedelta(days=1)
        if date.weekday() < 5:  # 0-4 是工作日
            return date


# 增加一个参数 period
async def get_next_trade_time_range(db, period):
    stmt = select(func.max(DqlOrder.timestamp)).where(DqlOrder.period == period)
    result = await db.execute(stmt)
    latest_time_str = result.scalar()
    if latest_time_str:
        begin_time_dt = datetime.strptime(latest_time_str, '%Y-%m-%d %H:%M:%S')
    else:
        # 没有数据，从上一个工作日0点开始
        begin_time_dt = datetime.combine(get_next_workday(datetime.now().date() - timedelta(days=1)), time(0, 0, 0))

    # end_time 默认是 begin_time + 1天
    end_day = begin_time_dt.date() + timedelta(days=1)
    # 如果+1天是周末，则找下一个工作日
    while end_day.weekday() >= 5:
        end_day = get_next_workday(end_day)
    # end_time设为这个工作日的 23:59:59
    end_time_dt = datetime.combine(end_day, time(23, 59, 59))

    begin_time = begin_time_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_time = end_time_dt.strftime('%Y-%m-%d %H:%M:%S')
    return begin_time, end_time

async def fetch_period_data(db, period, goods, strategyUid, begin_time, end_time):
    strategy = await fetch_indicators(db, strategyUid["趋势止损策略"])
    dpl_goods = await db.execute(select(DplGoodsTest).where(DplGoodsTest.goods == goods))
    goods_data = dpl_goods.scalars().first()

    backtesting_param = {
        "period": period, "goods": goods, "startTime": begin_time,
        "endTime": end_time, "leverage": 500, "initialCash": 100000, "spread": 0
    }

    log.info(f"开始回测周期：{period} 开始时间：{begin_time}  结束时间：{end_time}")
    backtest_result = await run_backtest(db, backtesting_param, strategy, 0, goods_data, task_name="sync")

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
    async with async_db_session() as db:
        for period in CYCLES:
            begin_time, end_time = await get_next_trade_time_range(db, period)
            await fetch_period_data(db, period, goods, strategyUid, begin_time, end_time)


scheduler = AsyncIOScheduler()
scheduler.add_job(daily_task, "cron", hour=0, minute=0, day_of_week='mon-fri')
# scheduler.add_job(daily_task, "interval", minutes=1)  # 真实业务用1，测试时可用10~30秒
