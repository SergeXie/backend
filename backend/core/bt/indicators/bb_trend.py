import pandas as pd
import backtrader as bt
import numpy as np


class ResponseBBTrendData(bt.Strategy):
    lines = ('bar_o', 'bar_h', 'bar_l', 'bar_c',
             'tr_tmp', 'up', 'dn', 'trend_change')
    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments, begin_time=None):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        # print('indicator_params', indicator_params)
        self.shortLengthInput = self.indicator_params.get("shortLengthInput", 20)
        self.longLengthInput = self.indicator_params.get("longLengthInput ", 50)
        self.devfactor = self.indicator_params.get("devfactor", 2.0)
        self.longbollinger = bt.indicators.BollingerBands(self.data.close, period=self.longLengthInput, devfactor=self.devfactor)
        self.shortbollinger = bt.indicators.BollingerBands(self.data.close, period=self.shortLengthInput, devfactor=self.devfactor)

        shortMiddle = self.shortbollinger.mid
        shortUpper = self.shortbollinger.top
        shortLower = self.shortbollinger.bot

        longMiddle = self.longbollinger.mid
        longUpper = self.longbollinger.top
        longLower = self.longbollinger.bot

        self.BBTrend = (abs(shortLower - longLower) - abs(shortUpper - longUpper)) / shortMiddle * 100

        self.result_data = []
        self.result_data_dict = dict()

        self.zeroline = []
        self.trline = []
        self.upline = []
        self.dnline = []

        self.dir = 1
        self.st = 0

    def next(self):
        if len(self) < self.indicator_params.get("longLengthInput ", 50):
            return
        current_kline_id = int(self.data.klineId[0])
        # 将数据添加到结果列表
        self.result_data.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price":  self.BBTrend[0],
        })
        self.zeroline.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price":  0,
        })

        self.lines.bar_o[0] = self.BBTrend[-1]
        self.lines.bar_h[0] = max(self.BBTrend[0], self.BBTrend[-1])
        self.lines.bar_l[0] = min(self.BBTrend[0], self.BBTrend[-1])
        self.lines.bar_c[0] = self.BBTrend[0]

        if np.isnan(self.lines.bar_h[-1]):
            self.lines.tr_tmp[0] = self.lines.bar_h[0] - self.lines.bar_l[0]
        else:
            self.lines.tr_tmp[0] = max(
                max(self.lines.bar_h[0]-self.lines.bar_l[0], abs(self.lines.bar_h[0]-self.lines.bar_c[-1])),
                abs(self.lines.bar_l[0] - self.lines.bar_c[-1]))

        atr = pine_rma(self.lines.tr_tmp, self.indicator_params.get("Length ", 10))
        # print(len(self), tr[-1])
        if not np.isnan(atr[-1]):
            # print(tr.iloc[-1], len(self))
            self.trline.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": atr[-1],
            })
            mlt = self.indicator_params.get("Factor ", 7)
            b_hl2 = (self.lines.bar_h[0] + self.lines.bar_l[0])/2
            self.lines.up[0] = b_hl2 + mlt * atr[-1]
            self.lines.dn[0] = b_hl2 - mlt * atr[-1]


            if not np.isnan(self.lines.up[-1]):
                if self.lines.up[0] < self.lines.up[-1] or self.lines.bar_c[-1] > self.lines.up[-1]:
                    pass
                else:
                    self.lines.up[0] = self.lines.up[-1]
            if not np.isnan(self.lines.dn[-1]):
                if self.lines.dn[0] > self.lines.dn[-1] or self.lines.bar_c[-1] < self.lines.dn[-1]:
                    pass
                else:
                    self.lines.dn[0] = self.lines.dn[-1]

            # print(self.lines.up[0])

            # self.upline.append({
            #     "kLineId": current_kline_id,
            #     "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            #     "price": self.lines.up[0],
            # })
            # self.dnline.append({
            #     "kLineId": current_kline_id,
            #     "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            #     "price": self.lines.dn[0],
            # })

            if self.st == self.lines.up[-1]:
                if self.lines.bar_c[0] > self.lines.up[0]:
                    self.dir = -1
                else:
                    self.dir = 1
            else:
                if self.lines.bar_c[0] < self.lines.dn[0]:
                    self.dir = 1
                else:
                    self.dir = -1

            self.st = self.lines.dn[0] if self.dir == -1 else self.lines.up[0]
            # print(self.dir)

            self.upline.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.lines.up[0] if self.dir == 1 else None,
            })
            self.dnline.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.lines.dn[0] if self.dir == -1 else None,
            })

            self.lines.trend_change[0] = self.dir


    def stop(self):

        # print(np.isnan(self.lines.bar_h[-999]), self.lines.bar_h[-999])
        # print(self.lines.bar_c.array)
        pass

    def get_analysis(self):
        # 组织数据结构
        self.result_data_dict["lines"] = [
            # {
            #     "type": "line",
            #     "color": self.indicator_params.get("TrendmidColor", "#00FF00"),
            #     "data": self.result_data
            # },
            {
                "type": "line",
                "color": self.indicator_params.get("TrendmidColor", "#00FFFF"),
                "data": self.zeroline
            },
            # {
            #     "type": "line",
            #     "color": self.indicator_params.get("TrendmidColor", "#00FF00"),
            #     "data": self.trline
            # },
            {
                "type": "line",
                "color": self.indicator_params.get("TrendmidColor", "#00FF00"),
                "data": self.upline
            },
            {
                "type": "line",
                "color": self.indicator_params.get("TrendmidColor", "#FF0000"),
                "data": self.dnline
            },

        ]



        return [self.result_data_dict["lines"],
                None,None]  # 结束时间


# def pine_rma(src, length):
#     src = pd.Series(src.array)
#     # print(src)
#     alpha = 1 / length
#     rma_series = src.ewm(alpha=alpha, adjust=False).mean()
#     return rma_series

def pine_rma(src, length):
    src = pd.Series(src.array)
    alpha = 1 / length
    sum_values = [0.0]  # Renamed variable to avoid shadowing the built-in sum function

    def na(value):
        return value is None or (isinstance(value, float) and value != value)

    def nz(value):
        return value if not na(value) else 0

    def ta_sma(values, length):
        if len(values) < length:
            return None
        return sum(values[-length:]) / length  # Using the built-in sum function here

    rma_values = []
    for i, value in enumerate(src):
        if na(sum_values[-1]):
            sum_values.append(ta_sma(src.iloc[:i + 1].tolist(), length))
        else:
            sum_values.append(alpha * value + (1 - alpha) * nz(sum_values[-1]))
        rma_values.append(sum_values[-1])

    return rma_values
