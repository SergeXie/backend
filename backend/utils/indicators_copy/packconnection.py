from utils.indicators.indicators_common import Custom_indicators, TempInd
import backtrader as bt
import numpy as np


class ResponsePCData(bt.Strategy):
    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_name = indicator_name
        self.comments = comments
        self.indicator_params = indicator_params
        self.PCdata = Custom_indicators(self.data, self.indicator_params)
        self.result_data_dict = dict()
        self.result_data = []
        self.buy_poit = []
        self.sell_poit = []
        self.close_poit = []
        self.title = {}
        self.TI = TempInd(self.data, diff=self.indicator_params.get("NumericalDifference", 1))
        self.date = []
        self.order = None
        self.data_line_count = 0
        self.trend_change_last = 0
        self.tm = 0  # tm用于判断平仓后要不要进行买卖

    def next(self):
        self.mountain_poit = self.PCdata.lines.mountain_poit_line[0]
        if np.isnan(self.mountain_poit):
            self.mountain_poit = None

        current_kline_id = int(self.data.klineId[0])

        self.data_line_count += 1
        trend_change_now = self.TI.lines.mountain_poit_index[0]  # 获取当前

        if not self.position and (self.data.buflen() - self.data_line_count > 1):  # 没有持仓
            if self.broker.get_cash() < 0:
                self.tm = -2
            if trend_change_now == -1 and self.tm == 0:
                # print("没有持仓，开始买入")
                self.buy_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.high[0]})
                self.trend_change_last = trend_change_now

            elif trend_change_now == 1 and self.tm == 0:
                # print("没有持仓，开始卖出")
                self.sell_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.low[0]})

                self.trend_change_last = trend_change_now
            if not np.isnan(self.TI.lines.left[-1]):
                le = self.TI.lines.left[-1]
            else:
                le = 0

            if self.tm == -1 and self.data.low[0] > self.data.low[-int(le)]:
                self.buy_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.high[0]})
                # print("开始买入")
                self.trend_change_last = -1
            elif self.tm == 1 and self.data.high[0] < self.data.high[-int(le)]:
                self.sell_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.low[0]})
                # print("开始卖出")
                self.trend_change_last = 1
            else:
                self.tm = 0
        else:
            if trend_change_now != self.trend_change_last:
                close_now = self.data.close[0]
                if trend_change_now == -1 and self.position.size < 0 :  # 如果当前为底 持有空头仓位
                    self.close_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.low[0]})
                    self.trend_change_last = trend_change_now
                    self.tm = -1   # 只有当前的k的最低比底的底大 ，表明上升趋势， 开始做多

                elif trend_change_now == 1 and self.position.size > 0:  # 如果当前为顶 持有多头仓位
                    self.close_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.low[0]})

                    self.trend_change_last = trend_change_now
                    self.tm = 1   # 当前的k的最高比顶的高大 ，表明下降趋势， 开始做空

        if (self.data_line_count == self.data.buflen()-1) and self.position:
            pass

        # 将数据添加到结果列表
        self.mountain_poit2 = self.TI.lines.mountain_poit[0]
        if np.isnan(self.mountain_poit2):
            self.mountain_poit2 = None
        else:
            self.result_data.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.mountain_poit2,
            })

    def stop(self):
        self.notnallpoint = [[index, value] for index, value in enumerate(self.TI.lines.mountain_poit.array) if
                             not np.isnan(value)]
        current_kline_id = int(self.data.klineId[0])
        self.title = [
            {
                "kLineId": int(self.data.klineId[-2]),
                "timestamp": self.datas[0].datetime.datetime(-2).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.datas[0].high[-2],
                "value": "标题",
            },
        ]

    def get_analysis(self):
        # 组织数据结构
        self.result_data_dict["lines"] = [
            {
                "type": "brokenline",
                "color": self.indicator_params.get("TrendPackconnectionColor", "#00FF00"),
                "data": self.result_data
            },
            {
                "type": "bmp",  # 表示买点
                "arrow": "1",
                "data": self.buy_poit
            },
            {
                "type": "bmp",  # 表示卖点
                "arrow": "2",
                "data": self.sell_poit
            },
            {
                "type": "bmp",  # 表示平仓点
                "arrow": "3",
                "data": self.close_poit
            },
            {
                "type": "text",
                "data": self.title
            },
        ]

        return [self.result_data_dict["lines"], None, None]

