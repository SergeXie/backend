import datetime
import time
from sqlalchemy import select, and_
from common.log import log
from models.dql_platform import TradingFPG


class MarketStatisticsObject:

    # 时间周期映射
    INTERVALS = {
        "m5": datetime.timedelta(minutes=5),
        "m30": datetime.timedelta(minutes=30),
        "h1": datetime.timedelta(hours=1),
        "d1": datetime.timedelta(days=1),
        "w1": datetime.timedelta(weeks=1),
    }

    @staticmethod
    # 时间格式输出标准化
    def to_str(dt: datetime.datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def aggregate_kline(kline_rows):
        """传入 ORM 对象列表，返回 OHLC 聚合结果"""

        if not kline_rows:
            return None

        t0 = time.perf_counter()

        result = {
            "open": float(kline_rows[0].opening),
            "high": float(max(row.high for row in kline_rows)),
            "low": float(min(row.low for row in kline_rows)),
            "close": float(kline_rows[-1].closed),
        }

        t1 = time.perf_counter()
        cost_ms = (t1 - t0) * 1000

        log.info(f"aggregate_kline 聚合耗时: {cost_ms:.4f} ms  | 行数: {len(kline_rows)}")

        return result

    @staticmethod
    async def _get_kline(db, start, end):
        """获取某时间段的 M1 K线（TradingFPG）"""
        t0 = time.perf_counter()

        stmt = (
            select(TradingFPG)
            .where(
                and_(
                    TradingFPG.tradingGoods == "XAUUSD",
                    TradingFPG.platform == "FPG",
                    TradingFPG.type == "M1",
                    TradingFPG.tradeDateTime.between(start, end),
                )
            )
            .order_by(TradingFPG.tradeDateTime.asc())
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        t1 = time.perf_counter()
        cost_ms = (t1 - t0) * 1000

        return rows, cost_ms

    @classmethod
    async def get_statistics(cls, db, name, time_str):
        """主入口：根据发布时间计算各周期 K线统计"""

        try:
            base_time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            log.info(f"时间格式错误: {time_str}")
            return None

        log.info(f" 处理 {name} ({time_str})")

        data = {}

        # ⭐ 构建 PeriodRange（字符串时间 + 列表）
        periodRange = {
            key: [
                cls.to_str(base_time),
                cls.to_str(base_time + delta)
            ]
            for key, delta in cls.INTERVALS.items()
        }

        for key, delta in cls.INTERVALS.items():

            start_time = base_time
            end_time = base_time + delta

            # 1 次查询：最大区间就是 W1
            end_time_max = base_time + datetime.timedelta(weeks=1)

            # 一次取回所有 M1 数据
            rows, cost = await cls._get_kline(db, base_time, end_time_max)
            log.info("查询耗时:{} {}".format(cost, "ms"))

            # 然后按周期切片
            period_data = {
                "m5": [r for r in rows if r.tradeDateTime < base_time + datetime.timedelta(minutes=5)],
                "m30": [r for r in rows if r.tradeDateTime < base_time + datetime.timedelta(minutes=30)],
                "h1": [r for r in rows if r.tradeDateTime < base_time + datetime.timedelta(hours=1)],
                "d1": [r for r in rows if r.tradeDateTime < base_time + datetime.timedelta(days=1)],
                "w1": rows,  # 全部
            }

            log.info("周期:{} 起始时间：{} 结束时间：{}".format(key, start_time, end_time))

            # 聚合
            agg = cls.aggregate_kline(period_data[key])

            # agg = cls.aggregate_kline(kline_rows)

            if agg:
                data[key] = f"{agg['open']},{agg['high']},{agg['low']},{agg['close']}"
            else:
                data[key] = None

        print("最终结果：", data)
        return data,periodRange
