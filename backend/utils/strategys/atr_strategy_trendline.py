import datetime
import numpy as np

import backtrader as bt
from utils.indicators import ATRStopLoss
from utils.public_strategy import CommonStrategy

class ATRStopLoss(bt.Indicator):

    lines = ('target_dn', 'target_up', 'trend_change', 'ATR',
             'target_dn1', 'target_up1')
    params = (
        ('atr_len', 10),  # ATR 计算周期
        ('multiplier', 3.0),  # ATR 的乘数
    )

    plotinfo = dict(subplot=False, plotlinelabels=True)  # 将指标放在主图表中

    def __init__(self):
        self.atr = bt.indicators.AverageTrueRange(self.data, period=self.params.atr_len)
        self.src = (self.data.high + self.data.low) / 2
        self.lines.target_dn = self.src + self.p.multiplier * self.atr
        self.lines.target_up = self.src - self.p.multiplier * self.atr
        self.count_change = 0
        self.count_up = 0
        self.count_dn = 0
        self.change = 0

    def next(self):
        d_change = self.lines.trend_change[-1]
        if np.isnan(d_change):
            self.lines.trend_change[0] = 1
        else:
            up1 = self.lines.target_up[-1]
            dn1 = self.lines.target_dn[-1]

            # 更新 target_up 和 target_dn
            self.lines.target_up[0] = max(self.lines.target_up[0], up1) if self.data.close[-1] > up1 else self.lines.target_up[0]
            self.lines.target_dn[0] = min(self.lines.target_dn[0], dn1) if self.data.close[-1] < dn1 else self.lines.target_dn[0]

            # 获取前一个趋势
            trend1 = self.lines.trend_change[-1]

            if trend1 == -1 and self.data.close[0] > self.lines.target_dn[-1]:
                self.lines.trend_change[0] = 1
            else:
                if trend1 == 1 and self.data.close[0] < self.lines.target_up[-1]:
                    self.lines.trend_change[0] = -1
                else:
                    self.lines.trend_change[0] = trend1

            self.lines.target_dn1[0] = self.lines.target_dn[0]
            self.lines.target_up1[0] = self.lines.target_up[0]
            # 根据趋势变化更新上下限
            if self.lines.trend_change[0] == 1:
                self.lines.target_dn[0] = np.nan
            elif self.lines.trend_change[0] == -1:
                self.lines.target_up[0] = np.nan

class MyStrategy(CommonStrategy):

    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        # 接收参数变量
        self.indicator_params = indicator_params
        self.baseLots = baseLots
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
            begin_time = '2014-08-15 00:00:00'
            self.need_closr = False
        else:
            self.need_closr = True
        self.start_date = datetime.datetime.strptime(begin_time, '%Y-%m-%d %H:%M:%S')  # 设置开始日期


        self.atr_stoploss = ATRStopLoss(self.data)
        self.atr_len = self.atr_stoploss.params.atr_len
        self.data_line_count = 0
        self.er_data_line_count = 0
        self.new_trend_change = 0
        self.trend_change = self.atr_stoploss.lines.trend_change

        self.dataclose = self.datas[0].close
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.dataopen = self.datas[0].open
        self.trade_xinhao = 0

    def next(self):
        # print(self.atr_stoploss.lines.target_dn[0], self.atr_stoploss.lines.target_up[0], self.atr_stoploss.lines.trend_change[0])
        self.data_line_count += 1

        # 获取当前数据点的时间
        current_date = self.datas[0].datetime.datetime(0)

        # 只在 current_date 大于等于 start_date 时执行策略逻辑
        if current_date <= self.start_date:
            self.er_data_line_count += 1
            return

        trend = self.atr_stoploss.lines.trend_change[0]
        if trend == 1 or trend == -1:
            if self.prev_trend == 0:  # 跳过第一条
                self.prev_trend = trend
            else:
                if not self.position and self.prev_trend == trend:
                    if self.trade_xinhao == 1 and self.atr_stoploss.lines.target_up[0] != \
                            self.atr_stoploss.lines.target_up[-1]:
                        self.private_modify(limit_price=self.atr_stoploss.lines.target_up[0],size=10)
                    elif self.trade_xinhao == -1 and self.atr_stoploss.lines.target_dn[0] != \
                            self.atr_stoploss.lines.target_dn[-1]:
                        self.private_modify(limit_price=self.atr_stoploss.lines.target_dn[0],size=10)

                if self.prev_trend != trend:  # 信号反转
                    if not self.position:  # 不持仓
                        if trend == 1:
                            self.trade_xinhao = 1
                            self.private_buy_limit(limit_price=self.atr_stoploss.lines.target_up[0])
                        elif trend == -1:
                            self.trade_xinhao = -1
                            self.private_sell_limit(limit_price=self.atr_stoploss.lines.target_dn[0])
                    else:  # 持仓
                        if self.atr_stoploss.lines.trend_change[0] != self.atr_stoploss.lines.trend_change[-1]:
                            if trend == -1 and self.position.size > 0:
                                self.order = self.close(size=self.baseLots)  # 平仓，以下一日开盘价卖出
                                self.trade_xinhao = -1
                                self.private_sell_limit(limit_price=self.atr_stoploss.lines.target_dn[0])
                            elif trend == 1 and self.position.size < 0:
                                self.order = self.close(size=self.baseLots)  # 平仓，以下一日开盘价卖出
                                self.trade_xinhao = 1
                                self.private_buy_limit(limit_price=self.atr_stoploss.lines.target_up[0])
                    self.prev_trend = trend

            if not self.position:
                if self.trade_xinhao == 1 and self.data.low <= self.atr_stoploss.lines.target_up[0]:
                    self.order = self.buy(size=self.baseLots)
                    self.trade_xinhao = 0
                elif self.trade_xinhao == -1 and self.data.high >= self.atr_stoploss.lines.target_dn[0]:
                    self.order = self.sell(size=self.baseLots)
                    self.trade_xinhao = 0


            # 检查是否到达数据末尾且仍持有仓位
            if self.data_line_count == (self.data.buflen() - (self.atr_len + 1)) and self.position:
                pass


                # self.order = self.close()  # 平仓，以下一日开盘价卖出

        else:
            print("Invalid trend value")

        # print("---end---", self.data_line_count, current_date, len(self.get_orderpoint().orderpoint_list))

    # def stop(self):
    #     super().stop()
    #     self.order = self.buy(size=0.1)
    #     print(self.get_orderpoint().orderpoint_list)


