import backtrader as bt

from core.bt.tools.wm_pattern_recognizer import WMPatternRecognizer
from core.bt.tools.zigzag_calculator import ZigZagCalculator
from core.bt.indicators.packconnection import IndicatorDataProcessor


# 假设 ZigZagCalculator 和 WMPatternRecognizer 已经在当前文件中定义或已导入

class ResponseWMPicyureData(bt.Strategy):
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
        print('参数这里',indicator_params)
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
        self.M = []

        self.zigzag = []
        Z_from = indicator_params.get("Zfrom", 1)
        self.Z_from = 'pc' if Z_from == 0 else 'zig'

        self.index_to_ts = {}
        self.ts_to_index = {}


    def next(self):

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
        index = len(self)
        ts = self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')
        self.index_to_ts[index] = ts
        self.ts_to_index[ts] = index


        if self.Z_from == 'zig':

            # 确保数据长度足够
            if len(self) < self.p.inp_depth:
                return

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
            pattern_titles = self.pattern_recognizer.get_maybe_detected_patterns()
        print("这里@@@@@@@@@@@@")
        print(self.index_to_ts)
        print(self.ts_to_index)

        formatted_m_w_patterns = self.pattern_recognizer.get_formatted_m_w_patterns(self.index_to_ts,self.ts_to_index)
        print(formatted_m_w_patterns)

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
                "data": formatted_m_w_patterns
            },
            {
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FFFF"),
                "data": zigzag_points
            },
        ]

        return [self.result_data_dict["lines"], None, None]


