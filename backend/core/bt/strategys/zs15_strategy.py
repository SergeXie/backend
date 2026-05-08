import pytz
import backtrader as bt
from core.bt.base.public_strategy_two import CommonStrategyTwo


class ZuoShi15Strategy(CommonStrategyTwo):
    params = (
        ('price_diff', 15),  # 当日单边走落差15美元
        ('trade_time', 16),  # 下单开始时间点：UTC时间16:00，对应北京时间22:00
        ('risk_reward_ratio', 1.0),  # 止盈/止损比
        ('lot_size', 0.1),  # 每次交易的手数
        ('buffer', 2),  # 止损止盈缓冲
    )

    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
        super().__init__(goodsId)
        # 时区处理
        self.local_time_zone = pytz.timezone('Asia/Shanghai')  # 北京时间
        self.utc_time_zone = pytz.utc

        # 保存每日最高和最低价格及其发生的时间
        self.cur_high = self.cur_low = None
        self.cur_high_dt = self.cur_low_dt = None

        self.last_reversal_dt = None
        self.order = None
        self.cur_day = None
        self.trader_result = []
        self.starting_cash = self.broker.startingcash  # 起始资金
        self.baseLots = baseLots

    def data_dict(self, stop_loss, take_profit):
        """下单过程中，附带额外信息"""
        return dict(stopLoss=stop_loss, takeProfit=take_profit)

    def next(self):
        super().calculate_values()

        # 如果订单存在且已提交或已接受，则跳过
        if self.order:
            if any(x.status in [bt.Order.Submitted, bt.Order.Accepted] for x in self.order):
                return

        utc_datetime = bt.num2date(self.data.datetime[0])
        local_datetime = utc_datetime
        local_hour = local_datetime.hour  # 获取北京时间的小时部分

        # 切换到新的一天时重置变量
        current_date = local_datetime.date()

        # 通过比较当前日期和self.cur_day，判断是否进入新的一天。如果是新的一天，重置当天的最高价、最低价和相应的时间
        if self.cur_day != current_date:
            self.cur_day = current_date
            self.cur_high = None
            self.cur_low = None
            self.cur_high_dt = None
            self.cur_low_dt = None
            self.last_reversal_dt = None  # 重置记录反转K线时间的变量，以便在新的一天中重新计算反转K线。

            print(f"新的一天开始: {current_date}")

        # 仅在北京时间22点之后进行交易
        if local_hour < self.params.trade_time:
            return  # 如果当前时间未达到22:00，直接退出，不进行交易

        # 计算当天的最高价和最高价时间:
        if self.cur_high is None or self.data.high[0] > self.cur_high:
            self.cur_high = self.data.high[0]
            self.cur_high_dt = local_datetime

        # 计算当天最低价和最低价时间
        if self.cur_low is None or self.data.low[0] < self.cur_low:
            self.cur_low = self.data.low[0]
            self.cur_low_dt = local_datetime

        # 确认当日价格差是否满足差值 日内波动过滤
        if (self.cur_high - self.cur_low) < self.params.price_diff:
            return

        # 是否反向K线 && 是否是当日新低点
        last_candle_bullish = self.data.close[-1] > self.data.open[-1]

        last_candle_bearish = self.data.close[-1] < self.data.open[-1]

        # print(f"当前日期：{current_date}, 当前时间：{local_hour}, 当前价格：{self.data.close[0]}")
        # print(f"当天最高价：{self.cur_high}, 最低价：{self.cur_low}, 价格波动差：{self.cur_high - self.cur_low}")
        # print(f"上一根K线是 {'多头' if last_candle_bullish else '空头'}，当前K线是 {'多头' if self.data.close[0] > self.data.open[0] else '空头'}")

        # 空头趋势中出现阳线，当前K线是日内最低点
        if self.data.close[0] > self.data.open[0] and last_candle_bearish:
            # 如果前一根K线是阴线（空头），而当前K线是阳线（多头）， 执行买入操作（做多）
            if self.last_reversal_dt is None or self.cur_low_dt >= self.last_reversal_dt:
                # 确保只在新的反转信号出现时才执行交易。self.last_reversal_dt
                # 保存了上次反转的时间，
                self.last_reversal_dt = self.cur_low_dt

                sl = self.data.low[0] - self.p.buffer
                tp = self.data.close[0] + (self.data.close[0] - sl)

                self.order = self.buy_bracket(
                    price=self.data.close[0], stopprice=sl,
                    size=self.baseLots, limitprice=tp,
                    **self.data_dict(sl, tp))

        # 多头趋势中出现阴线，当前K线是日内最高点
        elif self.data.close[0] < self.data.open[0] and last_candle_bullish:
            # 如果前一根K线是阳线（多头），而当前K线是阴线（空头）， 执行卖出操作（做空）
            if self.last_reversal_dt is None or self.cur_high_dt >= self.last_reversal_dt:
                # 确保只在新的反转信号出现时才执行交易。self.last_reversal_dt
                # 保存了上次反转的时间，
                self.last_reversal_dt = self.cur_high_dt

                sl = self.data.high[0] + self.p.buffer
                tp = self.data.close[0] - (sl - self.data.close[0])
                self.order = self.sell_bracket(
                    price=self.data.close[0],
                    stopprice=sl, size=self.baseLots, limitprice=tp,
                    **self.data_dict(sl, tp))






