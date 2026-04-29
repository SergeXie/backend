import bisect
import backtrader as bt
from core.bt.tools.zigzag_calculator_byclass import ZigZagCalculator
from core.bt.tools.wm_pattern_recognizer import WMPatternRecognizer2

class WMExtractorStrategy(bt.Strategy):
    """
    用于提取历史WM形态的策略
    """
    def __init__(self):
        self.result_data_dict = dict()
        self.Id_TS_dict = {}
        self.Ts_to_hloc = {}
        self.inp_depth = 12
        self.all_kline_data = []

        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer2()

        self.addminperiod(self.inp_depth)

        self.next_total_time = 0.0
        self.ts_list = []

        self.d_klineId = self.data.klineId
        self.d_open = self.data.open
        self.d_high = self.data.high
        self.d_low = self.data.low
        self.d_close = self.data.close
        self.d_volume = self.data.volume

        self.all_date_strings = [
            bt.num2date(x).strftime('%Y-%m-%d %H:%M:%S')
            for x in self.data.datetime.array
        ]

    def next(self):
        if len(self) < self.inp_depth:
            return

        idx = len(self) - 1
        current_ts_str = self.all_date_strings[idx]
        k_id = int(self.d_klineId[0])

        self.Id_TS_dict[k_id] = current_ts_str

        current_kline_data = {
            "kLineId": k_id,
            "timestamp": current_ts_str,
            "open": self.d_open[0],
            "high": self.d_high[0],
            "low": self.d_low[0],
            "close": self.d_close[0],
            "volume": self.d_volume[0],
        }

        self.all_kline_data.append(current_kline_data)
        self.ts_list.append(current_ts_str)

        self.zigzag_calculator.process_kline(current_kline_data)

    def stop(self):
        zigzag_points = self.zigzag_calculator.get_zigzag_points(as_dict=False)
        min_points = 5
        if len(zigzag_points) >= min_points:
            for i in range(min_points, len(zigzag_points) + 1):
                window = zigzag_points[i - min_points: i]
                self.pattern_recognizer.analyze_zigzag_points(window)

    def get_analysis(self):
        wm_pattern = self.pattern_recognizer.get_pattern_titles()
        non_m_pattern = self.pattern_recognizer.get_non_standard_m_patterns()
        non_w_pattern = self.pattern_recognizer.get_non_standard_w_patterns()
        wm_pattern = wm_pattern + non_w_pattern + non_m_pattern
        ts_list = self.ts_list
        kline_data = self.all_kline_data

        for pattern in wm_pattern:
            # 填充 target_klines
            start_idx = bisect.bisect_left(ts_list, pattern.start_timestamp)
            end_idx = bisect.bisect_right(ts_list, pattern.end_timestamp)

            # 这是一个 List[Dict]，会被保存到 detail_data 中
            pattern.target_klines = kline_data[start_idx:end_idx]

        return wm_pattern