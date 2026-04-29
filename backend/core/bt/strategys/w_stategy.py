import copy
import pickle

from core.ai.dtw import calc_dtw_distance
from core.bt.indicators.wm_predict_bymath import klines_to_dataframe, merge_klines, get_klines_in_range, \
    convert_to_weight, probability
from core.bt.tools.zigzag_calculator import ZigZagCalculator
from core.bt.base.public_strategy import CommonStrategy
from core.bt.indicators import *


class WMTradingStrategy(CommonStrategy):
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
        self.probability = self.indicator_params.get("p_value", 10)

        # ========== 2. 初始化 WM 形态相关 ==========
        # 调用WM形态
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.p.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer()
        self.last_pattern_ts = None

        # ========== 3. 控制变量 ==========
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
        self.last_pattern_titles = None
        self.two_price = None
        self.stop_price1 = None
        self.all_kline_data = []

        # ========== 4. 参数 ==========
        self.price_diff = 0

        # ============================
        # 读取全部形态
        with open('./dataset/all_wm_pattern_kline.pkl', 'rb') as file:
            self.all_wm_pattern = pickle.load(file)
        self.all_wm_pattern_kline = [klines_to_dataframe(merge_klines(i['target_klines'])) for i in self.all_wm_pattern]

        print('是我了',len(self.all_wm_pattern_kline))



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
        current_kline = {
            "kLineId": len(self),
            "timestamp": current_dt.strftime('%Y-%m-%d %H:%M:%S'),
            "open": open_,
            "high": self.data.high[0],
            "low": self.data.low[0],
            "close": close,
            "volume": self.data.volume[0],
        }

        current_kline_data = {
            "kLineId": self.data.klineId[0],  # 假设datafeed提供了klineId
            "timestamp": self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "open": self.data.open[0],
            "high": self.data.high[0],
            "low": self.data.low[0],
            "close": self.data.close[0],
            "volume": self.data.volume[0],
        }
        self.all_kline_data.append(current_kline_data)

        updated = self.zigzag_calculator.process_kline(current_kline)

        zigzag_pts = self.zigzag_calculator.get_zigzag_points()
        # print(len(zigzag_pts))
        index2ts, ts2index = self.zigzag_calculator.get_index_timestamp_maps()
        self.pattern_recognizer.analyze_zigzag_points(zigzag_pts, index2ts, ts2index)

        # pattern_titles = self.pattern_recognizer.get_pattern_titles()

        # 可能构成wm的点
        pattern_titles = self.pattern_recognizer.get_maybe_detected_patterns()

        if len(pattern_titles) == 0:
            return
        # print(current_dt, len(pattern_titles), pattern_titles[-1]['end'])
        # print('还是这里',pattern_titles)

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
                con1 = self.data.high[0] - self.open_time_close > self.four_to_three_price  # 一倍价差
                self.con1 = self.con1 or con1
                con2 = trend != self.last_trend and trend == -1 # 趋势反转
                con3 = open_ > close  # 阴线
                con4 = self.data.high[0] - self.open_time_close > (2 * self.four_to_three_price)  # 两倍价差

                stop = self.two_price if trend == -1 else (atr - self.price_diff)
                con5 = close < stop  # 止损

                con6 = close > self.stop_price1 # 止盈

                if con5 or con6:
                    # print(f"[平多] {current_dt}", (self.con1 and con3), con2, con4, con5)
                    self.close()
                    self.con1 = False
                    self.open_type = None
                    self.open_time_close = None
                    self.four_to_three_price = None
                    self.stop_price1 = None


        self.last_trend = trend

        # ========== 开仓判断 ==========
        if not self.position and self.last_pattern_titles != pattern_titles:
            pattern = pattern_titles[-1]

            # print('这里',pattern)
            # 当前 K线是否是这个形态的 end 点
            if pattern["end"] == current_dt.strftime('%Y-%m-%d %H:%M:%S'):
                # 获取最后一个形态的k线
                last_mw_kline = get_klines_in_range(self.all_kline_data, pattern['start'], pattern['end'])
                last_mw_kline_df = klines_to_dataframe(merge_klines(last_mw_kline))
                # 计算相似度
                distance = [calc_dtw_distance(last_mw_kline_df, i) for i in self.all_wm_pattern_kline]
                weight = convert_to_weight(distance)  # 相似度转为权重

                # w的权重
                w_zigzag_points = [i['points'] for i in self.all_wm_pattern if "W" in i['pattern_type']]
                w_weight = [weight[index] for index, i in enumerate(self.all_wm_pattern) if "W" in i['pattern_type']]
                w_p = probability(w_zigzag_points, datafrom='w', weight=w_weight)
                w_max_val = max(w_p['probabilities'])
                w_max_idx = w_p['probabilities'].index(w_max_val)
                print("w概率:", w_p, w_max_val, w_max_idx)

                # 在这里获取 start_two 时刻的趋势值
                trend_at_start_two = self.trend_map.get(pattern["start_two"])

                if "W" in pattern["value"] and trend_at_start_two == -1 and w_max_val>self.probability:
                    print(f"[做多] W形态：开多仓 @ {current_dt} 第二个点的趋势：{trend_at_start_two}")
                    self.order = self.buy(size=self.baseLots)
                    self.open_time_close = close
                    self.four_to_three_price = abs(pattern["four_price"] - pattern["price"])
                    self.stop_price1 = close + self.four_to_three_price * (w_max_val + 1)  # 预测能到的最大值
                    self.four_price = pattern["four_price"]
                    self.open_type = "long"
                    self.two_price = pattern["two_price"]


        self.last_pattern_titles = copy.copy(pattern_titles)



