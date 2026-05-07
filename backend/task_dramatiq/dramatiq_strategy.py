import asyncio
import json
import traceback
import dramatiq
import pandas as pd
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.middleware import AsyncIO
from sqlalchemy import select, update
from common.log import log
from database.db_mysql import async_db_session
from schemas.base import DqlStrategy, DqlStrategyTestResult, DqlGoods
from common.common import fetch_trading_data, model_classes, PandasData
from core.bt.base.public_strategy import ComprehensiveAnalyzer
from core.bt.strategys import reload_strategies
import backtrader as bt

# 配置 RabbitMQ broker
rabbitmq_broker = RabbitmqBroker(url="amqp://guest:guest@localhost:5672/")
#rabbitmq_broker = RabbitmqBroker(url="amqp://admin:admin123@192.168.0.73:5672/")
dramatiq.set_broker(rabbitmq_broker)
rabbitmq_broker.add_middleware(AsyncIO())

strategy_classes = {}
strategy_classes = reload_strategies()


# 定义一个简单的任务
@dramatiq.actor
async def print_message(message):
    print(f"Received message: {message}")


@dramatiq.actor
async def task_run_backtest(strategy_data_requests, tester_uid, task_name=None):
    try:
        async with async_db_session() as db:

            # 根据品种或者品种表的手数和盈亏倍率
            dp_goods_data = await db.execute(select(DqlGoods).where(
                DqlGoods.goods == strategy_data_requests.get("goods")))

            goods_data = dp_goods_data.scalars().first()

            # 根据period参数的取值进行条件判断
            period_dict = {"period": strategy_data_requests.get("period", None),
                           "tradingGoods": strategy_data_requests.get("goods", None),
                           "beginTime": strategy_data_requests.get("startTime", None),
                           "endTime": strategy_data_requests.get("endTime", None)}

            period_tuple = tuple(period_dict.items())

            select_indicators = await db.execute(select(DqlStrategy).where(
                DqlStrategy.uid == strategy_data_requests.get("uid", 0)))
            strategys = select_indicators.scalars().first()

        indicator_params = strategy_data_requests.get("parameter", {})
        trading_data = await fetch_trading_data(db, strategy_data_requests.get("goods", None),
                                                strategy_data_requests.get("period", None),
                                                model_classes,
                                                begin_time=strategy_data_requests.get("startTime", None),
                                                end_time=strategy_data_requests.get("endTime", None),
                                                period_tuple=period_tuple, class_name=json.loads(strategys.className))

        if not trading_data:
            return

        # 创建backtrader大脑实例
        cerebro = bt.Cerebro()
        # 数据源处理
        df = pd.DataFrame(trading_data)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        data = PandasData(dataname=df)
        # 添加数据源
        cerebro.adddata(data)
        # 加载策略
        # strategys.className 存储的是列表类型
        indicator_params['Kline_period'] = strategy_data_requests.get("period", None)
        indicator_params['Kline_goods'] = strategy_data_requests.get("goods", None)
        for class_name in json.loads(strategys.className):
            cerebro.addstrategy(strategy_classes.get(class_name), indicator_params,
                                goodsId=strategy_data_requests.get("goods", None),
                                begin_time=strategy_data_requests.get("startTime", None),
                                baseLots=goods_data.baseLots)

        # 综合分析器
        cerebro.addanalyzer(ComprehensiveAnalyzer, _name='comprehensive')
        # 添加最大回撤分析器
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

        # 设置初始资金
        cerebro.broker.set_cash(float(strategy_data_requests.get("initialCash", 100000)))

        # mult 合约单位100  leverage 杠杆
        cerebro.broker.setcommission(
            commission=strategy_data_requests.get("commission", 0),
            mult=100, leverage=strategy_data_requests.get("leverage", 1))

        if strategy_data_requests.get("spread", 0):
            # 设置滑点/点差
            cerebro.broker.set_slippage_fixed(fixed=strategy_data_requests.get("spread", 0) / 100)

        result = cerebro.run(stdstats=True, tradehistory=True)
        # 获取最大回撤信息
        drawdown = result[0].analyzers.drawdown.get_analysis()
        trader_return = result[0].get_analysis()

        traderResult = trader_return.get('trader_result')
        traderReport = trader_return.get('trader_report')
        floatingPointValues = trader_return.get('floating_point_values')
        netAssetValues = trader_return.get('net_asset_values')
        newReportTemplate = result[0].analyzers.comprehensive.get_analysis()

        traderReport["maxFUR"] = float(format(drawdown.max.drawdown, f".{int(2)}f"))
        traderReport["mdr"] = float(format(drawdown.max.drawdown, f".{int(2)}f"))
        # 对交易订单 traderResult还在持仓的，进行盈利结算
        # traderResult_ = await adjust_unpaired_trades(db, strategy_data_requests.get("endTime"), traderResult)

        # 事务2：更新策略测试结果，带重试机制
        for attempt in range(3):
            try:
                async with async_db_session() as db:
                    await db.execute(
                        update(DqlStrategyTestResult).where(DqlStrategyTestResult.uid == tester_uid).values(
                            traderResult=json.dumps({
                                "traderResult": traderResult,
                                "traderReport": traderReport,
                                "floatingPointValues": floatingPointValues,
                                "netAssetValues": netAssetValues
                            }),
                            yieldRate=traderReport.get("yieldRate", 0),
                            isBursted=traderReport.get("isBursted", 0),
                            mdr=traderReport.get("mdr", 0),
                            winRate=traderReport.get("winRate", 0),
                            pnl=traderReport.get("totalNetProfit", 0),
                            plr=traderReport.get("plr", 0),
                            tradeCount=traderReport.get("totalTrades", 0),
                            maxProfit=traderReport.get("largestProfit", 0),
                            maxLoss=traderReport.get("largestLoss", 0),
                            avgProfit=traderReport.get("avgProfit", 0),
                            maxFUR=traderReport.get("maxFUR", 0),
                            score=traderReport.get("totalTrades", 0),
                            paramsStrName=traderReport.get("paramsStrName", None),
                            newReportTemplate=json.dumps(newReportTemplate),
                            calculationStatus=1
                        )
                    )
                    await db.commit()
                    log.info(f"更新DqlStrategyTestResult成功：{tester_uid}")
                break  # 成功后退出重试循环
            except Exception as e:
                if "Lock wait timeout" in str(e):
                    log.info("Lock wait timeout, retrying... attempt {}".format(attempt + 1))
                    await asyncio.sleep(2 ** attempt)  # 指数退避重试
                else:
                    log.info("更新DqlStrategyTestResult失败: {}".format(e))
                    await db.rollback()  # 回滚事务
                    break  # 不重试其他异常

            log.info("策略结果所有入库完毕！")
    except Exception as e:
        info = traceback.format_exc()
        log.info("策略结果插入数据库失败：{}".format(info))
        log.info("请求参数信息：{}".format(strategy_data_requests))
        await db.rollback()  # 如果发生异常，回滚事务
        return None

if __name__ == "__main__":
    # 发送任务
    print_message.send("Hello, Dramatiq with RabbitMQ!")
