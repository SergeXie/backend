import backtrader as bt


class ResponseCCIData(bt.Strategy):
    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.cci = bt.indicators.CCI(self.data,
                                     period=self.indicator_params.get("Periods", 20),
                                     factor=self.indicator_params.get("Multiplier", 0.015),
                                     upperband=self.indicator_params.get("Upperband", 100.0),
                                     lowerband=self.indicator_params.get("Uowerband", -100.0),
                                     )

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
            "price": self.cci[0],
        })

    def get_analysis(self):
        # 组织数据结构
        self.result_data_dict["lines"] = [
            {
                "type": "line",
                "color": self.indicator_params.get("TrenCCIColor", "#FF0000"),
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
                self.datas[0].datetime.datetime(
                    self.indicator_params.get("Periods", 10) - self.data.buflen() + 1).strftime(
                    '%Y-%m-%d %H:%M:%S'),  # 开始时间
                self.datas[0].datetime.datetime(0).strftime(
                    '%Y-%m-%d %H:%M:%S')]  # 结束时间
