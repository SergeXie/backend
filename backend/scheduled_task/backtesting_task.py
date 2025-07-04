import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from datetime import datetime, timedelta, time

from common.log import log
from database.db_mysql import async_db_session
from models.dql_platform import TradingFPG, DplGoodsTest
from utils.common import fetch_indicators, run_backtest, save_trader_result

CYCLES = ['M5', 'M15', 'M30', 'H1', 'H4', 'D1']

strategyUid = {"趋势止损策略": "SSWiwM6dp5FgE8"}

goods = "FPG-XAUUSD"


async def fetch_period_data(db, period):
    # 获取“昨天”的日期
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    # begin_time = datetime.combine(yesterday, time(0, 0, 0)).strftime('%Y-%m-%d %H:%M:%S')
    # end_time = datetime.combine(yesterday, time(23, 59, 0)).strftime('%Y-%m-%d %H:%M:%S')
    begin_time = "2025-07-03 00:00:00"
    end_time = "2025-07-03 23:59:00"
    # 查询策略
    strategy = await fetch_indicators(db, strategyUid["趋势止损策略"])

    # 根据品种或者品种表的手数和盈亏倍率
    dpl_goods = await db.execute(select(DplGoodsTest).where(DplGoodsTest.goods == goods))
    goods_data = dpl_goods.scalars().first()

    backtesting_param = {"period": period, "goods": goods, "startTime": begin_time,
                         "endTime": end_time, "leverage": 500}

    log.info("开始回测周期：{}".format(period))
    backtest_result = await run_backtest(db, backtesting_param, strategy, 0, goods_data, task_name="sync")

    if backtest_result:
        traderResult = backtest_result["traderResult"]
        log.info("订单数据：traderResult:{}".format(traderResult))
        # TODO 将traderResult 订单 存储到单独的订单中
        await save_trader_result(traderResult, db, strategyUid["趋势止损策略"], period)
    else:
        print("定时任务回测数据为空，周期:{}".format(period))


async def daily_task():
    print(f"定时回测任务启动: {datetime.now()}")
    async with async_db_session() as db:
        data = {}
        for period in CYCLES:
            rows = await fetch_period_data(db, period)

scheduler = AsyncIOScheduler()
scheduler.add_job(daily_task, "interval", minutes=0.1)
