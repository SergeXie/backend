import asyncio
import traceback
from fastapi import Request
from sqlalchemy import select
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.dql_platform import DqlIndicators
from utils.common import model_classes, fetch_trading_data
from workers.backtrader_runner import run_backtrader_strategy
async def get_indicator_data_async(request: Request, data_type: str, executor, name):
    try:
        indicator_request = await request.json()
        async with async_db_session() as db:
            tasks = []
            for request_item in indicator_request:
                if not request_item.get("lineId", 0) and data_type == "AfterKline":
                    return await response_base.fail(msg="lineId not found !", data=[])
                select_stmt = select(DqlIndicators).where(
                    DqlIndicators.uid == request_item.get("uid", 0)
                )
                result = await db.execute(select_stmt)
                indicators = result.scalars().first()
                if not indicators:
                    return await response_base.fail(msg="uids not found !", data=[])
                indicator_params = request_item.get("parameter", {})
                indicator_params['Kline_period'] = request_item.get("period", None)
                indicator_params['Kline_goods'] = request_item.get("goods", None)
                period = request_item.get("period", None)
                period_tuple = None
                if period and period[0] in ['H', 'W', 'D', 'M']:
                    period_tuple = tuple({
                        "period": period,
                        "tradingGoods": request_item.get("goods"),
                        "IndicatorName": indicators.name,
                        "lineId": request_item.get("lineId"),
                        "indicatortype": data_type,
                        "begin_time": request_item.get("beginTime"),
                        "end_time": request_item.get("endTime")
                    }.items())
                trading_data = await fetch_trading_data(db, request_item.get("goods", None),
                                                        period,
                                                        model_classes, lineId=request_item.get("lineId", 0),
                                                        name=name,
                                                        begin_time=request_item.get("beginTime", None),
                                                        end_time=request_item.get("endTime", None),
                                                        period_tuple=period_tuple)
                if not trading_data:
                    continue
                # 获取当前正在运行的事件循环（FastAPI 的异步主循环）
                loop = asyncio.get_running_loop()
                # 将回测任务提交到进程池中执行（不会阻塞主线程）
                # run_backtrader_strategy 是一个同步函数，会在独立子进程中运行
                task = loop.run_in_executor(
                    executor, # 使用我们预设的 ProcessPoolExecutor 在后台启动多个子进程，并把任务交给它们去并行执行
                    run_backtrader_strategy, # 要执行的回测函数（同步的）
                    trading_data,
                    indicators.className,
                    indicator_params,
                    indicators.name,
                    indicators.description,
                    indicators.uid,
                    request_item.get("pId"),
                    request_item.get("index", 0),
                    indicators.subType
                )
                # 将这个异步任务加入任务列表，后面统一 await asyncio.gather(tasks) 并发执行
                tasks.append(task)
            result_data = await asyncio.gather(*tasks)
            return await response_base.success(data=result_data)
    except Exception as e:
        info = traceback.format_exc()
        print(f"[ERROR] 获取技术指标数据异常：{info}")
        return await response_base.fail(msg="系统错误！")