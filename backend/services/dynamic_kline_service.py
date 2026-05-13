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

    # ================= ⭐ 主入口 =================
    async def get_dynamic_kline(
            self,
            period: str,
            start_time_str: str,
    ):
        """
        动态0号K接口（跨天 + 动态K + 历史增量K）

        参数:
            period: K线周期 (M1/M5/M15/M30/H1/H4/D1/W1/MN)
            start_time_str: 前端最后一根已完成正式K线时间
            now: 当前系统时间

        返回:
            {
                goods,
                period,
                utc,
                is_final,
                lineData,
                klinePeriodData
            }
        """
        interval_minutes = self.PERIOD_MINUTES[period]

        # ================= 前端最后正式K =================
        if not start_time_str:
            # 首次加载，没有历史K
            return {
                "goods": self.goods,
                "period": period,
                "utc": self.result.utc,
                "is_final": False,
                "lineData": None,
                "klinePeriodData": []
            }

        start_dt = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")

        # ================= 初步计算下一根动态K时间 =================
        dynamic_start = start_dt + datetime.timedelta(minutes=interval_minutes)
        dynamic_end = dynamic_start + datetime.timedelta(minutes=interval_minutes)

        # ================= 检查当天是否有M1数据 =================
        stmt_next_m1 = select(self.model.tradeDateTime).where(
            self.model.platform == self.result.platform,
            self.model.tradingGoods == self.result.trading_goods,
            self.model.type == "M1",
            self.model.tradeDateTime >= dynamic_start
        ).order_by(self.model.tradeDateTime.asc()).limit(1)

        res_next_m1 = await self.db.execute(stmt_next_m1)
        next_m1_dt = res_next_m1.scalar()

        # 如果当天没有M1数据，则跨天到交易日开始（01:00）
        if next_m1_dt is None and dynamic_start.hour < 1:
            next_day = dynamic_start.replace(hour=1, minute=0, second=0, microsecond=0)
            dynamic_start = next_day
            dynamic_end = dynamic_start + datetime.timedelta(minutes=interval_minutes)

        # ================= 查询当前动态K是否已正式生成 =================
        stmt_finished = select(self.model).where(
            self.model.platform == self.result.platform,
            self.model.tradingGoods == self.result.trading_goods,
            self.model.type == period,
            self.model.tradeDateTime == dynamic_start
        )
        res_finished = await self.db.execute(stmt_finished)
        finished_kline = res_finished.scalar()

        # ================= 构建动态K或正式K =================
        if finished_kline:
            # 当前K已完成 → 直接用数据库正式K
            lineData = self.build_kline_dict(finished_kline)
            is_final = True
            dynamic_pk_id = int(finished_kline.pkId)
        else:
            # 当前K未完成 → 聚合M1生成动态K
            m1_rows = await self.query_kline("M1", dynamic_start, dynamic_end)
            lineData = self.build_dynamic_bar(m1_rows, dynamic_start, pk_id=0)
            is_final = False
            dynamic_pk_id = 0

        # ================= 增量返回历史正式K =================
        history = []
        if is_final:
            stmt_history = select(self.model).where(
                self.model.platform == self.result.platform,
                self.model.tradingGoods == self.result.trading_goods,
                self.model.type == period,
                self.model.tradeDateTime > start_dt,
                self.model.tradeDateTime < dynamic_start
            ).order_by(self.model.tradeDateTime)
            res_hist = await self.db.execute(stmt_history)
            history = res_hist.scalars().all()

        return {
            "goods": self.goods,
            "period": period,
            "utc": self.result.utc,
            "is_final": is_final,
            "lineData": lineData,
            "klinePeriodData": [self.build_kline_dict(x) for x in history]
        }