import backtrader as bt
from utils.indicators.peak_trough import PeakTroughIndicator, PeakTroughType
from dataclasses import asdict
import math
from utils.module.wm_pattern_recognizer import WMPatternRecognizer, WMPatternRecognizer2
from utils.module.zigzag_calculator_byclass import ZigZagCalculator
from utils.module.wm_pk_point_calculator import PeakTroughPointCalculator

# 假设 ZigZagCalculator 和 WMPatternRecognizer 已经在当前文件中定义或已导入

class ResponseWMData(bt.Strategy):
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
        self.pk_point_calculator = PeakTroughPointCalculator()
        self.pattern_recognizer = WMPatternRecognizer2()
        # 确保数据长度足够时再开始计算
        self.addminperiod(self.p.inp_depth)

        ##################################################################
        self.peak_trough = PeakTroughIndicator(self.data)

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
        self.kLineId_to_ts = dict()
        self.ts_to_kLineId = dict()
        self.kLineId_to_all = dict()

        self.zigzag = []
        Z_from = indicator_params.get("Zfrom", 1)
        self.Z_from = 'pc' if Z_from == 0 else 'zig'


    def next(self):
        self.ts_to_kLineId[self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')] = int(self.data.klineId[0])
        self.kLineId_to_ts[int(self.data.klineId[0])] = self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')
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
        self.kLineId_to_all[int(self.data.klineId[0])] = current_kline_data

        if self.Z_from == 'zig':
            # 确保数据长度足够
            if len(self) < self.p.inp_depth:
                return
            # 调用ZigZag算法类的处理方法
            # process_kline会返回是否产生了新的zigzag点，如果产生，就通知形态识别器
            new_zigzag_point_or_updated = self.zigzag_calculator.process_kline(current_kline_data)

            # 如果ZigZag有更新，就通知形态识别器进行分析
            if new_zigzag_point_or_updated:
                # zigzag_points = self.zigzag_calculator.get_zigzag_points()
                # dict_index2ts, dict_ts2index = self.zigzag_calculator.get_index_timestamp_maps()
                # self.pattern_recognizer.analyze_zigzag_points(zigzag_points)
                # 修改为对象列表
                zigzag_points = self.zigzag_calculator.get_zigzag_points(as_dict=False)
                self.pattern_recognizer.analyze_zigzag_points(zigzag_points)

        #################################################################################################
        elif self.Z_from == 'pc':  # 峰值连线

            val = self.peak_trough.lines.pt_r[0]
            if val > 0:
                pt_type = PeakTroughType.Peak
            elif val < 0:
                pt_type = PeakTroughType.Trough
            else:
                pt_type = PeakTroughType.Normal

            center_line_id = self.peak_trough.lines.pt_center[0]
            center_line_id = self.data.klineId[0] if pt_type == PeakTroughType.Normal else center_line_id
            self.pk_point_calculator.process_point(self.kLineId_to_all.get(center_line_id), pt_type)
            # print('峰值连线',val)
            # 如果值不是 NaN，说明当前K线确认了一个顶或底
            if not math.isnan(val):
                PeakTrough_points = self.pk_point_calculator.get_PeakTrough_points(as_dict=False)
                self.pattern_recognizer.analyze_zigzag_points(PeakTrough_points)





    def get_analysis(self):
        # # 组织数据结构，从独立的算法类获取数据
        # zigzag_points = self.zigzag_calculator.get_zigzag_points()
        # # 获取索引-时间戳映射，用于格式化M/W形态数据
        if self.Z_from == 'zig':
            zigzag_points = self.pattern_recognizer.get_zigzag_points()
        else:
            zigzag_points = self.pattern_recognizer.get_zigzag_points()


        show_pattern = self.indicator_params.get("show_mabye_pattern")
        # print(show_pattern)
        if show_pattern == 0:  # 确认形态
            pattern_titles = self.pattern_recognizer.get_pattern_titles()  # 获取原始形态标题列表
            non_standard_m_patterns = self.pattern_recognizer.get_non_standard_m_patterns()
            non_standard_w_patterns = self.pattern_recognizer.get_non_standard_w_patterns()
            pattern_titles = pattern_titles + non_standard_m_patterns + non_standard_w_patterns

            for pattern_title in pattern_titles:
                print(pattern_title.value)
        elif show_pattern == 1:
            pattern_titles = self.pattern_recognizer.get_maybe_detected_patterns()





        self.result_data_dict["lines"] = [
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'top',
                "data": pattern_titles
            },
            {
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FFFF"),
                "data": [asdict(point) for point in zigzag_points]
            },
        ]

        return [self.result_data_dict["lines"], None, None]


