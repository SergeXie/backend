import datetime

from core.bt.indicators import ATRStopLoss
from core.bt.tools.wm_pattern_recognizer import WMPatternRecognizer
from core.bt.indicators import IndicatorDataProcessor
from core.bt.base.public_strategy import CommonStrategy


class PCTradingStrategy(CommonStrategy):
    params = dict(inp_depth=12)

    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        # 接收参数变量
        self.indicator_params = indicator_params
        # ========== 1. 初始化 ATR 趋势指标 ==========
        # 初始化趋势止损指标
        self.atr_stoploss = ATRStopLoss(self.data,
                                        atr_len=self.indicator_params.get("period", 10),
                                        multiplier=self.indicator_params.get("Multiplier", 3.0))

        # ========== 2. 初始化 峰值连线 ==========
        # 调用WM形态
        self.data_processor = IndicatorDataProcessor(self.data, indicator_params)
        self.pattern_recognizer = WMPatternRecognizer()
        self.zigzag = []

        # self.zigzag_calculator = ZigZagCalculator(inp_depth=self.p.inp_depth)

        # self.last_pattern_ts = None

        # ========== 3. 控制变量 ==========
        self.last_from = ''
        self.sum_po = 0


        self.data_line_count = 0
        self.prev_trend = 0
        self.dataspread = self.datas[0].spread
        self.start_date = datetime.datetime.strptime(begin_time, '%Y-%m-%d %H:%M:%S')
        self.baseLots = baseLots
        self.entry_price = None
        self.entry_atr = None
        self.four_price = None
        self.current_trade = None  # 当前持仓信息
        self.handled_patterns = set()  # 已处理形态标识
        self.open_price = None  # 记录开仓价
        self.open_type = None  # "long" or "short"
        self.open_time_close = None
        self.four_to_three_price = None
        self.con1 = False
        self.trend_map = {}  # 时间戳 -> trend_change 值
        self.last_trend = 0
        self.ProfitRatio = self.indicator_params.get("ProfitRatio", 1.0)

        self.price_diff = 2

    def next(self):
        self.data_line_count += 1
        super().calculate_values()

        if self.datas[0].datetime.datetime(0) <= self.start_date:
            return

        #  === 当前 K线时间 ===
        current_dt = self.data.datetime.datetime(0)
        close = self.data.close[0]
        open_ = self.data.open[0]

        # 进场点减去第四个点

        # 当前趋势
        trend = self.atr_stoploss.lines.trend_change[0]
        # 记录当前K线的趋势
        self.trend_map[current_dt.strftime('%Y-%m-%d %H:%M:%S')] = trend
        # 市场的平均波动范围  如果 ATR = 10，说明当前市场每根K线大概有 10 点左右的波动
        atr = self.atr_stoploss.lines.ATR[0]

        # ========== 更新 ZigZag 点 ==========
        result_data, result_data_original, po_high, po_low = self.data_processor.process_next_data()
        # print(current_dt,  po_high, po_low)
        # print(result_data) if len(result_data) > 0 else None
        # self.result_data.extend(result_data)  # 原点
        # self.result_data_original.extend(result_data_original)  # 偏点
        # self.po_high.extend(po_high)  # 破高
        # self.po_low.extend(po_low)  # 破低

        if len(result_data) != 0:
            if self.last_from == 'po_high' or self.last_from == 'po_low':
                self.zigzag.pop(-1)
            self.zigzag.append(result_data[0])
            self.last_from = 'result_data'
        if len(po_high) != 0:
            if self.last_from == 'po_high':
                self.zigzag.pop(-1)
            self.zigzag.append(po_high[0])
            self.last_from = 'po_high'
        if len(po_low) != 0:
            if self.last_from == 'po_low':
                self.zigzag.pop(-1)
            self.zigzag.append(po_low[0])
            self.last_from = 'po_low'
        # print(self.zigzag)
        # self.pattern_recognizer.analyze_zigzag_points(self.zigzag)
        # pattern_titles = self.pattern_recognizer.get_pattern_titles()
        dict_index2ts, dict_ts2index = self.data_processor.get_index_timestamp_maps()
        self.pattern_recognizer.analyze_zigzag_points(self.zigzag, dict_index2ts, dict_ts2index)
        pattern_titles = self.pattern_recognizer.get_pattern_titles()
        # print(pattern_titles)



        if not pattern_titles:
            return

        # ========== 平仓判断 ==========
        if self.position:
            if self.open_type == "long":  # W形态
                # 趋势反转 or
                # self.entry_price：开仓时记录下的价格；
                # close：是当前这根K线的收盘价（现价）
                # self.four_price 第四个点价格
                # 当前价格 - 开仓价格 = 当前浮动盈亏 >= 开仓价上涨超过 1 倍 ATR
                # 且当前这根K线是阴线（close < open_），市场开始转弱，有反转可能  先平仓
                # close < open_ 阴线
                con1 = self.data.high[0] - self.open_time_close > self.four_to_three_price * self.ProfitRatio  # 一倍价差
                self.con1 = self.con1 or con1

                con2 = trend != self.last_trend and trend == -1  # 趋势反转

                con3 = open_ > close  # 阴线

                # con4 = self.data.high[0] - self.open_time_close > (2 * self.four_to_three_price)  # 两倍价差

                stop = (atr - self.price_diff) if trend == 1 else close - 1
                con5 = close < stop  # 止损

                if con1 or con2 or con5:
                    print(f"[平多] {current_dt} {con1} {con2} {con5}")
                    self.close()
                    self.con1 = False
                    self.open_type = None
                    self.open_time_close = None
                    self.four_to_three_price = None
            elif self.open_type == "short":  # M形态
                # 趋势反转 or 前浮动盈亏 >= 距离开仓价上涨超过 1 倍 ATR（达到预期利润区间）
                # self.four_price 第四个点价格
                # close > open_ 代表当前是阳线，市场可能要反弹了 → 先平掉。
                con1 = self.open_time_close - self.data.low[0] > self.four_to_three_price * self.ProfitRatio  # 一倍价差
                self.con1 = self.con1 or con1
                con2 = trend != self.last_trend and trend == 1  # 趋势反转
                con3 = open_ < close  # 阳线
                con4 = self.open_time_close - self.data.low[0] > (2 * self.four_to_three_price)  # 两倍价差
                stop = (atr + self.price_diff) if trend == -1 else close + 1
                con5 = close > stop  # 止损

                # if (self.con1 and con3) or con2 or con4 or con5:
                if con1 or con2 or con5:
                    print(f"[平空] {current_dt} {con1} {con2} {con5}")
                    self.close()
                    self.con1 = False
                    self.open_type = None
                    self.open_time_close = None
                    self.four_to_three_price = None

        self.last_trend = trend

        # ========== 开仓判断 ==========
        if not self.position:
            for pattern in pattern_titles:
                key = (pattern["end"], pattern["value"])
                if key in self.handled_patterns:
                    continue

                # 当前 K线是否是这个形态的 end 点
                if pattern["end"] == current_dt.strftime('%Y-%m-%d %H:%M:%S'):

                    # 在这里获取 start_two 时刻的趋势值
                    trend_at_start_two = self.trend_map.get(pattern["start_two"])

                    if pattern["value"] == "M形态" and trend_at_start_two == 1:
                        # print(f"[做空] M形态：开空仓 @ {current_dt} 第二个点的趋势：{trend_at_start_two}")
                        self.order = self.sell(size=self.baseLots)
                        self.open_time_close = close
                        self.four_to_three_price = abs(pattern["four_price"] - pattern["price"])
                        self.four_price = pattern["four_price"]
                        self.open_type = "short"

                    elif pattern["value"] == "W形态" and trend_at_start_two == -1:
                        # print(f"[做多] W形态：开多仓 @ {current_dt} 第二个点的趋势：{trend_at_start_two}")
                        self.order = self.buy(size=self.baseLots)
                        self.open_time_close = close
                        self.four_to_three_price = abs(pattern["four_price"] - pattern["price"])
                        self.four_price = pattern["four_price"]
                        self.open_type = "long"

                    self.handled_patterns.add(key)
                    break




# 形态关键点位
# pattern_titles: [
#     {'kLineId': 9901375.0, 'timestamp': '2025-07-10 14:00:00', 'price': 3330.19, 'value': 'W形态',
#      'start': '2025-07-08 01:00:00', 'end': '2025-07-11 03:00:00', 'high': 3330.19, 'low': 3282.53},
#
#     {'kLineId': 9958607.0, 'timestamp': '2025-07-14 17:00:00', 'price': 3340.91, 'value': 'M形态',
#      'start': '2025-07-10 17:00:00', 'end': '2025-07-15 16:00:00', 'high': 3374.85, 'low': 3340.91},
#
#     {'kLineId': 10048296.0, 'timestamp': '2025-07-18 05:00:00', 'price': 3344.07, 'value': 'W形态',
#      'start': '2025-07-16 18:00:00', 'end': '2025-07-18 10:00:00', 'high': 3344.07, 'low': 3309.7}]
#


