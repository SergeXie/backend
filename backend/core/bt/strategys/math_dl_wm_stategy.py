from core.bt.indicators import ATRStopLoss
from core.bt.base.public_strategy import CommonStrategy
import pickle
import numpy as np

from core.bt.indicators.wm_predict_bymath import klines_to_dataframe, merge_klines, get_klines_in_range, \
    convert_to_weight, probability
from core.bt.tools.zigzag_calculator import ZigZagCalculator
from core.bt.tools.wm_pattern_recognizer import WMPatternRecognizer
from core.ai.dtw import calc_dtw_distance
import warnings
from sklearn.exceptions import UndefinedMetricWarning

# 过滤特定警告
warnings.filterwarnings('ignore', category=UndefinedMetricWarning)


class WMTradingStrategy(CommonStrategy):
    # 定义参数
    params = (
        ('inp_depth', 12),
    )

    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        # 接收参数变量
        self.indicator_params = indicator_params
        self.baseLots = baseLots


        self.result_data_dict = dict()
        self.Id_TS_dict = {}

        self.BarState = []
        self.BarStateText = []
        self.W_sum = 0
        self.M_sum = 0
        self.all_kline_data = []
        self.Ts_to_hloc = {}

        self.last_all_5point = None

        self.last_maybe_m = []
        self.last_maybe_w = []
        self.len_last_maybe_m = 0
        self.len_last_maybe_w = 0
        self.close_price = None
        self.stop_price = None

        #----------
        # 参数 # 0为指标,1为模型
        self.wm_from = self.indicator_params.get('WMfrom', 0)
        self.pre_from = self.indicator_params.get('Prefrom', 1)
        #---------
        # 实例化独立的算法类
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.p.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer()

        # 确保数据长度足够时再开始计算
        self.addminperiod(self.p.inp_depth)
        self.atr_stoploss = ATRStopLoss(self.data,
                                        atr_len=self.indicator_params.get("period", 10),
                                        multiplier=self.indicator_params.get("Multiplier", 3.0))

        # ---------
        with open('./dataset/all_wm_pattern_kline.pkl', 'rb') as file:
            self.all_wm_pattern = pickle.load(file)
        with open('./dataset/all_no_pattern_kline.pkl', 'rb') as file:
            self.all_none_pattern = pickle.load(file)

        self.all_save_pattern = self.all_wm_pattern + self.all_none_pattern[:len(self.all_wm_pattern)]  # 保存的全部形态数据

        self.all_wm_pattern_kline = [klines_to_dataframe(merge_klines(i['target_klines'])) for i in self.all_wm_pattern]


    def next(self):
        self.Id_TS_dict[int(self.data.klineId[0])] = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')
        # 确保数据长度足够
        if len(self) < self.p.inp_depth:
            return

        # 准备当前K线数据，传递给ZigZagCalculator
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
        self.Ts_to_hloc[self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')] = [self.data.high[0],
                                                 self.data.low[0],
                                                 self.data.open[0],
                                                 self.data.close[0]]

        # 调用ZigZag算法类的处理方法
        # process_kline会返回是否产生了新的zigzag点，如果产生，就通知形态识别器
        new_zigzag_point_or_updated = self.zigzag_calculator.process_kline(current_kline_data)

        digit = int(self.datas[0].digits[0])
        # if not new_zigzag_point_or_updated:
        #     return
        zigzag_points = self.zigzag_calculator.get_zigzag_points()
        self.pattern_recognizer.analyze_zigzag_points(zigzag_points)


        self.wm_from = 0
        self.pre_from = 0

        #  ----------------------------------------这里先预测是否是形态--------------------------------
        buy_Signal = 0
        sell_Signal = 0
        trend = self.atr_stoploss.lines.trend_change[0]

        #  ----------------------------------------这里先预测是否是形态--------------------------------
        maybe_m = self.pattern_recognizer.get_maybe_m_patterns()
        maybe_w = self.pattern_recognizer.get_maybe_w_patterns()

        if len(maybe_m) != len(self.last_maybe_m):
            sell_Signal = 1
        if len(maybe_w) != len(self.last_maybe_w):
            buy_Signal = 1

        self.last_maybe_w = maybe_w.copy()
        self.last_maybe_m = maybe_m.copy()

        # print(len(self.data))

        # _______________计算相似度____________________
        # -----------获取最后一个可能的m，用于计算概率----------------
        if len(maybe_m)>0 and sell_Signal == 1:
            maybe_m = self.pattern_recognizer.get_maybe_m_patterns()[-1]
            last_m_start = maybe_m['start']
            last_m_end = maybe_m['end']
            last_m_kline = get_klines_in_range(self.all_kline_data, last_m_start, last_m_end)
            last_m_kline_df = klines_to_dataframe(merge_klines(last_m_kline))
            # print(last_m_kline_df)
            # print(calc_dtw_distance(last_m_kline_df, last_m_kline_df))
            distance = [calc_dtw_distance(last_m_kline_df, i) for i in self.all_wm_pattern_kline]
            weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
            m_zigzag_points = [i['points'] for i in self.all_wm_pattern if "M" in i['pattern_type']]
            weight = [weight[index] for index, i in enumerate(self.all_wm_pattern) if "M" in i['pattern_type']]
            p = probability(m_zigzag_points, datafrom='m', weight=weight)
            # print("m概率:",trend, p)
            price_diff = self.Ts_to_hloc.get(maybe_m['start_third'])[1] - self.Ts_to_hloc.get(maybe_m['start_four'])[0]  # 高点到低点的价差

            max_value = np.max(p['probabilities'])  # 获取最大值
            max_index = np.argmax(p['probabilities'])
            price_list = []
            for index, i in enumerate(p['probabilities']):
                base_price = self.Ts_to_hloc.get(maybe_m['start_third'])[1]
                price = base_price + price_diff * index
                price = np.round(price, digit)
                price_list.append(price)
            # print(price_list, max_value, max_index)
            if max_value > 0.6:
                sell_Signal = 1
                close_price = price_list[max_index]
            else:
                sell_Signal = 0

        # -----------获取最后一个可能的w，用于计算概率----------------
        if len(maybe_w)>0 and buy_Signal == 1:
            maybe_w = self.pattern_recognizer.get_maybe_w_patterns()[-1]
            last_w_start = maybe_w['start']
            last_w_end = maybe_w['end']
            last_w_kline = get_klines_in_range(self.all_kline_data, last_w_start, last_w_end)
            last_w_kline_df = klines_to_dataframe(merge_klines(last_w_kline))
            distance = [calc_dtw_distance(last_w_kline_df, i) for i in self.all_wm_pattern_kline]
            weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
            w_zigzag_points = [i['points'] for i in self.all_wm_pattern if "W" in i['pattern_type']]
            weight = [weight[index] for index, i in enumerate(self.all_wm_pattern) if "W" in i['pattern_type']]
            p = probability(w_zigzag_points, datafrom='w', weight=weight)
            # print("w概率:",trend, p)
            price_diff = self.Ts_to_hloc.get(maybe_w['start_third'])[0] - self.Ts_to_hloc.get(maybe_w['start_four'])[1]  # 高点到低点的价差
            max_value = np.max(p['probabilities'])  # 获取最大值
            max_index = np.argmax(p['probabilities'])
            price_list = []
            for index, i in enumerate(p['probabilities']):
                base_price = self.Ts_to_hloc.get(maybe_w['start_third'])[0]
                price = base_price + price_diff * index
                price = np.round(price, digit)
                price_list.append(price)
            # print(price_list, max_value, max_index)
            if max_value > 0.6:
                buy_Signal = 1
                close_price = price_list[max_index]
            else:
                buy_Signal = 0


        close = self.data.close[0]
        target_dn = self.atr_stoploss.lines.target_dn[0]
        target_up = self.atr_stoploss.lines.target_up[0]
        # ========== 平仓判断 ==========
        if self.position and self.close_price is not None:
            # print(close, target_dn, target_up, trend)
            if self.position.size > 0 and (close>self.close_price or close < target_up):
                print('buy_close',close>self.close_price , close > target_up, target_up, self.data.datetime.datetime(0))
                self.order = self.close()
                self.close_price = None
                self.stop_price = None
                print('############################')
            if self.position.size < 0 and (close<self.close_price or close < target_dn):
                print('sell_close',close<self.close_price , close < target_dn, target_dn, self.data.datetime.datetime(0))
                self.order = self.close()
                self.close_price = None
                self.stop_price = None
                print('############################')
        # ========== 开仓判断 ==========
        if not self.position:
            if buy_Signal == 1 and trend == -1:
                print('buy','止盈:', close_price, self.data.datetime.datetime(0),close)
                self.order = self.buy(size=self.baseLots)
                self.close_price = close_price

            if sell_Signal == 1 and trend == 1:
                print('sell','止盈:', close_price, self.data.datetime.datetime(0),close)
                self.order = self.sell(size=self.baseLots)
                self.close_price = close_price






