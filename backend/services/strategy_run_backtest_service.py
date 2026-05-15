import asyncio
import json
import traceback
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from common.log import log
from schemas.base import DqlGoods, DqlStrategyTestResult
from common.common import fetch_indicators, run_backtest, adjust_unpaired_trades, fetch_trading_data, model_classes, \
    generate_random_string


async def create_strategy_record(db: AsyncSession, indicator_data_request, strategys):
    """
    :param db: 数据库会话
    :param indicator_data_request: 请求参数
    :param strategys:  策略对象
    :return:
    """
    try:
        # 创建策略结果记录
        add_strategy_record = DqlStrategyTestResult(
            uid=generate_random_string("TR"),
            title=strategys.name,
            notes=strategys.description,
            strategyUid=indicator_data_request.get("uid", 0),
            goodsId=indicator_data_request["goods"],
            period=indicator_data_request["period"],
            startTime=indicator_data_request["startTime"],
            endTime=indicator_data_request["endTime"],
            traderResult="{}",
            parameter=json.dumps(indicator_data_request.get("parameter", {})),
            isBursted=0, status=0, yieldRate=0,
            mdr=0, winRate=0, plr=0, tradeCount=0,
            pnl=0,maxProfit=0, maxLoss=0, avgProfit=0, maxFUR=0, score=0,
            is_delete=0, spread=indicator_data_request.get("spread", 0),
            leverage=indicator_data_request.get("leverage", 1),
            paramsStrName=indicator_data_request.get("paramsStrName", None),
            newReportTemplate=json.dumps(indicator_data_request.get("newReportTemplate", {}))
        )
        db.add(add_strategy_record)
        await db.commit()
        return add_strategy_record.uid

    except Exception as e:
        info = traceback.format_exc()
        log.error("策略存储插入数据库失败：{}".format(info))
        await db.rollback()  # 如果发生异常，回滚事务
        await db.close()
        return None


class StrategyRunBacktestService:

    async def batch_run_backtest(self, db, payload_list):
        result_data = []

        for item in payload_list:
            print("item:{}".format(item))
            # 1. 查策略
            strategy = await fetch_indicators(db, item["uid"])
            if not strategy:
                continue

            # 2. 查品种信息表
            goods_data = await self._get_goods(db, item["goods"])

            # 3. K线数据
            trading_data = await self._get_kline(db, item, strategy)

            # 4. 组装参数
            params = self._build_params(item)

            # 5. 在线程池里执行同步 backtest
            loop = asyncio.get_running_loop()
            backtest_result = await loop.run_in_executor(
                None,
                run_backtest,
                trading_data,
                params,
                strategy,
                goods_data,
                item.get("size", 1)
            )
            if backtest_result is None:
                continue

            traderResult = backtest_result["traderResult"]
            traderReport = backtest_result["traderReport"]

            # 对交易订单 traderResult还在持仓的，进行盈利结算
            traderResult = await adjust_unpaired_trades(db, item.get("startTime"),
                                                        item.get("endTime"), traderResult)

            # 7. 如果不是手动测试，则写入数据库
            tester_uid = None
            if not item.get("manualBatchTest", 0):
                tester_uid = await self._save_result(
                    db, item, strategy, traderResult, backtest_result
                )

            # 8. 整理响应数据
            result_data.append(self._build_response(item, tester_uid, backtest_result, traderResult, traderReport))

        return result_data

    async def _get_goods(self, db, goods):
        res = await db.execute(select(DqlGoods).where(DqlGoods.goods == goods))
        return res.scalars().first()

    async def _get_kline(self, db, item, strategy):
        # 根据period参数的取值进行条件判断（缓存数据）
        period_tuple = tuple({
            "period": item["period"],
            "tradingGoods": item["goods"],
            "beginTime": item["startTime"],
            "endTime": item["endTime"]
        }.items())

        return await fetch_trading_data(
            db,
            item["goods"],
            item["period"],
            model_classes,
            item["startTime"],
            item["endTime"],
            period_tuple,
            json.loads(strategy.className)
        )

    def _build_params(self, item):
        params = item.get("parameter", {})
        params["Kline_period"] = item["period"]
        params["Kline_goods"] = item["goods"]
        return item

    async def _save_result(self, db, item, strategy, traderResult, backtest):
        tester_uid = await create_strategy_record(db, item, strategy)
        traderReport = backtest["traderReport"]

        await db.execute(
            update(DqlStrategyTestResult)
            .where(DqlStrategyTestResult.uid == tester_uid)
            .values(
                traderResult=json.dumps({
                    "traderResult": traderResult,
                    "traderReport": traderReport,
                    "floatingPointValues": backtest["floatingPointValues"],
                    "netAssetValues": backtest["netAssetValues"]
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
                paramsStrName=item.get("paramsStrName", ""),
                calculationStatus=1
            )
        )
        await db.commit()
        return tester_uid

    def _build_response(self, item, tester_uid, backtest_result, traderResult, traderReport):
        item["testerUids"] = tester_uid
        item["createTime"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        item["account"] = None
        item["userName"] = None
        item["currency"] = "USD"
        item["floatingPointValues"] = backtest_result["floatingPointValues"]
        item["netAssetValues"] = backtest_result["netAssetValues"]
        item["traderResult"] = traderResult
        item["traderReport"] = traderReport
        item["newReportTemplate"] = backtest_result["newReportTemplate"]
        return item


strategy_run_backtest_service = StrategyRunBacktestService()
