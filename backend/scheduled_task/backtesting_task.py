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


async def get_next_trade_date(db):
    # 查询最大timestamp
    stmt = select(func.max(DqlOrder.timestamp))
    result = await db.execute(stmt)
    latest_time_str = result.scalar()
    if latest_time_str:
        # 假设timestamp字段是字符串
        latest_time = datetime.strptime(latest_time_str, '%Y-%m-%d %H:%M:%S')
        target_day = latest_time.date() + timedelta(days=1)
    else:
        # 没有订单数据，默认用昨天
        target_day = datetime.now().date() - timedelta(days=1)

    begin_time = datetime.combine(target_day, time(0, 0, 0)).strftime('%Y-%m-%d %H:%M:%S')
    end_time = datetime.combine(target_day, time(23, 59, 0)).strftime('%Y-%m-%d %H:%M:%S')
    return begin_time, end_time


async def fetch_period_data(db, period, goods, strategyUid, begin_time, end_time):
    strategy = await fetch_indicators(db, strategyUid["趋势止损策略"])
    dpl_goods = await db.execute(select(DplGoodsTest).where(DplGoodsTest.goods == goods))
    goods_data = dpl_goods.scalars().first()

    backtesting_param = {
        "period": period, "goods": goods, "startTime": begin_time,
        "endTime": end_time, "leverage": 500
    }

    log.info(f"开始回测周期：{period} 开始时间：{begin_time}  结束时间：{end_time}")
    backtest_result = await run_backtest(db, backtesting_param, strategy, 0, goods_data, task_name="sync")

    if backtest_result:
        traderResult = backtest_result["traderResult"]
        log.info(f"订单数据：traderResult:{traderResult}")
        await save_trader_result(traderResult, db, strategyUid["趋势止损策略"], period)
    else:
        print(f"定时任务回测数据为空，周期:{period}")


async def daily_task():
    today = datetime.now().date()
    if today.weekday() >= 5:  # 5=Saturday, 6=Sunday
        print("今天是周末，不执行定时任务")
        return
    print(f"定时回测任务启动: {datetime.now()}")
    async with async_db_session() as db:
        # 1. 先查最大timestamp，得到需要回测的日期区间
        begin_time, end_time = await get_next_trade_date(db)
        # 2. 回测并保存订单，插入不会影响本轮begin_time/end_time
        for period in CYCLES:
            await fetch_period_data(db, period, goods, strategyUid, begin_time, end_time)

scheduler = AsyncIOScheduler()
scheduler.add_job(daily_task, "cron", hour=0, minute=0, day_of_week='mon-fri')
