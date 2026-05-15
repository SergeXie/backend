import datetime
from sqlalchemy import select

from common.common import select_goods_common
from common.response.response_schema import response_base


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
            raise response_base.fail(msg="品种数据未找到！", data=[])

        return cls(db, model, result, goods)


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

    def align_period_start(
            self,
            dt: datetime.datetime,
            period: str
    ):
        """
        Align a data timestamp to the start of its K-line period.
        """

        period = period.upper()
        if period not in self.PERIOD_MINUTES:
            raise response_base.fail(msg="K线周期不支持！", data=[])

        interval_minutes = self.PERIOD_MINUTES[period]

        if period == "D1":
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)

        if period == "W1":
            week_start = dt - datetime.timedelta(days=dt.weekday())
            return week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        if period == "MN":
            return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if period == "H4":
            trading_day_start = dt.replace(hour=1, minute=0, second=0, microsecond=0)
            if dt < trading_day_start:
                return trading_day_start - datetime.timedelta(hours=4)

            elapsed_minutes = int((dt - trading_day_start).total_seconds() // 60)
            aligned_minutes = (elapsed_minutes // interval_minutes) * interval_minutes
            return trading_day_start + datetime.timedelta(minutes=aligned_minutes)

        day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elapsed_minutes = dt.hour * 60 + dt.minute
        aligned_minutes = (elapsed_minutes // interval_minutes) * interval_minutes
        return day_start + datetime.timedelta(minutes=aligned_minutes)

    async def resolve_dynamic_window(
            self,
            period: str,
            dynamic_start: datetime.datetime,
            dynamic_end: datetime.datetime
    ):
        """
        Move an empty dynamic window to the next real M1 period.
        """

        m1_rows = await self.query_kline("M1", dynamic_start, dynamic_end)
        if m1_rows:
            return dynamic_start, dynamic_end, m1_rows

        stmt_next_m1 = select(self.model.tradeDateTime).where(
            self.model.platform == self.result.platform,
            self.model.tradingGoods == self.result.trading_goods,
            self.model.type == "M1",
            self.model.tradeDateTime >= dynamic_start
        ).order_by(self.model.tradeDateTime.asc()).limit(1)

        res_next_m1 = await self.db.execute(stmt_next_m1)
        next_m1_dt = res_next_m1.scalar()

        if next_m1_dt:
            next_start = self.align_period_start(next_m1_dt, period)
            if next_start != dynamic_start:
                dynamic_start = next_start
                dynamic_end = dynamic_start + datetime.timedelta(
                    minutes=self.PERIOD_MINUTES[period]
                )
                m1_rows = await self.query_kline("M1", dynamic_start, dynamic_end)
            return dynamic_start, dynamic_end, m1_rows

        if dynamic_start.hour < 1:
            dynamic_start = dynamic_start.replace(
                hour=1,
                minute=0,
                second=0,
                microsecond=0
            )
            dynamic_end = dynamic_start + datetime.timedelta(
                minutes=self.PERIOD_MINUTES[period]
            )

        return dynamic_start, dynamic_end, []

    async def query_finished_kline(
            self,
            period: str,
            dynamic_start: datetime.datetime
    ):
        stmt = select(self.model).where(
            self.model.platform == self.result.platform,
            self.model.tradingGoods == self.result.trading_goods,
            self.model.type == period,
            self.model.tradeDateTime == dynamic_start
        )
        res = await self.db.execute(stmt)
        return res.scalar()

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
        period = period.upper()
        if period not in self.PERIOD_MINUTES:
            raise response_base.fail(msg="K线周期不支持！", data=[])

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

        try:
            start_dt = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise response_base.fail(msg="startTime格式错误，应为YYYY-MM-DD HH:MM:SS", data=[])

        # ================= 初步计算下一根动态K时间 =================
        dynamic_start = start_dt + datetime.timedelta(minutes=interval_minutes)
        dynamic_end = dynamic_start + datetime.timedelta(minutes=interval_minutes)

        # ================= 查询当前动态K是否已正式生成 =================
        finished_kline = await self.query_finished_kline(period, dynamic_start)
        m1_rows = []
        if not finished_kline:
            dynamic_start, dynamic_end, m1_rows = await self.resolve_dynamic_window(
                period,
                dynamic_start,
                dynamic_end
            )
            finished_kline = await self.query_finished_kline(period, dynamic_start)

        # ================= 构建动态K或正式K =================
        if finished_kline:
            # 当前K已完成 → 直接用数据库正式K
            lineData = self.build_kline_dict(finished_kline)
            is_final = True
        else:
            # 当前K未完成 → 聚合M1生成动态K
            lineData = self.build_dynamic_bar(m1_rows, dynamic_start, pk_id=0)
            is_final = False

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
