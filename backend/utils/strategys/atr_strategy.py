import datetime

import backtrader as bt
from utils.indicators import ATRStopLoss
from utils.public_strategy import CommonStrategy


class ATRStrategy(CommonStrategy):
    # 初始化各种指标、设置变量，以及为策略的其他部分做准备
    def __init__(self, indicator_params, goodsId=None, begin_time=None):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        # 接收参数变量
        self.indicator_params = indicator_params
        # 初始化指标
        self.atr_stoploss = ATRStopLoss(self.data,
                                        atr_len=self.indicator_params.get("period", 10),
                                        multiplier=self.indicator_params.get("Multiplier", 3.0))
        # 设置变量
        self.atr_len = self.indicator_params.get("period", 10)
        self.data_line_count = 0
        self.dataspread = self.datas[0].spread
        self.prev_trend = 0
        if not begin_time:
            begin_time='2014-08-15 00:00:00'
            self.need_closr = False
        else:
            self.need_closr = True
        self.start_date = datetime.datetime.strptime(begin_time, '%Y-%m-%d %H:%M:%S')  # 设置开始日期

    def next(self):
        """
        next 方法是 Backtrader 策略的核心之一。它会在每个新的数据点（通常是每个新的 K 线）到达时被调用.
        策略正常运行阶段，对应从第一根K线到最后一根bar
        进入该阶段后，会依次在每个bar上循环运行next函数
        :return:
        """
        # 当前循环的第多少根k线记录
        self.data_line_count += 1

        # 调用父类方法 （固定写法）
        super().calculate_values()

        #  小于起始时间的不做策略回测
        if self.datas[0].datetime.datetime(0) <= self.start_date:
            return


        # 趋势反转变化
        trend = self.atr_stoploss.lines.trend_change[0]

        if trend == 1 or trend == -1:
            if self.prev_trend == 0:
                self.prev_trend = trend
            else:
                if self.prev_trend != trend:
                    # 检查是否有持仓
                    if not self.position:
                        if trend == 1:
                            self.order = self.buy(size=0.1)
                        elif trend == -1:
                            self.order = self.sell(size=0.1)
                    else:
                        if self.atr_stoploss.lines.trend_change[0] != self.atr_stoploss.lines.trend_change[-1]:
                            if trend == -1 and self.position.size > 0:
                                self.order = self.close(size=0.1)  # 平仓，以下一日开盘价卖出

                                # 平仓后立即卖出
                                self.order = self.sell(size=0.1)

                            elif trend == 1 and self.position.size < 0:
                                self.order = self.close(size=0.1)  # 平仓，以下一日开盘价卖出
                                # 平仓后立即买入
                                self.order = self.buy(size=0.1)

                    self.prev_trend = trend

        else:
            print("Invalid trend value")

        # 检查是否到达数据末尾且仍持有仓位
        if self.need_closr:
            if self.data_line_count == (self.data.buflen() - (self.atr_len + 1)) and self.position:
                print("执行最后关仓")
                self.order = self.close()  # 平仓，以下一日开盘价卖出
        else:
            pass

