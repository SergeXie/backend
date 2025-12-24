import datetime
import calendar
import pandas as pd
from sqlalchemy import select

from utils.common import select_goods_common


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

        # ⚠️ 临时兼容策略（与你原逻辑完全一致）
        if goods == "FPG-XAUUSD_合成":
            goods = "FPG-XAUUSD"

        model, result = await select_goods_common(db, goods, model_classes)

        if not model:
            return None

        return cls(db, model, result, goods)

    # ================= 时间区间 =================

    def calc_period_range(self, period: str, now: datetime.datetime):
        minutes = self.PERIOD_MINUTES[period]

        if period == "W1":
            start = now - datetime.timedelta(days=now.weekday() + 1)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=7)

        elif period == "D1":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=1)

        elif period == "MN":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            _, last_day = calendar.monthrange(now.year, now.month)
            end = start.replace(day=last_day, hour=23, minute=59, second=59)

        else:
            start = now.replace(
                minute=(now.minute // minutes) * minutes,
                second=0,
                microsecond=0
            )
            end = start + datetime.timedelta(minutes=minutes)

        return start, end, minutes

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
        start_time: datetime.datetime
    ):
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

    async def get_dynamic_kline(
        self,
        period: str,
        start_time_str: str,
        now: datetime.datetime
    ):
        start_time, end_time, minutes = self.calc_period_range(period, now)

        # ---------- 0号K ----------
        m1_rows = await self.query_kline("M1", start_time, end_time)
        is_final = not bool(m1_rows)

        if m1_rows:
            df = pd.DataFrame([{
                "tradeDateTime": x.tradeDateTime,
                "opening": float(x.opening),
                "high": float(x.high),
                "low": float(x.low),
                "closed": float(x.closed),
                "vol": x.vol,
                "spread": x.spread,
                "pkId": x.pkId,
                "swapLong": x.swapLong,
                "swapShort": x.swapShort,
            } for x in m1_rows]).set_index("tradeDateTime")

            lineData = self.build_dynamic_bar(df, period, start_time)

        else:
            prev = await self.query_kline(
                period,
                start_time - datetime.timedelta(minutes=minutes),
                start_time,
                limit=1,
                desc=True
            )
            lineData = self.build_kline_dict(prev[0]) if prev else None

        # ---------- 历史K ----------
        if start_time_str:

            start_dt = datetime.datetime.strptime(
                start_time_str, "%Y-%m-%d %H:%M:%S"
            )

            history = await self.query_kline(period, start_dt)
        else:
            history = []

        return {
            "goods": self.goods,
            "period": period,
            "utc": self.result.utc,
            "is_final": is_final,
            "lineData": lineData,
            "klinePeriodData": [self.build_kline_dict(x) for x in history]
        }
