import datetime

from utils.indicators.indicators_common import ATRStopLoss
import backtrader as bt
import numpy as np


class ResponseATRStopLossData(bt.Strategy):
    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments, begin_time=None):
        self.digits = int(self.data.digits[0])
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data_up = []
        self.result_data_dn = []
        self.result_num = []
        self.result_data_dict = dict()
        self.i = 0
        self.data_line_count = 0
        self.buy_poit = []
        self.sell_poit = []
        self.close_poit = []

        self.atr_stoploss = ATRStopLoss(self.data,
                                        atr_len=self.indicator_params.get("Periods", 10),
                                        multiplier=self.indicator_params.get("Multiplier", 3.0))

        if begin_time:
            self.start_date = datetime.datetime.strptime(begin_time, '%Y-%m-%d %H:%M:%S')  # 设置开始日期
        else:
            self.start_date = None

    def next(self):

        self.i += 1
        current_kline_id = int(self.data.klineId[0])
        # 趋势反转变化
        trend_change = self.atr_stoploss.lines.trend_change[0]

        if self.start_date:
            #  小于起始时间的不计算指标
            if self.datas[0].datetime.datetime(0) <= self.start_date:
                # print("datetime:{}".format(self.datas[0].datetime.datetime(0)))
                return

        # 检查是否有持仓
        if not self.position:
            if trend_change == 1:
                self.buy_poit.append({
                    "kLineId": current_kline_id,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.data.high[0]})
            elif trend_change == -1:
                self.sell_poit.append({
                    "kLineId": current_kline_id,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.data.low[0]})
        else:
            if self.atr_stoploss.lines.trend_change[0] != self.atr_stoploss.lines.trend_change[-1]:
                if trend_change == -1 and self.position.size > 0:
                    self.close_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.high[0]})

                elif trend_change == 1 and self.position.size < 0:
                    self.close_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.high[0]})

        self.i += 1
        current_kline_id = int(self.data.klineId[0])
        target_up_value = self.atr_stoploss.lines.target_up[0]
        target_dn_value = self.atr_stoploss.lines.target_dn[0]
        timestamp = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')
        # 检查并替换 NaN 值为 None
        if np.isnan(target_up_value):
            target_up_value = None
        if np.isnan(target_dn_value):
            target_dn_value = None

        # 将数据添加到结果列表
        self.result_data_up.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": round(target_up_value, self.digits) if target_up_value else None,
        })

        self.result_data_dn.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": round(target_dn_value, self.digits) if target_dn_value else None,
        })

    def get_analysis(self):
        # 组织数据结构
        self.result_data_dict["lines"] = [
            {
                "type": "line",
                "color": self.indicator_params.get("TrendUpColor", "#00FF00"),
                "data": self.result_data_up

            },
            {
                "type": "line",
                "color": self.indicator_params.get("TrenDownColor", "#FF0000"),
                "data": self.result_data_dn
            },
        ]

        return [self.result_data_dict["lines"],
                self.datas[0].datetime.datetime(
                    self.indicator_params.get("Periods", 10) - self.data.buflen() + 1).strftime(
                    '%Y-%m-%d %H:%M:%S'),  # 开始时间
                self.datas[0].datetime.datetime(0).strftime(
                    '%Y-%m-%d %H:%M:%S')]  # 结束时间
