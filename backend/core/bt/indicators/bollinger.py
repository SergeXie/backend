import backtrader as bt


class ResponseBollingerData(bt.Strategy):
    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        # print('indicator_params', indicator_params)
        self.period = self.indicator_params.get("Periods", 20)
        self.devfactor = self.indicator_params.get("devfactor", 2.0)
        self.bollinger = bt.indicators.BollingerBands(self.data.close, period=self.period, devfactor=self.devfactor)

        self.mid = self.bollinger.mid
        self.top = self.bollinger.top
        self.bot = self.bollinger.bot

        self.result_data = []
        self.result_data_dict = dict()

        self.result_data_mid = []
        self.result_data_top = []
        self.result_data_bot = []
        print('ok')

    def next(self):
        current_kline_id = int(self.data.klineId[0])

        # 将数据添加到结果列表
        self.result_data_mid.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price":  self.mid[0],
        })
        self.result_data_top.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price":  self.top[0],
        })
        self.result_data_bot.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": self.bot[0],
        })

    def get_analysis(self):
        # 组织数据结构
        self.result_data_dict["lines"] = [
            {
                "type": "line",
                "color": self.indicator_params.get("TrendmidColor", "#00FF00"),
                "data": self.result_data_mid
            },
            {
                "type": "line",
                "color": self.indicator_params.get("TrendtopColor", "#FF0000"),
                "data": self.result_data_top
            },
            {
                "type": "line",
                "color": self.indicator_params.get("TrendbotColor", "#FF0000"),
                "data": self.result_data_bot
            },

        ]

        return [self.result_data_dict["lines"],
                None,None]  # 结束时间
