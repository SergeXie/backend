import backtrader as bt


class ResponseEMAData(bt.Strategy):
    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        # print('indicator_params', indicator_params)
        self.period = self.indicator_params.get("Periods", 20)

        self.ema = bt.indicators.EMA(self.data.close, period=self.period)

        self.result_data = []
        self.result_data_dict = dict()


    def next(self):
        current_kline_id = int(self.data.klineId[0])

        # 将数据添加到结果列表
        self.result_data.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price":  self.ema[0],
        })

    def get_analysis(self):
        # 组织数据结构
        self.result_data_dict["lines"] = [
            {
                "type": "line",
                "color": self.indicator_params.get("TrendmidColor", "#00FF00"),
                "data": self.result_data
            },

        ]

        return [self.result_data_dict["lines"],
                None,None]  # 结束时间
