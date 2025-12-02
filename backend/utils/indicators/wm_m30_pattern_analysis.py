import backtrader as bt
import numpy as np
import math
import random
import pandas as pd
from backtrader.feeds import PandasData

from utils.module.wm_pattern_recognizer import WMPatternRecognizer
from utils.module.zigzag_calculator import ZigZagCalculator
from utils.indicators.packconnection import IndicatorDataProcessor
from utils.indicators.packconnection import DataAnalysisOrganizer


# 假设 ZigZagCalculator 和 WMPatternRecognizer 已经在当前文件中定义或已导入

class ResponseWMM30Data(bt.Strategy):
    # 定义参数
    params = (
        ('inp_depth', 12),
    )

    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data_dict = dict()

        # 实例化独立的算法类
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.p.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer()
        # 确保数据长度足够时再开始计算
        self.addminperiod(self.p.inp_depth)

        ##################################################################
        self.data_processor = IndicatorDataProcessor(self.data, indicator_params)
        self.result_data = []
        self.result_data_original = []
        self.po_high = []
        self.po_low = []
        self.title = []
        self.titlepeak = []
        self.titlebottol = []
        self.title_offset = []
        self.titlepeak_offset = []
        self.titlebottol_offset = []
        self.notnallpoint = []
        self.open_list = []
        self.date = []
        self.order = None
        self.trades = []
        self.last_cash = self.broker.get_cash()
        self.last_value = self.broker.getvalue()
        self.data_line_count = 0
        self.trend_change_last = 0
        self.tm = 0
        self.result_data_dict = dict()

        self.m_p2_mid = None
        self.w_p2_mid = None
        self.ts_list = []
        self.h_list = []
        self.l_list = []
        self.o_list = []
        self.c_list = []

        self.m1_list = []
        self.m2_list = []
        self.m3_list = []
        self.w1_list = []
        self.w2_list = []
        self.w3_list = []
        self.all_wm_picture_list = []

        self.zigzag = []
        Z_from = indicator_params.get("Zfrom", 1)
        self.Z_from = 'pc' if Z_from == 0 else 'zig'


    def next(self):
        ts = self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')
        self.ts_list.append(ts)
        self.h_list.append(self.data.high[0])
        self.l_list.append(self.data.low[0])
        self.o_list.append(self.data.open[0])
        self.c_list.append(self.data.close[0])
        if self.Z_from == 'zig':

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

            # 调用ZigZag算法类的处理方法
            # process_kline会返回是否产生了新的zigzag点，如果产生，就通知形态识别器
            new_zigzag_point_or_updated = self.zigzag_calculator.process_kline(current_kline_data)

            # 如果ZigZag有更新，就通知形态识别器进行分析
            if new_zigzag_point_or_updated:
                zigzag_points = self.zigzag_calculator.get_zigzag_points()
                dict_index2ts, dict_ts2index = self.zigzag_calculator.get_index_timestamp_maps()
                self.pattern_recognizer.analyze_zigzag_points(zigzag_points, dict_index2ts, dict_ts2index)





            #################################################################################################
        elif self.Z_from == 'pc':
            result_data, result_data_original, po_high, po_low = self.data_processor.process_next_data()
            # print('这里',po_high)
            self.result_data.extend(result_data)  # 原点
            self.result_data_original.extend(result_data_original)  # 偏点
            self.po_high.extend(po_high)  # 破高
            self.po_low.extend(po_low)  # 破低

            if len(result_data) != 0:
                self.zigzag.append(result_data[0])
                dict_index2ts, dict_ts2index = self.data_processor.get_index_timestamp_maps()
                self.pattern_recognizer.analyze_zigzag_points(self.zigzag, dict_index2ts, dict_ts2index)

    def stop(self):
        (self.notnallpoint,
         self.title, self.titlepeak, self.titlebottol, self.title_offset,
         self.titlepeak_offset, self.titlebottol_offset, offset_index) = self.data_processor.process_stop_data(self.result_data, self.result_data_original)

        m_tmp = self.pattern_recognizer.get_pattern_titles()
        w_tmp = self.pattern_recognizer.get_pattern_titles()
        m_non_standard = self.pattern_recognizer.get_non_standard_m_patterns()
        w_non_standard = self.pattern_recognizer.get_non_standard_w_patterns()

        print("这里@@@@@@@@@@@@", len(m_tmp), len(w_tmp), len(m_non_standard), len(w_non_standard))
        print(len(self.h_list),len(self.l_list),len(self.o_list),len(self.c_list),len(self.ts_list))

        m1_count = []
        m2_count = []
        m3_count = []
        w1_count = []
        w2_count = []
        w3_count = []

        # pattern = m_tmp[-2]
        for pattern in m_tmp:
            if 'M' in pattern['value']:
                multiple = self.get_multiple_m(self.h_list, self.l_list, self.o_list, self.c_list, self.ts_list, pattern)
                # print(multiple)
                if pattern['value'] == 'M2形态':
                    m2_count.append(multiple)
                if pattern['value'] == 'M1形态':
                    m1_count.append(multiple)

        for pattern in w_tmp:
            if 'W' in pattern['value']:
                multiple = self.get_multiple_w(self.h_list, self.l_list, self.o_list, self.c_list, self.ts_list, pattern)
                # print(multiple)
                if pattern['value'] == 'W2形态':
                    w2_count.append(multiple)
                if pattern['value'] == 'W1形态':
                    w1_count.append(multiple)


        for pattern in m_non_standard:
            multiple = self.get_multiple_m(self.h_list, self.l_list, self.o_list, self.c_list, self.ts_list, pattern,sta='special')
            m3_count.append(multiple)
            print(multiple)

        for pattern in w_non_standard:
            multiple = self.get_multiple_w(self.h_list, self.l_list, self.o_list, self.c_list, self.ts_list, pattern,sta='special')
            w3_count.append(multiple)

        print("M1 长度：", len(m1_count), sum(1 for x in m1_count if x > 2), sum(1 for x in m1_count if x > 3))
        print("M2 长度：", len(m2_count), sum(1 for x in m2_count if x > 2), sum(1 for x in m2_count if x > 3))
        print("M3 长度：", len(m3_count), sum(1 for x in m3_count if x > 2), sum(1 for x in m3_count if x > 3))
        print("W1 长度：", len(w1_count), sum(1 for x in w1_count if x > 2), sum(1 for x in w1_count if x > 3))
        print("W2 长度：", len(w2_count), sum(1 for x in w2_count if x > 2), sum(1 for x in w2_count if x > 3))
        print("W3 长度：", len(w3_count), sum(1 for x in w3_count if x > 2), sum(1 for x in w3_count if x > 3))




    def get_analysis(self):
        # # 组织数据结构，从独立的算法类获取数据
        # zigzag_points = self.zigzag_calculator.get_zigzag_points()
        # # 获取索引-时间戳映射，用于格式化M/W形态数据
        if self.Z_from == 'zig':
            dict_index2ts, dict_ts2index = self.zigzag_calculator.get_index_timestamp_maps()
            zigzag_points = self.pattern_recognizer.get_zigzag_points()
        else:
            dict_index2ts, dict_ts2index = self.data_processor.get_index_timestamp_maps()
            zigzag_points = self.pattern_recognizer.get_zigzag_points()

        # print(self.pattern_recognizer.get_zigzag_points())

        # pattern_titles = self.pattern_recognizer.get_pattern_titles()  # 获取原始形态标题列表
        # maybe_pattern_titles = self.pattern_recognizer.get_maybe_detected_patterns()
        show_pattern = self.indicator_params.get("show_mabye_pattern")
        # print(show_pattern)
        if show_pattern == 0:  # 确认形态
            pattern_titles = self.pattern_recognizer.get_pattern_titles()  # 获取原始形态标题列表
        elif show_pattern == 1:
            pattern_titles = self.pattern_recognizer.get_maybe_classification()
        print("这里@@@@@@@@@@@@")
        pattern_titles_non_w = self.pattern_recognizer.get_non_standard_w_patterns()
        pattern_titles_non_m = self.pattern_recognizer.get_non_standard_m_patterns()

        pattern_titles = pattern_titles + pattern_titles_non_w + pattern_titles_non_m

        self.result_data_dict["lines"] = [
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'top',
                "data": pattern_titles
            },
            {
                "type": "picture2",  # 假设'picture'是您自定义的一种绘图类型，用于M/W形态
                "data": self.all_wm_picture_list
            },
            # {
            #     "type": "picture",  # 假设'picture'是您自定义的一种绘图类型，用于M/W形态
            #     "data": formatted_m_w_patterns
            # },
            {
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FFFF"),
                "data": zigzag_points
            },
        ]

        return [self.result_data_dict["lines"], None, None]

    def get_multiple_m(self, h_list, l_list, o_list, c_list, ts_list, pattern, sta=''):
        four_point_ts = pattern['points'][3]['timestamp']
        # print(four_point_ts,'@@@@@@@@@')
        # 基础价差
        base_diff = pattern['points'][3]['kline_data']['price'] - pattern['points'][2]['kline_data']['price']
        # print(pattern['points'][3]['kline_data']['price'] , pattern['points'][2]['kline_data']['price'])

        # 1. 找到目标时间在时间戳列表中的索引
        h1_index = ts_list.index(four_point_ts)

        # 2. 获取基准h1值
        h1 = h_list[h1_index]
        if sta == 'special':
            h1 = max(o_list[h1_index], c_list[h1_index])

        # 3. 向后寻找第一个大于h1的h2值
        h2_index = None
        for i in range(h1_index + 1, len(h_list)):
            if h_list[i] > h1:
                h2_index = i
                break

        # print(h1_index, h2_index)
        # print(ts_list[h1_index], ts_list[h2_index])
        # 4. 找到h1和h2索引之间的l列表最小值
        # 注意：这里是闭区间，包含h1和h2位置的l值
        if h2_index is None:
            h2_index = len(l_list)

        try:
            tmp_slice = l_list[h1_index+1:h2_index + 1]
            min_l = min(tmp_slice)
            min_index_in_slice = tmp_slice.index(min_l) + h1_index

        except:
            min_l = pattern['points'][3]['kline_data']['price']
            min_index_in_slice = h1_index
        # 真实价差
        diff = min_l - pattern['points'][3]['kline_data']['price']
        # print(min_l)

        start_ts = pattern.get('start')
        high_price = pattern.get('leftTop_price')
        if l_list[min_index_in_slice] < pattern.get('rigthBottom_price'):
            end_ts = ts_list[min_index_in_slice]
            low_price = l_list[min_index_in_slice]
        else:
            end_ts = pattern.get('end')
            low_price = pattern.get('rigthBottom_price')
        self.all_wm_picture_list = list_add(self.all_wm_picture_list, pattern, start_ts, end_ts, high_price, low_price)

        return abs(diff/base_diff)

    def get_multiple_w(self, h_list, l_list, o_list, c_list, ts_list, pattern,  sta=''):
        four_point_ts = pattern['points'][3]['timestamp']
        # print(four_point_ts,'@@@@@@@@@')
        # 基础价差
        base_diff = pattern['points'][3]['kline_data']['price'] - pattern['points'][2]['kline_data']['price']
        # print(pattern['points'][3]['kline_data']['price'] , pattern['points'][2]['kline_data']['price'])

        # 1. 找到目标时间在时间戳列表中的索引
        l1_index = ts_list.index(four_point_ts)

        # 2. 获取基准h1值
        l1 = l_list[l1_index]
        if sta == 'special':
            l1 = min(o_list[l1_index], c_list[l1_index])

        # 3. 向后寻找第一个大于h1的h2值
        l2_index = None
        for i in range(l1_index + 1, len(l_list)):
            if l_list[i] < l1:
                l2_index = i
                break

        # print(l1_index, l2_index)
        # print(ts_list[h1_index], ts_list[h2_index])
        # 4. 找到h1和h2索引之间的l列表最小值
        # 注意：这里是闭区间，包含h1和h2位置的l值
        if l2_index is None:
            l2_index = len(l_list)

        try:
            tmp_slice = h_list[l1_index+1:l2_index + 1]
            max_h = max(tmp_slice)
            max_index_in_slice = tmp_slice.index(max_h) + l1_index
        except:
            max_h = pattern['points'][3]['kline_data']['price']
            max_index_in_slice = l1_index
        # 真实价差
        diff = max_h - pattern['points'][3]['kline_data']['price']
        # print(max_h)

        start_ts = pattern.get('start')
        low_price = pattern.get('rigthBottom_price')
        if h_list[max_index_in_slice] < pattern.get('rigthBottom_price'):
            end_ts = ts_list[max_index_in_slice]
            high_price = h_list[max_index_in_slice]
        else:
            end_ts = pattern.get('end')
            high_price = pattern.get('rigthBottom_price')
        self.all_wm_picture_list = list_add(self.all_wm_picture_list, pattern, start_ts, end_ts, high_price, low_price)

        return abs(diff/base_diff)


def list_add(wm_list, pattern, start_ts, end_ts, high_price, low_price):
    my_list = wm_list.copy()
    my_list.append({
        "truetime": [start_ts, end_ts],
        "time": [start_ts, end_ts],
        "list": [{
            "leftTop": {
                "time": start_ts,
                "price": high_price
            },
            "rightBottom": {
                "time": end_ts,
                "price": low_price
            },
            "classType": pattern.get('value')  # 添加形态类型
        }]
    })
    return my_list
















