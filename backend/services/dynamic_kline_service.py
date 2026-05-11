import datetime
import pandas as pd
from sqlalchemy import select
from common.common import select_goods_common
from utils.timezone import timezone


class DynamicKlineService:
    """
    动态 0 号 K 线 Service（包含 goods 映射 + model 解析）
    """

    PERIOD_MINUTES = {
        "M1": 1,
        "M5": 5,
        "M15": 15,
        "M30": 30,
        "H1": 60,
        "H4": 240,
        "D1": 1440,
        "W1": 10080,
        "MN": 43800
    }

    PANDAS_FREQ = {
        "M1": "1min",
        "M5": "5min",
        "M15": "15min",
        "M30": "30min",
        "H1": "1h",
        "H4": "4h",
        "D1": "1d",
        "W1": "W",
        "MN": "ME"
    }

    def __init__(self, db, model_class, result, goods: str):
        self.db = db
        self.model = model_class
        self.result = result
        self.goods = goods

    # ================= 工厂方法（收编你指出的那段逻辑） =================

    @classmethod
    async def create(cls, db, goods: str, model_classes):
        """
        统一处理：
        - goods 兼容映射
        - select_goods_common
        """

        #  临时兼容策略（与你原逻辑完全一致）
        if goods == "FPG-XAUUSD_合成":
            goods = "FPG-XAUUSD"

        model, result = await select_goods_common(db, goods, model_classes)

        if not model:
            return None

        return cls(db, model, result, goods)


    # ================= 查询 =================

    async def query_kline(
        self,
        period: str,
        start: datetime.datetime,
        end: datetime.datetime | None = None,
        limit: int | None = None,
        desc: bool = False
    ):
        stmt = select(self.model).where(
            self.model.platform == self.result.platform,
            self.model.tradingGoods == self.result.trading_goods,
            self.model.type == period,
            self.model.tradeDateTime >= start
        )

        if end:
            stmt = stmt.where(self.model.tradeDateTime < end)

        stmt = stmt.order_by(
            self.model.tradeDateTime.desc()
            if desc else self.model.tradeDateTime
        )

        if limit:
            stmt = stmt.limit(limit)

        res = await self.db.execute(stmt)
        return res.scalars().all()

    # ================= K线 dict =================

    @staticmethod
    def build_kline_dict(row):
        return {
            "pkId": int(row.pkId),
            "timestamp": row.tradeDateTime.strftime("%Y-%m-%d %H:%M:%S"),
            "unxTimestamp": int(row.tradeDateTime.timestamp()),
            "open": float(row.opening),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.closed),
            "vol": int(row.vol),
            "spread": float(row.spread),
            "swapLong": float(row.swapLong),
            "swapShort": float(row.swapShort),
        }

    # ================= 动态 0 号 K =================

    def build_dynamic_bar(
        self,
        df: pd.DataFrame,
        period: str,
        start_time: str
    ):
        start_time = timezone.f_str(start_time)

        freq = self.PANDAS_FREQ[period]

        resampled = df.resample(freq).agg({
            "high": "max",
            "low": "min",
            "vol": "sum",
            "spread": "last",
            "pkId": "last",
            "swapLong": "mean",
            "swapShort": "mean",
        })

        resampled["opening"] = df["opening"].resample(freq).first()
        resampled["closed"] = df["closed"].resample(freq).last()

        if resampled.empty:
            return None

        row = resampled.iloc[0]
        return {
            "pkId": int(row.pkId),
            "timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "unxTimestamp": int(start_time.timestamp()),
            "open": float(row.opening),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.closed),
            "vol": int(row.vol),
            "spread": float(row.spread),
            "swapLong": float(row.swapLong),
            "swapShort": float(row.swapShort),
        }

    # ================= ⭐ 主入口 =================

    def calc_current_period(
            self,
            period: str,
            now: datetime.datetime
    ):
        """
        计算当前时间所属动态K周期
        """

        interval_minutes = self.PERIOD_MINUTES[period]

        # ================= W1 =================

        if period == "W1":

            start_time = now - datetime.timedelta(days=now.weekday())

            start_time = start_time.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            end_time = start_time + datetime.timedelta(days=7)

        # ================= D1 =================

        elif period == "D1":

            start_time = now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            end_time = start_time + datetime.timedelta(days=1)

        # ================= MN =================

        elif period == "MN":

            start_time = now.replace(
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            if now.month == 12:

                end_time = now.replace(
                    year=now.year + 1,
                    month=1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0
                )

            else:

                end_time = now.replace(
                    month=now.month + 1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0
                )

        # ================= H4 =================

        elif period == "H4":

            hour = (now.hour // 4) * 4

            start_time = now.replace(
                hour=hour,
                minute=0,
                second=0,
                microsecond=0
            )

            end_time = start_time + datetime.timedelta(hours=4)

        # ================= 普通分钟周期 =================

        else:

            start_time = now.replace(
                minute=(now.minute // interval_minutes) * interval_minutes,
                second=0,
                microsecond=0
            )

            end_time = start_time + datetime.timedelta(
                minutes=interval_minutes
            )

        return start_time, end_time

    async def check_current_kline_finished(
            self,
            period: str,
            dynamic_start: datetime.datetime
    ):
        """
        判断当前动态K
        是否已经正式生成
        """

        stmt = select(self.model).where(
            self.model.platform == self.result.platform,
            self.model.tradingGoods == self.result.trading_goods,
            self.model.type == period,
            self.model.tradeDateTime == dynamic_start
        )

        res = await self.db.execute(stmt)

        return res.scalars().first()

    def build_dynamic_bar(
            self,
            rows,
            start_time: datetime.datetime,
            pk_id: int = 0
    ):
        """
        手动聚合动态K
        """

        if not rows:
            return None

        first = rows[0]
        last = rows[-1]

        return {
            "pkId": pk_id,

            "timestamp": start_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

            "unxTimestamp": int(start_time.timestamp()),

            "open": float(first.opening),

            "high": max(float(x.high) for x in rows),

            "low": min(float(x.low) for x in rows),

            "close": float(last.closed),

            "vol": sum(int(x.vol) for x in rows),

            "spread": float(last.spread),

            "swapLong": float(
                sum(float(x.swapLong) for x in rows)
                / len(rows)
            ),

            "swapShort": float(
                sum(float(x.swapShort) for x in rows)
                / len(rows)
            ),
        }

    async def get_dynamic_kline(
            self,
            period: str,
            start_time_str: str,
    ):
        """
        动态0号K

        startTime:
            前端最后一根正式K

        例如：

        startTime = 09:10
        M5

        当前动态K:
            09:15 ~ 09:20
        """

        # ================= 周期分钟 =================

        interval_minutes = self.PERIOD_MINUTES[period]

        # ================= 前端最后正式K =================

        start_dt = datetime.datetime.strptime(
            start_time_str,
            "%Y-%m-%d %H:%M:%S"
        )

        # ================= 当前动态K时间 =================

        dynamic_start = start_dt + datetime.timedelta(
            minutes=interval_minutes
        )

        dynamic_end = dynamic_start + datetime.timedelta(
            minutes=interval_minutes
        )

        print(f"startTime:{start_time_str}")
        print(f"dynamic_start:{dynamic_start}")
        print(f"dynamic_end:{dynamic_end}")

        # ================= 当前动态K是否已正式生成 =================

        finished_kline = await self.check_current_kline_finished(
            period,
            dynamic_start
        )

        # ================= 当前动态K已正式完成 =================

        if finished_kline:

            is_final = True

            # 直接返回数据库正式K
            lineData = self.build_kline_dict(
                finished_kline
            )

            # 返回新增正式K
            history = [finished_kline]

        # ================= 当前还是动态K =================

        else:

            is_final = False

            # 查询动态K区间M1
            m1_rows = await self.query_kline(
                "M1",
                dynamic_start,
                dynamic_end
            )

            # 动态聚合
            lineData = self.build_dynamic_bar(
                m1_rows,
                dynamic_start,
                pk_id=0
            )

            history = []

        return {
            "goods": self.goods,
            "period": period,
            "utc": self.result.utc,

            # 当前动态K是否正式完成
            "is_final": is_final,

            # 当前K
            "lineData": lineData,

            # 新正式K
            "klinePeriodData": [
                self.build_kline_dict(x)
                for x in history
            ]
        }