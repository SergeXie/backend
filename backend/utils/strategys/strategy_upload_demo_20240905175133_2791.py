# 上传到APP的模板格式
import backtrader as bt
from utils.public_strategy import CommonStrategy


# MACDStrategy 可自定义名字
class MACDStrategy(CommonStrategy):
    # 公共参数定义可以自定义参数
    params = (
        ('fast', 12),   # 快速EMA的周期
        ('slow', 26),   # 慢速EMA的周期
        ('signal', 9),  # 信号线的周期
    )

    # 固定三个参数 indicator_params/goodsId/begin_time
    def __init__(self, indicator_params, goodsId=None, begin_time=None):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)

        # 以下变量可自定义，目的为了实现策略而存在

        # 初始化MACD指标： https://www.backtrader.com/docu/talibindautoref/#macd
        self.macd = bt.indicators.MACD(self.data.close,
                                       period_me1=self.params.fast,
                                       period_me2=self.params.slow,
                                       period_signal=self.params.signal)
        self.order = None

    def next(self):
        """
        策略逻辑
        :return:
        """
        if not self.position:
            # 检查当前的 MACD 线是否大于信号线（self.macd.macd[0] > self.macd.signal[0]），
            # 并且前一个周期的 MACD 线是否小于或等于信号线（self.macd.macd[-1] <= self.macd.signal[0]）
            if self.macd.macd[0] > self.macd.signal[0] and self.macd.macd[-1] <= self.macd.signal[-1]:
                # MACD线上穿信号线时买入
                self.log(f'买入执行, {self.data.close[0]}')
                self.order = self.buy(size=0.1)

        else:
            # 检查当前的 MACD 线是否小于信号线（self.macd.macd[0] < self.macd.signal[0]），
            # 并且前一个周期的 MACD 线是否大于或等于信号线（self.macd.macd[-1] >= self.macd.signal[0]）。
            if self.macd.macd[0] < self.macd.signal[0] and self.macd.macd[-1] >= self.macd.signal[-1]:
                # MACD线下穿信号线时卖出
                self.log(f'卖出执行, {self.data.close[0]}')
                self.order = self.sell(size=0.1)