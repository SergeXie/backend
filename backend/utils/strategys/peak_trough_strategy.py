import math
import backtrader as bt
from utils.indicators.peak_trough import PeakTroughIndicator, PeakTroughType
from utils.time_utils import LZSDTimeUtils


class ResponsePeakTroughData(bt.Strategy):
    def __init__(self, indicator_params, indicator_name, comments, begin_time=None):
        # 初始化指标
        self.indicator_params = indicator_params
        self.peak_trough = PeakTroughIndicator(self.data)
        self.broken_peak = []  # 顶
        self.broken_trough = []  # 底

        self.line_data = []

        self.broken_trough_data = []
        self.broken_peak_data = []
        self.peak_text_data = []
        self.trough_text_data = []


        self.last_type = PeakTroughType.Normal
        self.last_k_center_id = 0

    def next(self):
        val = self.peak_trough.lines.pt_r[0]
        if not math.isnan(val):
            pt_type = PeakTroughType.Peak if val > 0 else PeakTroughType.Trough
            if self.last_type != PeakTroughType.Normal:
                if self.last_type == pt_type:
                    if pt_type == PeakTroughType.Trough:
                        self.broken_trough.append(self.last_k_center_id)
                    else:
                        self.broken_peak.append(self.last_k_center_id)

            self.last_type = pt_type
            self.last_k_center_id = self.peak_trough.pt_center[0]


    def _index_of_line_id(self, line_id):
        line_count = len(self.data)
        for i in range(0 - line_count -1, 1, 1):
            if line_id == self.data.klineId[i]:
                return i

        return None

    def stop(self):
        line_count = len(self.data)
        index = 0

        for i in range(0 - line_count -1, 1, 1):
            pt_type_val = self.peak_trough.lines.pt_r[i]
            if not math.isnan(pt_type_val):
                pt_type = PeakTroughType.Peak if pt_type_val > 0 else PeakTroughType.Trough
                center_line_id = self.peak_trough.lines.pt_center[i]
                center_line_index = self._index_of_line_id(center_line_id)
                if center_line_index:
                    h = self.data.high[center_line_index]
                    l = self.data.low[center_line_index]
                    price = h if pt_type == PeakTroughType.Peak else l
                    timestamp_str = LZSDTimeUtils.fmt(self.data.datetime.datetime(center_line_index))
                    """
                    {kLineId: 11326235, timestamp: "2025-09-05 17:00:00", price: 3597.93, index: 4}
                    """
                    self.line_data.append({
                        "kLineId": int(center_line_id),
                        "timestamp": timestamp_str,
                        "price": price,
                        "index": index
                    })

                    if len(self.line_data) > 1:
                        dict = self.line_data[-2]
                        """
                        "value": "顶32 26.80 K8 \n 2025-09-05 19:30:00"
                        """
                        type_desc_str = str(pt_type) + str(index)
                        price_str = str(round(abs(price - dict["price"]), 2))
                        k_interval_str = "K" + str(index - dict["index"])
                        print("price_str:{}".format(price_str))

                        text = f"{type_desc_str} {price_str} {k_interval_str}\n{timestamp_str}"

                        entity = {
                            "kLineId": int(center_line_id),
                            "timestamp": timestamp_str,
                            "price": price,
                            "value": text
                        }

                        if pt_type == PeakTroughType.Peak:
                            self.peak_text_data.append(entity)
                        else:
                            self.trough_text_data.append(entity)

            index += 1

        broken_data_array = [self.broken_trough, self.broken_peak]
        pt_type_array = [PeakTroughType.Trough, PeakTroughType.Peak]
        fill_data_array = [self.broken_trough_data, self.broken_peak_data]

        for j in range(len(broken_data_array)):
            broken_data = broken_data_array[j]
            pt_type = pt_type_array[j]

            for k in range(len(broken_data)):
                center_line_id = broken_data[k]
                """
                {kLineId: 11326472, timestamp: "2025-09-08 11:15:00", price: 3617.11, index: 73}
                """
                center_line_index = self._index_of_line_id(center_line_id)
                if center_line_index is not None:
                    h = self.data.high[center_line_index]
                    l = self.data.low[center_line_index]
                    fill_data_array[j].append({
                        "kLineId": int(center_line_id),
                        "timestamp": LZSDTimeUtils.fmt(self.data.datetime.datetime(center_line_index)),
                        "price": l if pt_type == PeakTroughType.Trough else h,
                    })

    def get_analysis(self):
        result_data_dict = {}
        result_data_dict["lines"] = [
            {
                "type": "brokenline",
                "color": self.indicator_params.get("TrendPackconnectionColor", "#00FF00"),
                "data": self.line_data
            },
            {
                "type": "bmp",
                "arrow": self.indicator_params.get("peakBmp", 1),
                "data": self.broken_trough_data
            },
            {
                "type": "bmp",
                "arrow": self.indicator_params.get("bottolBmp", 2),
                "data": self.broken_peak_data
            },
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'top',
                "data": self.peak_text_data
            },
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'bottom',
                "data": self.trough_text_data
            },
        ]

        startime = None
        endtime = None
        return [result_data_dict["lines"], startime, endtime, None]

