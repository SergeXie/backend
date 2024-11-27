import backtrader as bt
from utils.public_strategy import CommonStrategy


# 定义第一个策略类：均线交叉策略
# 当短期均线（短期周期设为10）上穿长期均线（长期周期设为30）时买入；当短期均线下穿长期均线时卖出。
class MovingAverageCrossStrategy(CommonStrategy):
    params = (
        ('short_period', 20),  # 短期均线周期
        ('long_period', 50),  # 长期均线周期
        ('name', None),  # 策略名称
    )

    def __init__(self, indicator_params, goodsId=None, begin_time=None):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        self.short_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.short_period)
        self.long_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.long_period)

        self.order = None

    def next(self):
        stop_loss = self.data.open[0] + 2
        if not self.position:  # 如果没有持仓
            if self.short_ma > self.long_ma:
                self.order = self.buy(size=0.1)
                self.order.addinfo(strategy_name=self.params.name, stopLoss=stop_loss, takeProfit=0)

        elif self.short_ma < self.long_ma:
            self.order = self.sell(size=0.1)
            self.order.addinfo(strategy_name=self.params.name, stopLoss=stop_loss, takeProfit=0)


# 定义第二个策略类：布林带突破策略
# 当价格突破布林带上轨时买入；当价格跌破布林带下轨时卖出。
class BollingerBandsStrategy(CommonStrategy):
    params = (
        ('period', 20),  # 布林带周期
        ('devfactor', 2),  # 标准差倍数
        ('name', None),  # 策略名称

    )

    def __init__(self, indicator_params, goodsId=None, begin_time=None):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        self.bollinger = bt.indicators.BollingerBands(
            self.data.close, period=self.params.period, devfactor=self.params.devfactor)

        self.order = None

    def next(self):
        stop_loss = self.data.open[0] + 2
        if not self.position:  # 如果没有持仓
            if self.data.close > self.bollinger.lines.top:
                self.order = self.buy()  # 价格突破布林带上轨，买入
                self.order.addinfo(strategy_name=self.params.name, stopLoss=stop_loss, takeProfit=0)

        elif self.data.close < self.bollinger.lines.bot:
            self.order = self.sell()  # 价格跌破布林带下轨，卖出
            self.order.addinfo(strategy_name=self.params.name, stopLoss=stop_loss, takeProfit=0)


