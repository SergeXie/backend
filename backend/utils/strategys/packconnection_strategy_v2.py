from utils.indicators.indicators_common import TempInd, Custom_indicators
import numpy as np
from utils.public_strategy import CommonStrategy


class PCStrategy(CommonStrategy):

    # 初始化各种指标、设置变量，以及为策略的其他部分做准备
    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId=None)
        self.indicator_params = indicator_params
        self.TI = TempInd(self.data, diff=self.indicator_params.get("NumericalDifference", 1),
                          IsRightKBroken=self.indicator_params.get("IsRightKBroken", 1),
                          IsLeftKOffset=self.indicator_params.get("IsLeftKOffset", 1),
                          )
        self.CI = Custom_indicators(self.data, self.indicator_params)

        self.open_list = []
        self.date = []
        self.order = None
        self.trades = []
        self.last_cash = self.broker.get_cash()
        self.last_value = self.broker.getvalue()
        self.data_line_count = 0
        self.trend_change_last = 0
        self.tm = 0  # tm用于判断平仓后要不要进行买卖
        self.sltp = 0
        self.baseLots = baseLots

    def next(self):
        """
        next 方法是 Backtrader 策略的核心之一。它会在每个新的数据点（通常是每个新的 K 线）到达时被调用.
        策略正常运行阶段，对应从第一根K线到最后一根bar
        进入该阶段后，会依次在每个bar上循环运行next函数
        :return:
        """

        # 调用父类方法 （固定写法）
        super().calculate_values()
        self.data_line_count += 1
        trend_change_now = self.TI.lines.mountain_poit_index[0]  # 获取当前

        # print(sltp, len(self), self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'))

        if not self.position and (self.data.buflen() - self.data_line_count > 1):  # 没有持仓
            # print('$' * 20)
            if self.broker.get_cash() < 0:
                self.tm = -2

            if trend_change_now == -1:
                self.sltp = self.TI.lines.mountain_poit_index_sltp[0]
                print("没有持仓，开始买入", self.sltp)
                self.order = self.buy(size=self.baseLots)
                self.trend_change_last = trend_change_now
                mou_mon = self.data.close[0]
            elif trend_change_now == 1:
                self.sltp = self.TI.lines.mountain_poit_index_sltp[0]
                print("没有持仓，开始卖出", self.sltp)
                self.order = self.sell(size=self.baseLots)
                self.trend_change_last = trend_change_now
                mou_mon = self.data.close[0]

            # if not np.isnan(self.TI.lines.left[-1]):
            #     le = self.TI.lines.left[-1]
            # else:
            #     le = 0

            # # le = self.TI.lines.left[-1] if not np.isnan(self.TI.lines.left[-1]) else 0
            # if self.tm == -1 and self.data.low[0] > self.data.low[-int(le)]:
            #     print("开多仓")
            #     self.order = self.buy(size=0.1)
            #     self.trend_change_last = -1
            # elif self.tm == 1 and self.data.high[0] < self.data.high[-int(le)]:
            #     print("开空仓")
            #     self.order = self.sell(size=0.1)
            #     self.trend_change_last = 1
            # else:
            #     self.tm = 0


        else:  # 若持仓
            if self.position.size < 0 and self.data.high[0] > self.sltp:  # 持有空头仓位
                print("空头止损")
                self.order = self.close(size=self.baseLots)  # 平仓
            elif self.position.size > 0 and self.data.low[0] < self.sltp:  # 持有多头仓位
                print("多头止损")
                self.order = self.close(size=self.baseLots)  # 平仓

            if trend_change_now and trend_change_now != self.trend_change_last:  # 当前趋势与上一个趋势不同
                close_now = self.data.close[0]
                if trend_change_now == -1 and self.position.size < 0 :  # 如果当前为底 持有空头仓位
                    print("翻转时平空仓")
                    self.order = self.close(size=self.baseLots)  # 平仓
                    self.order = self.buy(size=self.baseLots)
                    self.sltp = self.TI.lines.mountain_poit_index_sltp[0]
                    self.trend_change_last = trend_change_now

                elif trend_change_now == 1 and self.position.size > 0:  # 如果当前为顶 持有多头仓位
                    print("翻转时平多仓")
                    self.order = self.close(size=self.baseLots)  # 平仓
                    self.order = self.sell(size=self.baseLots)
                    self.sltp = self.TI.lines.mountain_poit_index_sltp[0]
                    self.trend_change_last = trend_change_now

        if (self.data_line_count == self.data.buflen()-1) and self.position:
            print("end", self.position.size)
            self.order = self.close(size=self.baseLots)