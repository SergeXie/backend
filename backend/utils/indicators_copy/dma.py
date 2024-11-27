import backtrader as bt
import numpy as np

class ResponseDMAData(bt.Strategy):
    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.dma = bt.indicators.DicksonMovingAverage(self.data.close,
                                                      gainlimit=self.indicator_params.get("Gainlimit", 50),
                                                      hperiod=self.indicator_params.get("Hperiod", 7))
        self.result_data = []
        self.result_data_dict = dict()
        self.buy_poit = []
        self.sell_poit = []
        self.close_poit = []

    def next(self):
        current_kline_id = int(self.data.klineId[0])
        # # 将数据添加到结果列表
        self.result_data.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": self.dma[0] if not np.isnan(self.dma[0]) else None,
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