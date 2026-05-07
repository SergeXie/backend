import datetime

import backtrader as bt
from core.bt.indicators import ATRStopLoss
from core.bt.base.public_strategy import CommonStrategy

# CommonStrategy
class ATRStrategy(CommonStrategy):

    def log(self, txt, dt=None):
        '''记录策略日志'''
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f'{dt}, {txt}')
    # 初始化各种指标、设置变量，以及为策略的其他部分做准备
    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
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
        self.baseLots = baseLots
        if not begin_time:
            begin_time='2014-08-15 00:00:00'
            self.need_closr = False
        else:
            self.need_closr = True
        self.start_date = datetime.datetime.strptime(begin_time, '%Y-%m-%d %H:%M:%S')  # 设置开始日期

        self.Diff = self.indicator_params.get("Diff", 0)
        print('是我', self.indicator_params)

    def notify_trade(self, trade):
        super().notify_trade(trade)


        if trade.justopened:
            # self.log(self.datas[0].datetime.datetime(0),f"Trade opened: {'BUY' if trade.size > 0 else 'SELL'}, Size: {abs(trade.size)}")
            self.log(self.datas[0].datetime.datetime(0),f"Trade opened: {'BUY' if trade.size > 0 else 'SELL'}")

            # print()
        elif trade.isclosed:
            # self.log(self.datas[0].datetime.datetime(0),f"Trade closed: Gross P&L: {trade.pnl}, Net P&L: {trade.pnlcomm}")
            # self.log(self.datas[0].datetime.datetime(0),f"Trade closed")
            pass

            # print()

    # def notify_order(self, order):
        # # 挂单交易的状态变化监控
        # if order.status == order.Created:
        #     self.log(f"限价单创建: 价格={order.price}, 数量={order.size}")
        #
        # # elif order.status == order.Submitted:
        # #     self.log("限价单已提交至经纪商")
        #
        # elif order.status == order.Accepted:
        #     self.log("限价单已被接受，等待价格触发...")
        #
        # elif order.status == order.Partial:
        #     self.log(f"限价单部分成交: 已成交={order.executed.size}, 剩余={order.size - order.executed.size}")

        # if order.status == order.Completed:
        #     if order.isbuy():
        #         self.log(f"买入限价单完全成交: 价格={order.executed.price}, 总成本={order.executed.value}")
        #     else:
        #         self.log(f"卖出限价单完全成交: 价格={order.executed.price}, 总收入={order.executed.value}")
        #
        # elif order.status in [order.Canceled, order.Expired, order.Rejected]:
        #     self.log(f"限价单终止: 状态={order.Status[order.status]}")

    def next(self):
        """
        next 方法是 Backtrader 策略的核心之一。它会在每个新的数据点（通常是每个新的 K 线）到达时被调用.
        策略正常运行阶段，对应从第一根K线到最后一根bar
        进入该阶段后，会依次在每个bar上循环运行next函数
        :return:
        """
        # 当前循环的第多少根k线记录
        self.data_line_count += 1

        # # 调用父类方法 （固定写法）
        # super().calculate_values()

        #  小于起始时间的不做策略回测
        if self.datas[0].datetime.datetime(0) <= self.start_date:
            return

        # # 获取当前日期和时间
        # current_datetime = self.datas[0].datetime.datetime(0)
        #
        # # 定义目标下单时间
        # target_datetime = datetime.datetime(2025, 4, 3, 1, 0, 0)
        # if current_datetime == target_datetime:
        #     limit_price = self.atr_stoploss.lines.target_up[0]
        #     print(f"当前Bar信息 - High: {self.data.high[0]}, Low: {self.data.low[0]}, Close: {self.data.close[0]}")
        #     print(f"下限价买单，价格: {limit_price}",self.atr_stoploss.lines.trend_change[0])
        #     self.order = self.buy(exectype=bt.Order.Limit, price=2979)

        # 趋势反转变化
        trend = self.atr_stoploss.lines.trend_change[0]

        if trend == 1 or trend == -1:
            if self.prev_trend == 0:
                self.prev_trend = trend
            else:
                if self.prev_trend != trend:
                    # 检查是否有持仓
                    if self.broker.orders:  # 在反转点有挂单就取消
                        for order in self.broker.get_orders_open():
                            self.log('取消挂单')
                            self.broker.cancel(order)
                    if self.position:  # 有持仓就平仓
                        self.log('close')
                        self.order = self.close()

                    if trend == 1:
                        print(self.datas[0].datetime.datetime(0),'  开始挂单buy',self.atr_stoploss.lines.target_up[0])
                        self.order = self.buy(exectype=bt.Order.Limit, price=self.atr_stoploss.lines.target_up[0]+self.Diff,size=self.baseLots)
                    elif trend == -1:
                        print(self.datas[0].datetime.datetime(0),'  开始挂单sell', self.atr_stoploss.lines.target_dn[0])
                        self.order = self.sell(exectype=bt.Order.Limit, price=self.atr_stoploss.lines.target_dn[0]-self.Diff,size=self.baseLots)

                elif self.prev_trend == trend and len(self.broker.get_orders_open()) != 0:
                    if trend == 1 and self.atr_stoploss.lines.target_up[0] != self.atr_stoploss.lines.target_up[-1]:
                        for order in self.broker.get_orders_open():
                            self.broker.cancel(order)
                        print(self.datas[0].datetime.datetime(0),'  取消后挂buy单', self.atr_stoploss.lines.target_up[0])
                        self.order = self.buy(exectype=bt.Order.Limit, price=self.atr_stoploss.lines.target_up[0]+self.Diff,size=self.baseLots)
                    elif trend == -1 and self.atr_stoploss.lines.target_dn[0] != self.atr_stoploss.lines.target_dn[-1]:
                        for order in self.broker.get_orders_open():
                            self.broker.cancel(order)
                        print(self.datas[0].datetime.datetime(0), '  取消后挂sell单', self.atr_stoploss.lines.target_dn[0])
                        self.order = self.sell(exectype=bt.Order.Limit, price=self.atr_stoploss.lines.target_dn[0]-self.Diff,size=self.baseLots)

                self.prev_trend = trend



        # 检查是否到达数据末尾且仍持有仓位
        if self.need_closr:
            if self.data_line_count == (self.data.buflen() - (self.atr_len + 1)):
                print("执行最后关仓 K 线数量：{}".format(self.data_line_count))
                # self.order = self.close()  # 平仓，以下一日开盘价卖出
                # self.cancel(self.order)

        else:
            pass

    # def stop(self):
    #     print('self.Diff',self.Diff)
    #     print(self.broker.orders[-1])
    #     print(self.broker.orders[-1].Status in [bt.Order.Completed])
    #     # 检查是否有挂单
    #     if self.broker.orders:
    #         print(f"[{self.datas[0].datetime.datetime(0)}] 还有挂单存在:")
    #         for o in self.broker.orders:
    #             print(f"  ➤ 挂单类型: {o.getordername()}, 价格: {o.price}, 状态: {o.Status[o.status]}")
    #     else:
    #         print("✔ 无挂单")
    #
    #     # 检查是否有持仓
    #     if self.position:
    #         print(f"❗策略结束时仍持仓：持仓量 {self.position.size}, 成本价 {self.position.price}")
    #     else:
    #         print("✔ 无持仓")
    #
    #     self.cancel(self.order)
    #     if self.broker.orders:
    #         print(f"[{self.datas[0].datetime.datetime(0)}] 还有挂单存在:")
    #         for o in self.broker.orders:
    #             print(f"  ➤ 挂单类型: {o.getordername()}, 价格: {o.price}, 状态: {o.Status[o.status]}")
    #     else:
    #         print("✔ 无挂单")