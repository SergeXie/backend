import backtrader as bt
import numpy as np


class ResponseMAMovingAverageIndicator(bt.Strategy):

    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments

        # 定义移动平均线指标
        # 初始化指标
        # Source通过索引来找 ["Close","Open","High","Low"]
        # 简单移动平均线  指数移动平均线  平滑移动平均线 线性加权移动平均线
        # Method 通过索 引来找 ["Simple","Exponential","Smoothed","Linear Weighted"]
        self.options_price = {0: self.data.close, 1: self.data.open, 2: self.data.high, 3: self.data.low}

        self.method_price = {0: bt.indicators.SimpleMovingAverage, 1: bt.indicators.ExponentialMovingAverage,
                             2: bt.indicators.SmoothedMovingAverage, 3: bt.indicators.WeightedMovingAverage}

        # 获取 Source 和 Method 参数，如果没有传递则使用默认值
        source_index = int(self.indicator_params.get("Source", 0))
        method_index = int(self.indicator_params.get("Method", 0))
        period = self.indicator_params.get("Periods", 20)

        # 初始化选定的移动平均线
        self.ma = self.method_price[method_index](self.options_price[source_index], period=period)

        self.result_data = []
        self.result_data_dict = dict()

        self.buy_poit = []
        self.sell_poit = []
        self.close_poit = []

    def next(self):
        current_kline_id = int(self.data.klineId[0])
        # 将数据添加到结果列表
        self.result_data.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": self.ma[0] if not np.isnan(self.ma[0]) else None,
        })

    def get_analysis(self):
        # 组织数据结构
        self.result_data_dict["lines"] = [
            {
                "type": "line",
                "color": self.indicator_params.get("TrendDMAColor", "#FF0000"),
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
                "data": ''
            },
        ]

        return [self.result_data_dict["lines"],
                self.result_data[0].get('timestamp'),  # 开始时间
                self.result_data[-1].get('timestamp')]  # 结束时间