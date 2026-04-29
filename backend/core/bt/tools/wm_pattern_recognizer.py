from core.bt.tools.zigzag_calculator_byclass import ZigZagPoint
from dataclasses import dataclass, field
from typing import List, Dict, Any

class WMPatternRecognizer:
    """
    负责识别M和W形态的独立算法类。
    """
    def __init__(self):
        self.detected_patterns = []  # 存储M/W形态结果
        self._last_processed_zigzag_len = 0  # 跟踪已处理的zigzag点数量，避免重复判断
        self.zigzag_points = []
        self.maybe_detected_patterns = []  # 存储可能的M/W形态结果
        self.is_non_standard_maybe_w_patterns = []  #非标准的形态
        self.is_non_standard_maybe_m_patterns = []
        self.maybe_w = []
        self.maybe_m = []
        self.m_zigzag_points = []
        self.w_zigzag_points = []

        self.all_5point_list = []

        self.none_patterns = []

    # def zigzag_points_test(self, zigzag_points:List[ZigZagPoint]):
    #     pass

    def analyze_zigzag_points(self, zigzag_points, dict_index2ts=None, dict_ts2index=None):
        # print(zigzag_points[-1])
        """
        分析ZigZag点列表，识别M和W形态。
        Args:
            zigzag_points (list): 从ZigZagCalculator获取的ZigZag转折点列表。
            dict_index2ts (dict): 内部K线索引到时间戳的映射。
            dict_ts2index (dict): 时间戳到内部K线索引的映射。
        """
        # 只有当zigzag点数量增加且至少有5个点时才进行判断
        if len(zigzag_points) >= 5:
            self._add_all_5point(zigzag_points[-4:])

            self._judgment_m_pattern(zigzag_points, dict_index2ts, dict_ts2index)
            self._judgment_w_pattern(zigzag_points, dict_index2ts, dict_ts2index)
            maybe_m = self._maybe_m_pattern(zigzag_points[-4:])
            maybe_w = self._maybe_w_pattern(zigzag_points[-4:])

            self.zigzag_points = zigzag_points
            if not maybe_m and not maybe_w:
                self.none_patterns.append(zigzag_points[-5:])


    def _maybe_m_pattern(self, zigzag_points):
        fri = zigzag_points[0]
        sec = zigzag_points[1]
        thi = zigzag_points[2]
        fou = zigzag_points[3]

        h = sec['hloc'][0]
        l = sec['hloc'][1]
        mid = (h + l) / 2

        con1 = fri['price'] < thi['price'] < fou['price']< sec['price']
        con2 = (thi['index'] - fri['index']) > 20
        con5 = True
        if self.maybe_detected_patterns and zigzag_points[2]['timestamp'] == self.maybe_detected_patterns[-1]['timestamp']:
            con5 = False

        points_data = [
            {
                "timestamp": point['timestamp'],
                "kline_data": point  # 包含kLineId、price、index等完整数据
            }
            for point in zigzag_points
        ]
        if con1 and con2 and con5:
            self.maybe_detected_patterns.append({
                "timestamp": zigzag_points[2]['timestamp'],
                "price": zigzag_points[2]['price'],
                "four_price": zigzag_points[3]['price'],
                "two_price": zigzag_points[1]['price'],
                "value": "可能M形态",
                "start": zigzag_points[0]['timestamp'],
                "start_two": zigzag_points[1]['timestamp'],
                "end": zigzag_points[-1]['timestamp'],
                "kLineId": zigzag_points[2]['kLineId'],
            })
            value_str = "可能M形态"
            if fou['hloc'][0] > mid:
                value_str = 'M1形态'
            elif fou['hloc'][0] < mid:
                value_str = 'M2形态'
            # print(value_str)
            self.maybe_m.append({
                'points': points_data,
                "timestamp": zigzag_points[2]['timestamp'],
                "price": zigzag_points[2]['price'],
                "four_price": zigzag_points[3]['price'],
                "two_price": zigzag_points[1]['price'],
                "value": value_str,
                "start": zigzag_points[0]['timestamp'],
                "start_two": zigzag_points[1]['timestamp'],
                "start_third": zigzag_points[2]['timestamp'],
                "start_four": zigzag_points[3]['timestamp'],
                "end": zigzag_points[-1]['timestamp'],
                "kLineId": zigzag_points[2]['kLineId'],
                "kLineId_3": zigzag_points[3]['kLineId'],
                "start_timestamp": zigzag_points[0]['timestamp'],
                "end_timestamp": zigzag_points[-1]['timestamp'],
                "leftTop_price": max(zigzag_points[1]['price'], zigzag_points[3]['price']),
                "rigthBottom_price": zigzag_points[0]['price'],
            })
            return True
        else:

            return False

    def _maybe_w_pattern(self, zigzag_points):
        fri = zigzag_points[0]
        sec = zigzag_points[1]
        thi = zigzag_points[2]
        fou = zigzag_points[3]

        h = sec['hloc'][0]
        l = sec['hloc'][1]
        mid = (h + l) / 2

        con1 = sec['price'] < fou['price'] < thi['price']< fri['price']
        con2 = (thi['index'] - fri['index']) > 20

        con5 = True
        if self.maybe_detected_patterns and zigzag_points[2]['timestamp'] == self.maybe_detected_patterns[-1]['timestamp']:
            con5 = False
        points_data = [
            {
                "timestamp": point['timestamp'],
                "kline_data": point  # 包含kLineId、price、index等完整数据
            }
            for point in zigzag_points
        ]
        if con1 and con2 and con5:
            self.maybe_detected_patterns.append({
                "kLineId": zigzag_points[2]['kLineId'],
                "timestamp": zigzag_points[2]['timestamp'],
                "price": zigzag_points[2]['price'],
                "four_price": zigzag_points[3]['price'],
                "two_price": zigzag_points[1]['price'],
                "value": "可能W形态",
                "start": zigzag_points[0]['timestamp'],
                "start_two": zigzag_points[1]['timestamp'],
                "end": zigzag_points[3]['timestamp'],
            })
            value_str = "可能W形态"
            if fou['hloc'][1] < mid:
                value_str = 'W1形态'
            elif fou['hloc'][1] > mid:
                value_str = 'W2形态'
            # print(value_str)
            self.maybe_w.append({
                'points': points_data,
                "kLineId": zigzag_points[2]['kLineId'],
                "timestamp": zigzag_points[2]['timestamp'],
                "price": zigzag_points[2]['price'],
                "four_price": zigzag_points[3]['price'],
                "two_price": zigzag_points[1]['price'],
                "value": value_str,
                "start": zigzag_points[0]['timestamp'],
                "start_two": zigzag_points[1]['timestamp'],
                "start_third": zigzag_points[2]['timestamp'],
                "start_four": zigzag_points[3]['timestamp'],
                "end": zigzag_points[3]['timestamp'],
                "kLineId_3": zigzag_points[3]['kLineId'],
                "start_timestamp": zigzag_points[0]['timestamp'],
                "end_timestamp": zigzag_points[-1]['timestamp'],
                "leftTop_price": zigzag_points[0]['price'],
                "rigthBottom_price": min(zigzag_points[1]['price'], zigzag_points[3]['price'])
            })
            return True
        else:

            return False

    def _judgment_m_pattern(self, zigzag_points, dict_index2ts, dict_ts2index):
        """判断M形态 (双顶)"""
        # M形态需要至少5个点: L-D-H-D-L (或 H-D-H-D-H)
        # 这里的zigzag_points[-5:]是最近的5个点
        # 原始代码的M形态定义：l_d_val -> l_val -> head_val -> r_val -> r_d_val
        # 对应zigzag_points: [-5] -> [-4] -> [-3] -> [-2] -> [-1]
        fri = zigzag_points[-5]
        sec = zigzag_points[-4]
        thi = zigzag_points[-3]
        fou = zigzag_points[-2]

        h = sec['hloc'][0]
        l = sec['hloc'][1]
        mid = (h + l) / 2
        if len(zigzag_points) < 5:
            return

        l_val = zigzag_points[-4]['price']  # 左肩高点
        r_val = zigzag_points[-2]['price']  # 右肩高点
        l_d_val = zigzag_points[-5]['price']  # 左脚（形态起始低点）
        r_d_val = zigzag_points[-1]['price']  # 右脚（形态结束低点）
        head_val = zigzag_points[-3]['price']  # 颈线（谷底）

        # 距离20根 K 线
        con1 = (zigzag_points[-3]['index'] - zigzag_points[-5]['index']) > 20
        # 左肩高点高于右肩高点
        con3 = l_val > r_val
        # 颈线（谷底）高于双脚最低点，且低于双肩最高点
        con4 = head_val > max(l_d_val, r_d_val) and head_val < min(l_val, r_val)

        # 不重复判断，避免连续识别相同的形态
        con5 = True
        if self.detected_patterns and zigzag_points[-3]['timestamp'] == self.detected_patterns[-1]['timestamp']:
            con5 = False

        points_data = [
            {
                "timestamp": point['timestamp'],
                "kline_data": point  # 包含kLineId、price、index等完整数据
            }
            for point in zigzag_points[-5:]
        ]
        if con1 and con3 and con4 and con5:
            value_str = "M形态"
            if fou['hloc'][0] > mid:
                value_str = 'M1形态'
            elif fou['hloc'][0] < mid:
                value_str = 'M2形态'
            self.detected_patterns.append({
                'points': points_data,
                "kLineId": zigzag_points[-3]['kLineId'],
                "timestamp": zigzag_points[-3]['timestamp'],
                "price": zigzag_points[-3]['price'],
                "four_price": zigzag_points[-2]['price'],
                "value": value_str,
                "start": zigzag_points[-5]['timestamp'],
                "start_two": zigzag_points[-4]['timestamp'],
                "end": zigzag_points[-1]['timestamp'],
                "high": max(l_val, r_val),  # 形态的最高点是左右肩中较高的那个
                "low": head_val,  # 形态的最低点是颈线
                "leftTop_price": max(zigzag_points[1]['price'], zigzag_points[3]['price']),
                "rigthBottom_price": min(zigzag_points[0]['price'], zigzag_points[4]['price']),
            })
            self.m_zigzag_points.append(zigzag_points[-5:])
        else:
            no_con1 = fou['hloc'][0] > sec['hloc'][0]
            no_con2 = max(fou['hloc'][2], fou['hloc'][3]) < sec['hloc'][0]
            no_con3 = fri['price'] < thi['price'] and fri['price'] < sec['price']
            # 不重复判断，避免连续识别相同的形态
            no_con5 = True
            if self.is_non_standard_maybe_m_patterns and zigzag_points[-3]['timestamp'] == self.is_non_standard_maybe_m_patterns[-1]['timestamp']:
                no_con5 = False
            if no_con1 and no_con2 and no_con3 and no_con5:
                self.is_non_standard_maybe_m_patterns.append({
                    'points': points_data,
                    "timestamp": zigzag_points[-3]['timestamp'],
                    "price": zigzag_points[-2]['price'],
                    "four_price": zigzag_points[-2]['price'],
                    "two_price": zigzag_points[-4]['price'],
                    "value": 'M3形态',
                    "start": zigzag_points[-5]['timestamp'],
                    "start_two": zigzag_points[-4]['timestamp'],
                    "start_third": zigzag_points[-3]['timestamp'],
                    "start_four": zigzag_points[-2]['timestamp'],
                    "end": zigzag_points[-1]['timestamp'],
                    "kLineId": zigzag_points[-3]['kLineId'],
                    "kLineId_3": zigzag_points[-2]['kLineId'],
                    "start_timestamp": zigzag_points[-5]['timestamp'],
                    "end_timestamp": zigzag_points[-1]['timestamp'],
                    "leftTop_price": max(zigzag_points[-4]['price'], zigzag_points[-2]['price']),
                    "rigthBottom_price": zigzag_points[-5]['price'],
                })


    def _judgment_w_pattern(self, zigzag_points, dict_index2ts, dict_ts2index):
        """判断W形态 (双底)"""
        # W形态需要至少5个点: H-D-L-D-H (或 L-D-L-D-L)
        # 原始代码的W形态定义：l_d_val -> l_val -> head_val -> r_val -> r_d_val
        # 对应zigzag_points: [-5] -> [-4] -> [-3] -> [-2] -> [-1]
        fri = zigzag_points[-5]
        sec = zigzag_points[-4]
        thi = zigzag_points[-3]
        fou = zigzag_points[-2]


        h = sec['hloc'][0]
        l = sec['hloc'][1]
        mid = (h + l) / 2
        if len(zigzag_points) < 5:
            return

        l_val = zigzag_points[-4]['price']  # 左肩低点
        r_val = zigzag_points[-2]['price']  # 右肩低点
        l_d_val = zigzag_points[-5]['price']  # 左高（形态起始高点）
        r_d_val = zigzag_points[-1]['price']  # 右高（形态结束高点）
        head_val = zigzag_points[-3]['price']  # 颈线（山顶）

        # 距离20根 K 线
        con1 = (zigzag_points[-3]['index'] - zigzag_points[-5]['index']) > 20
        # 左肩低点低于右肩低点
        con3 = l_val < r_val
        # 颈线（山顶）低于双高点，且高于双低点
        con4 = head_val < min(l_d_val, r_d_val) and head_val > max(l_val, r_val)

        # 不重复判断
        con5 = True
        if self.detected_patterns and zigzag_points[-3]['timestamp'] == self.detected_patterns[-1]['timestamp']:
            con5 = False
        points_data = [
            {
                "timestamp": point['timestamp'],
                "kline_data": point  # 包含kLineId、price、index等完整数据
            }
            for point in zigzag_points[-5:]
        ]
        if con1 and con3 and con4 and con5:
            value_str = "W形态"
            if fou['hloc'][1] < mid:
                value_str = 'W1形态'
            elif fou['hloc'][1] > mid:
                value_str = 'W2形态'
            self.detected_patterns.append({
                'points': points_data,
                "kLineId": zigzag_points[-3]['kLineId'],
                "timestamp": zigzag_points[-3]['timestamp'],
                "price": zigzag_points[-3]['price'],
                "four_price": zigzag_points[-2]['price'],
                "value": value_str,
                "start": zigzag_points[-5]['timestamp'],
                "start_two": zigzag_points[-4]['timestamp'],
                "end": zigzag_points[-1]['timestamp'],
                "high": head_val,  # 形态的最高点是颈线
                "low": min(l_val, r_val),  # 形态的最低点是左右肩中较低的那个
                "leftTop_price": max(zigzag_points[0]['price'], zigzag_points[4]['price']),
                "rigthBottom_price": min(zigzag_points[1]['price'], zigzag_points[3]['price'])
            })
            self.w_zigzag_points.append(zigzag_points[-5:])
        else:
            no_con1 = fou['hloc'][1] < sec['hloc'][1]
            no_con2 = min(fou['hloc'][2], fou['hloc'][3]) > sec['hloc'][1]
            no_con3 = thi['price']< fri['price'] and sec['price']< fri['hloc'][2]
            no_con5 = True
            if self.is_non_standard_maybe_w_patterns and zigzag_points[-3]['timestamp'] == self.is_non_standard_maybe_w_patterns[-1]['timestamp']:
                no_con5 = False
            if no_con1 and no_con2 and no_con3 and no_con5:
                # print('W3形态')
                self.is_non_standard_maybe_w_patterns.append({
                    'points': points_data,
                    "timestamp": zigzag_points[-3]['timestamp'],
                    "price": zigzag_points[-3]['price'],
                    "four_price": zigzag_points[-2]['price'],
                    "two_price": zigzag_points[-4]['price'],
                    "value": 'W3形态',
                    "start": zigzag_points[-5]['timestamp'],
                    "start_two": zigzag_points[-4]['timestamp'],
                    "start_third": zigzag_points[-3]['timestamp'],
                    "start_four": zigzag_points[-2]['timestamp'],
                    "end": zigzag_points[-1]['timestamp'],
                    "kLineId": zigzag_points[-3]['kLineId'],
                    "kLineId_3": zigzag_points[-2]['kLineId'],
                    "start_timestamp": zigzag_points[-5]['timestamp'],
                    "end_timestamp": zigzag_points[-1]['timestamp'],
                    "leftTop_price": zigzag_points[-5]['price'],
                    "rigthBottom_price": min(zigzag_points[-4]['price'], zigzag_points[-2]['price'])
                })

    def _add_all_5point(self,zigzag_points):
        points_data = [
            {
                "timestamp": point['timestamp'],
                "kline_data": point  # 包含kLineId、price、index等完整数据
            }
            for point in zigzag_points
        ]
        self.all_5point_list.append({
            'points': points_data,
            "kLineId": zigzag_points[2]['kLineId'],
            "timestamp": zigzag_points[2]['timestamp'],
            "price": zigzag_points[2]['price'],
            "four_price": zigzag_points[3]['price'],
            "two_price": zigzag_points[1]['price'],
            "value": "全部形态",
            "start": zigzag_points[0]['timestamp'],
            "start_two": zigzag_points[1]['timestamp'],
            "start_third": zigzag_points[2]['timestamp'],
            "start_four": zigzag_points[3]['timestamp'],
            "end": zigzag_points[3]['timestamp'],
            "kLineId_3": zigzag_points[3]['kLineId'],
            "start_timestamp": zigzag_points[0]['timestamp'],
            "end_timestamp": zigzag_points[-1]['timestamp'],
        })



    def get_pattern_titles(self):
        """返回检测到的M/W形态标题的原始列表。"""
        return self.detected_patterns

    def get_non_standard_m_patterns(self):
        return self.is_non_standard_maybe_m_patterns

    def get_non_standard_w_patterns(self):
        return self.is_non_standard_maybe_w_patterns

    def get_maybe_detected_patterns(self):
        return self.maybe_detected_patterns

    def get_maybe_m_patterns(self):
        return self.maybe_m

    def get_maybe_classification(self):
        return self.detected_patterns + self.is_non_standard_maybe_m_patterns + self.is_non_standard_maybe_w_patterns

    def get_maybe_w_patterns(self):
        return self.maybe_w

    def get_zigzag_points(self):
        return self.zigzag_points

    def get_all_5point_list(self):
        return self.all_5point_list

    def get_formatted_m_w_patterns(self, index_to_ts=None, ts_to_index=None):
        """
        返回格式化后的M/W形态数据，包含时间范围和高低点信息。
        需要传入映射关系以便可能处理时间戳或索引。
        """
        formatted_list = []
        for p in self.detected_patterns:

            start_ts = p.get('start')
            end_ts = p.get('end')
            # try:
            #     start_ts_a2 = index_to_ts.get(ts_to_index.get(start_ts)+2)
            #     end_ts_d2 = index_to_ts.get(ts_to_index.get(end_ts)-2)
            # except:
            #     pass
            start_ts_a2 = start_ts
            end_ts_d2 = end_ts


            high_price = p.get('leftTop_price')
            low_price = p.get('rigthBottom_price')

            # 原始代码中有随机偏移，但在独立算法中通常不建议，
            # 这里直接使用形态的起止时间戳，如果需要随机偏移应由外部可视化逻辑处理。

            formatted_list.append({
                "truetime":[start_ts, end_ts],
                "time": [start_ts_a2, end_ts_d2],
                "list":[{
                    "leftTop": {
                        "time": start_ts_a2,
                        "price": high_price
                    },
                    "rightBottom": {
                        "time": end_ts_d2,
                        "price": low_price
                    },
                    "classType": p.get('value')  # 添加形态类型
                }]
            })
            # formatted_list.append({
            #     "time": [start_ts, end_ts],
            #     "leftTop": {
            #         "time": start_ts,
            #         "price": high_price
            #     },
            #     "rigthBottom": {
            #         "time": end_ts,
            #         "price": low_price
            #     },
            #     "value": p.get('value')  # 添加形态类型
            # })
        return formatted_list

    def get_all_wm_patterns(self):
        """
        返回所有识别到的W/M形态的详细数据列表
        每个元素为字典，包含形态类型、各点时间及完整K线数据
        """
        all_patterns = []

        # 处理M形态
        for m_points in self.m_zigzag_points:
            # 提取每个点的时间和完整K线数据
            points_data = [
                {
                    "timestamp": point['timestamp'],
                    "kline_data": point  # 包含kLineId、price、index等完整数据
                }
                for point in m_points
            ]

            all_patterns.append({
                "pattern_type": "M形态",
                "points": points_data,
                "start_timestamp": m_points[0]['timestamp'],
                "sec_timestamp": m_points[1]['timestamp'],
                'thi_timestamp': m_points[2]['timestamp'],
                "four_timestamp": m_points[3]['timestamp'],
                "end_timestamp": m_points[-1]['timestamp']
            })

        # 处理W形态
        for w_points in self.w_zigzag_points:
            points_data = [
                {
                    "timestamp": point['timestamp'],
                    "kline_data": point
                }
                for point in w_points
            ]

            all_patterns.append({
                "pattern_type": "W形态",
                "points": points_data,
                "start_timestamp": w_points[0]['timestamp'],
                "sec_timestamp": w_points[1]['timestamp'],
                'thi_timestamp': w_points[2]['timestamp'],
                "four_timestamp": w_points[3]['timestamp'],
                "end_timestamp": w_points[-1]['timestamp']
            })

        return all_patterns

    def get_all_none_patterns(self):

        all_patterns = []

        # 处理M形态
        for m_points in self.none_patterns:
            # 提取每个点的时间和完整K线数据
            points_data = [
                {
                    "timestamp": point['timestamp'],
                    "kline_data": point  # 包含kLineId、price、index等完整数据
                }
                for point in m_points
            ]

            all_patterns.append({
                "pattern_type": "空形态",
                "points": points_data,
                "start_timestamp": m_points[0]['timestamp'],
                "sec_timestamp": m_points[1]['timestamp'],
                'thi_timestamp': m_points[2]['timestamp'],
                "four_timestamp": m_points[3]['timestamp'],
                "end_timestamp": m_points[-1]['timestamp']
            })


        return all_patterns

@dataclass
class PatternBase:
    """所有形态的最底层基类（只允许无默认字段）"""
    timestamp: str
    price: float
    one_price: float
    two_price: float
    four_price: float
    start: str
    start_two: str
    start_third: str
    start_four: str
    end: str
    kLineId: int
    one_kLineId: int
    two_kLineId: int
    four_kLineId: int

# ================= 标准形态 =================

@dataclass
class StandardPattern(PatternBase):
    """标准 M/W 形态公共结构"""
    points: List[Dict]

    high: float
    low: float

    leftTop_price: float
    rightBottom_price: float

    start_timestamp: str
    end_timestamp: str

    end_price: float
    end_kLineId: int

    target_klines: list = field(default=None)


@dataclass
class StandardMPattern(StandardPattern):
    """标准 M 形态"""
    value: str = field(default="M形态")


@dataclass
class StandardWPattern(StandardPattern):
    """标准 W 形态"""
    value: str = field(default="W形态")


# ================= 可能形态 =================

@dataclass
class MaybePattern(PatternBase):
    """可能形态公共结构"""
    points: List[Dict]
    start_timestamp: str
    end_timestamp: str
    leftTop_price: float
    rightBottom_price: float
    start_second: int
    start_fourth: int
    end_price: float
    end_kLineId: int
    target_klines: list = field(default=None)



@dataclass
class MaybeMPattern(MaybePattern):
    value: str = field(default="可能M形态")


@dataclass
class MaybeWPattern(MaybePattern):
    value: str = field(default="可能W形态")


# ================= 非标准形态 =================

@dataclass
class NonStandardPattern(PatternBase):
    """非标准形态公共结构"""

    start_second: int
    start_fourth: int


@dataclass
class NonStandardMPattern(NonStandardPattern):
    pattern_type: str = field(default="M")
    value: str = field(default="M3形态")


@dataclass
class NonStandardWPattern(NonStandardPattern):
    pattern_type: str = field(default="W")
    value: str = field(default="W3形态")


# ================= 五点形态 =================

@dataclass
class All5PointPattern:
    """所有连续 5 点的原始形态"""
    points: List[Dict[str, Any]]
    timestamp: int
    price: float
    four_price: float
    two_price: float
    start: int
    start_second: int
    start_third: int
    start_fourth: int
    end: int
    kLineId: int
    kLineId_3: int
    start_timestamp: int
    end_timestamp: int



# =============== 主类重构 ===============
class WMPatternRecognizer2:
    """
    负责识别M和W形态的独立算法类。
    """

    def __init__(self):
        self.detected_patterns: List[StandardPattern] = []  # 标准M/W形态
        self.maybe_detected_patterns: List[MaybePattern] = []  # 可能M/W形态
        self.is_non_standard_maybe_m_patterns: List[NonStandardMPattern] = []  # 非标准M
        self.is_non_standard_maybe_w_patterns: List[NonStandardWPattern] = []  # 非标准W
        self.maybe_m: List[MaybeMPattern] = []  # 专用M形态
        self.maybe_w: List[MaybeWPattern] = []  # 专用W形态
        self.standard_m_patterns: List[StandardPattern] = []
        self.standard_w_patterns: List[StandardWPattern] = []

        self.m_zigzag_points: List[List[ZigZagPoint]] = []  # 标准M
        self.w_zigzag_points: List[List[ZigZagPoint]] = []  # 标准W
        self.all_5point_list: List[All5PointPattern] = []  # 全部的5点
        self.none_patterns: List[List[ZigZagPoint]] = []  # 非形态

        self.zigzag_points: List[ZigZagPoint] = []


    def analyze_zigzag_points(self, zigzag_points:List[ZigZagPoint]):
        if len(zigzag_points) >= 5:

            self.zigzag_points = zigzag_points
            self._add_all_5point(zigzag_points[-5:])
            self._judgment_m_pattern(zigzag_points[-5:])
            self._judgment_w_pattern(zigzag_points[-5:])
            maybe_m = self._maybe_m_pattern(zigzag_points[-4:])
            maybe_w = self._maybe_w_pattern(zigzag_points[-4:])

    def _maybe_m_pattern(self, zigzag_points: List[ZigZagPoint]):
        # 取最近4个点
        p0, p1, p2, p3 = zigzag_points[-4:]

        # 基础数据提取
        h = p1.hloc[0]
        l = p1.hloc[1]
        mid = (h + l) / 2

        con1 = p0.price < p2.price < p3.price < p1.price
        con2 = (p2.index - p0.index) > 20
        con5 = not self.maybe_detected_patterns or p2.timestamp != self.maybe_detected_patterns[-1].timestamp

        points_data = [
            {
                "timestamp": point.timestamp,
                "kline_data": point  # 包含kLineId、price、index等完整数据
            }
            for point in zigzag_points
        ]

        if con1 and con2 and con5:
            pattern = MaybeMPattern(
                points=points_data,
                timestamp=p2.timestamp,  # 颈线时间
                start=p0.timestamp,  # 起始时间
                end=p3.timestamp,  # 结束时间 (当前右肩)
                value="可能M形态",
                price=p2.price,  # 颈线价格
                one_price=p0.price,  # p0 价格 (起始点)
                one_kLineId=p0.kLineId,  # p0 K线ID
                two_kLineId=p1.kLineId,  # p1 K线ID (左肩)
                start_two=p1.timestamp,  # p1 时间 (左肩)
                start_four=p3.timestamp,  # p3 时间 (右肩)
                four_price=p3.price,  # 右肩价格
                two_price=p1.price,  # 左肩价格
                start_second=p1.timestamp,  # 左肩时间
                start_third=p2.timestamp,  # 颈线时间
                start_fourth=p3.timestamp,  # 右肩时间
                kLineId=p2.kLineId,  # 颈线K线ID
                four_kLineId=p3.kLineId,  # 右肩K线ID
                start_timestamp=p0.timestamp,
                end_timestamp=p3.timestamp,
                leftTop_price=max(p1.price, p3.price),  # 双肩最高
                rightBottom_price=p0.price,  # 起始最低
                end_price=p3.price,
                end_kLineId=p3.kLineId,

            )

            self.maybe_detected_patterns.append(pattern)
            self.maybe_m.append(pattern)
            return True

    def _maybe_w_pattern(self, zigzag_points: List[ZigZagPoint]):
        # 取最近4个点
        p0, p1, p2, p3 = zigzag_points[-4:]

        # 基础数据提取 (注意：W底通常关注低点p1的参考，这里逻辑保持与M头对称)
        h = p1.hloc[0]
        l = p1.hloc[1]
        mid = (h + l) / 2

        # W形态逻辑:
        # 原逻辑: sec < fou < thi < fri  =>  p1 < p3 < p2 < p0
        con1 = p1.price < p3.price < p2.price < p0.price
        con2 = (p2.index - p0.index) > 20
        con5 = not self.maybe_detected_patterns or p2.timestamp != self.maybe_detected_patterns[-1].timestamp

        points_data = [
            {
                "timestamp": point.timestamp,
                "kline_data": point  # 包含kLineId、price、index等完整数据
            }
            for point in zigzag_points
        ]

        if con1 and con2 and con5:
            # print(value_str)
            pattern = MaybeWPattern(
                points=points_data,
                timestamp=p2.timestamp,  # 颈线时间
                start=p0.timestamp,  # 起始时间
                end=p3.timestamp,  # 结束时间
                value="可能W形态",
                price=p2.price,  # 颈线价格 (High, p2)
                one_price=p0.price,  # p0 价格
                one_kLineId=p0.kLineId,  # p0 K线ID
                two_kLineId=p1.kLineId,  # p1 K线ID
                start_two=p1.timestamp,  # p1 时间 (对应报错 start_two)
                start_four=p3.timestamp,  # p3 时间 (对应报错 start_four)
                four_price=p3.price,  # 右脚价格 (Low, p3)
                two_price=p1.price,  # 左脚价格 (Low, p1)
                start_second=p1.timestamp,
                start_third=p2.timestamp,
                start_fourth=p3.timestamp,
                kLineId=p2.kLineId,  # 颈线K线ID
                four_kLineId=p3.kLineId,  # 右脚K线ID
                start_timestamp=p0.timestamp,
                end_timestamp=p3.timestamp,
                leftTop_price=p0.price,
                rightBottom_price=min(p1.price, p3.price),
                end_price=p3.price,
                end_kLineId=p3.kLineId,
            )

            self.maybe_detected_patterns.append(pattern)
            self.maybe_w.append(pattern)
            return True

        return False

    def _judgment_m_pattern(self, zigzag_points: List[ZigZagPoint]):
        # M形态需要至少5个点: L-D-H-D-L (或 H-D-H-D-H)
        # 这里的zigzag_points[-5:]是最近的5个点
        # 原始代码的M形态定义：l_d_val -> l_val -> head_val -> r_val -> r_d_val
        # 对应zigzag_points: [-5] -> [-4] -> [-3] -> [-2] -> [-1]
        if len(zigzag_points) < 5:
            return None

        # 取最近5个转折点：p0, p1, p2, p3, p4 对应 [左肩高, 左谷低, 头部高, 右谷低, 右肩高]
        p0, p1, p2, p3, p4 = zigzag_points[-5:]

        h = p1.hloc[0]
        l = p1.hloc[1]
        mid = (h + l) / 2

        l_val = p1.price  # 左肩高点
        r_val = p3.price  # 右肩高点
        l_d_val = p0.price  # 左脚（形态起始低点）
        r_d_val = p4.price  # 右脚（形态结束低点）
        head_val = p2.price  # 颈线（谷底）

        # 条件1：头部与左肩起点间隔足够（时间或K线索引）
        con1 = (p2.index - p0.index) > 20

        # 条件2：左肩高点 > 右肩高点（形成右肩下移）
        con3 = l_val > r_val

        # 条件3：颈线（谷底）高于双脚最低点，且低于双肩最高点
        con4 = con4 = head_val > max(l_d_val, r_d_val) and head_val < min(l_val, r_val)

        # 条件5：避免重复检测同一头部
        con5 = True
        if self.detected_patterns and p2.timestamp == self.detected_patterns[-1].timestamp:
            con5 = False

        points_data = [
            {
                "timestamp": point.timestamp,
                "kline_data": point  # 包含kLineId、price、index等完整数据
            }
            for point in zigzag_points[-5:]
        ]
        if con1 and con3 and con4 and con5:
            value_str = "M形态"
            if p3.hloc[0] > mid:
                value_str = 'M1形态'
            elif p3.hloc[0] < mid:
                value_str = 'M2形态'

            # 创建 M 形态实例
            pattern = StandardMPattern(
                points=points_data,
                kLineId=p2.kLineId,
                one_kLineId=p0.kLineId,  # 补全: p0 ID
                two_kLineId=p1.kLineId,  # 补全: p1 ID
                four_kLineId=p3.kLineId,  # 补全: p3 ID
                timestamp=p2.timestamp,
                price=p2.price,
                one_price=p0.price,
                four_price=p3.price,
                value=value_str,
                start=p0.timestamp,
                start_two=p1.timestamp,
                start_third=p2.timestamp,  # 补全: p2 时间
                start_four=p3.timestamp,  # 补全: p3 时间
                end=p4.timestamp,
                high=max(l_val, r_val),
                low=head_val,
                leftTop_price=max(p1.price, p3.price),
                rightBottom_price=min(p0.price, p4.price),
                two_price=p1.price,
                start_timestamp=p0.timestamp,
                end_timestamp=p4.timestamp,
                end_price=p4.price,
                end_kLineId=p4.kLineId,
            )

            self.detected_patterns.append(pattern)
            self.standard_m_patterns.append(pattern)
            self.m_zigzag_points.append(zigzag_points[-5:])
        else:
            no_con1 = p3.hloc[0] > p1.hloc[0]
            no_con2 = max(p3.hloc[2], p3.hloc[3]) < p1.hloc[0]
            no_con3 = p0.price < p2.price and p0.price < p1.price
            # 不重复判断，避免连续识别相同的形态
            no_con5 = True
            if self.is_non_standard_maybe_m_patterns and zigzag_points[-3].timestamp == \
                    self.is_non_standard_maybe_m_patterns[-1].timestamp:
                no_con5 = False
            if no_con1 and no_con2 and no_con3 and no_con5:
                pattern = MaybeMPattern(
                    points=points_data,
                    timestamp=p2.timestamp,  # [-3] 原字典 timestamp
                    value='M3形态',
                    start=p0.timestamp,  # [-5] 原字典 start
                    end=p4.timestamp,  # [-1] 原字典 end
                    price=p3.price,  # [-2] 原字典 price
                    four_price=p3.price,  # [-2] 原字典 four_price
                    two_price=p1.price,  # [-4] 原字典 two_price
                    one_price=p0.price,  # [-5]
                    one_kLineId=p0.kLineId,  # [-5]
                    two_kLineId=p1.kLineId,  # [-4]
                    start_two=p1.timestamp,  # [-4]
                    start_four=p3.timestamp,  # [-2]
                    # 时间参数
                    start_second=p1.timestamp,  # [-4] 原字典 start_two
                    start_third=p2.timestamp,  # [-3] 原字典 start_third
                    start_fourth=p3.timestamp,  # [-2] 原字典 start_four
                    # K线ID
                    kLineId=p2.kLineId,  # [-3] 原字典 kLineId
                    four_kLineId=p3.kLineId,  # [-2] 原字典 kLineId_3 (类参数通常为 four_kLineId)
                    # 其他
                    start_timestamp=p0.timestamp,  # [-5]
                    end_timestamp=p4.timestamp,  # [-1]
                    leftTop_price=max(p1.price, p3.price),  # 原字典 leftTop_price
                    rightBottom_price=p0.price,  # [-5] 原字典 rigthBottom_price (已修正拼写)
                    end_price=p4.price,
                    end_kLineId = p4.kLineId,
                )
                self.is_non_standard_maybe_m_patterns.append(pattern)

    def _judgment_w_pattern(self, zigzag_points: List[ZigZagPoint]):
        if len(zigzag_points) < 5:
            return

        p0, p1, p2, p3, p4 = zigzag_points[-5:]
        h = p1.hloc[0]
        l = p1.hloc[1]
        mid = (h + l) / 2

        l_val = p1.price  # 左肩低点
        r_val = p3.price  # 右肩低点
        l_d_val = p0.price  # 左高（形态起始高点）
        r_d_val = p4.price  # 右高（形态结束高点）
        head_val = p2.price  # 颈线（山顶）

        # 距离20根 K 线
        con1 = (p2.index - p0.index) > 20
        # 左肩低点低于右肩低点
        con3 = l_val < r_val
        # 颈线（山顶）低于双高点，且高于双低点
        con4 = head_val < min(l_d_val, r_d_val) and head_val > max(l_val, r_val)

        # 不重复判断
        con5 = True
        if self.detected_patterns and p2.timestamp == self.detected_patterns[-1].timestamp:
            con5 = False
        points_data = [
            {
                "timestamp": point.timestamp,
                "kline_data": point  # 包含kLineId、price、index等完整数据
            }
            for point in zigzag_points[-5:]
        ]
        if con1 and con3 and con4 and con5:
            value_str = "W形态"
            if p3.hloc[1] < mid:
                value_str = 'W1形态'
            elif p3.hloc[1] > mid:
                value_str = 'W2形态'
            # 创建标准W形态实例
            pattern = StandardWPattern(
                points=points_data,
                kLineId=p2.kLineId,
                one_kLineId=p0.kLineId,  # 补全
                two_kLineId=p1.kLineId,  # 补全
                four_kLineId=p3.kLineId,  # 补全
                timestamp=p2.timestamp,
                price=p2.price,
                one_price=p0.price,
                four_price=p3.price,
                value=value_str,
                start=p0.timestamp,
                start_third=p2.timestamp,  # 补全
                start_four=p3.timestamp,  # 补全
                start_two=p1.timestamp,
                end=p4.timestamp,
                high=head_val,
                low=min(l_val, r_val),
                leftTop_price=max(p0.price, p4.price),
                rightBottom_price=min(p1.price, p3.price),
                two_price=p1.price,
                start_timestamp=p0.timestamp,
                end_timestamp=p4.timestamp,
                end_price=p4.price,
                end_kLineId=p4.kLineId,
            )

            self.detected_patterns.append(pattern)
            self.standard_w_patterns.append(pattern)
            self.w_zigzag_points.append(zigzag_points[-5:])
        else:
            no_con1 = p3.hloc[1] < p1.hloc[1]
            no_con2 = min(p3.hloc[2], p3.hloc[3]) > p1.hloc[1]
            no_con3 = p2.price < p0.price and p1.price < p0.hloc[2]
            # 不重复判断，避免连续识别相同的形态
            no_con5 = True
            if self.is_non_standard_maybe_w_patterns and zigzag_points[-3].timestamp == \
                    self.is_non_standard_maybe_w_patterns[-1].timestamp:
                no_con5 = False
            if no_con1 and no_con2 and no_con3 and no_con5:
                pattern = MaybeMPattern(
                    points=points_data,
                    timestamp=p2.timestamp,  # [-3] 原字典 timestamp
                    value='W3形态',
                    start=p0.timestamp,  # [-5] 原字典 start
                    end=p4.timestamp,  # [-1] 原字典 end
                    price=p3.price,  # [-2] 原字典 price
                    four_price=p3.price,  # [-2] 原字典 four_price
                    two_price=p1.price,  # [-4] 原字典 two_price
                    one_price=p0.price,  # [-5]
                    one_kLineId=p0.kLineId,  # [-5]
                    two_kLineId=p1.kLineId,  # [-4]
                    start_two=p1.timestamp,  # [-4]
                    start_four=p3.timestamp,  # [-2]
                    # 时间参数
                    start_second=p1.timestamp,  # [-4] 原字典 start_two
                    start_third=p2.timestamp,  # [-3] 原字典 start_third
                    start_fourth=p3.timestamp,  # [-2] 原字典 start_four
                    # K线ID
                    kLineId=p2.kLineId,  # [-3] 原字典 kLineId
                    four_kLineId=p3.kLineId,  # [-2] 原字典 kLineId_3 (类参数通常为 four_kLineId)
                    # 其他
                    start_timestamp=p0.timestamp,  # [-5]
                    end_timestamp=p4.timestamp,  # [-1]
                    leftTop_price=p0.price,  # 原字典 leftTop_price
                    rightBottom_price=min(p1.price, p3.price),
                    end_price = p4.price,
                    end_kLineId=p4.kLineId,
                )
                self.is_non_standard_maybe_w_patterns.append(pattern)

    def _add_all_5point(self, zigzag_points: List[ZigZagPoint]):
        # 确保传入了5个点
        if len(zigzag_points) < 5:
            return

        # 解包5个点，方便后续取值
        p0, p1, p2, p3, p4 = zigzag_points

        points_data = [
            {
                "timestamp": point.timestamp,
                "kline_data": point  # 保持原样，前端可能需要原始对象
            }
            for point in zigzag_points
        ]

        pattern = All5PointPattern(
            points=points_data,
            # 以中间点 p2 (通常是形态的头部/颈线位) 为主要锚点
            timestamp=p2.timestamp,
            price=p2.price,

            # 其他关键价格
            four_price=p3.price,
            two_price=p1.price,

            # 时间序列
            start=p0.timestamp,
            start_second=p1.timestamp,
            start_third=p2.timestamp,
            start_fourth=p3.timestamp,
            end=p4.timestamp,

            # K线ID (注意：根据上下文，对象属性通常是 snake_case 的 kLineId)
            kLineId=p2.kLineId,  # 中间点ID
            kLineId_3=p3.kLineId,  # 第4点ID

            # 整体范围
            start_timestamp=p0.timestamp,
            end_timestamp=p4.timestamp
        )
        self.all_5point_list.append(pattern)

    # =============== 类型安全的访问方法 ===============
    def get_zigzag_points(self) -> List[ZigZagPoint]:
        return self.zigzag_points

    def get_pattern_titles(self) -> List[StandardPattern]:
        """返回标准M/W形态列表"""
        return self.detected_patterns

    def get_standard_m_patterns(self) -> List[StandardPattern]:
        """返回标准M/W形态列表"""
        return self.standard_m_patterns

    def get_standard_w_patterns(self) -> List[StandardPattern]:
        """返回标准M/W形态列表"""
        return self.standard_w_patterns

    def get_non_standard_m_patterns(self) -> List[NonStandardMPattern]:
        """返回非标准M形态列表"""
        return self.is_non_standard_maybe_m_patterns

    def get_non_standard_w_patterns(self) -> List[NonStandardWPattern]:
        """返回非标准W形态列表"""
        return self.is_non_standard_maybe_w_patterns

    def get_maybe_detected_patterns(self) -> List[MaybePattern]:
        """返回可能M/W形态列表（通用）"""
        return self.maybe_detected_patterns

    def get_maybe_m_patterns(self) -> List[MaybeMPattern]:
        """返回可能M形态列表（专用）"""
        return self.maybe_m

    def get_maybe_w_patterns(self) -> List[MaybeWPattern]:
        """返回可能W形态列表（专用）"""
        return self.maybe_w

    def get_all_5point_list(self) -> List[All5PointPattern]:
        """返回所有5点形态列表"""
        return self.all_5point_list

    def get_all_wm_patterns(self) -> List[StandardPattern]:
        """返回所有标准M/W形态列表"""
        return self.detected_patterns

    def get_all_none_patterns(self) -> List[List[ZigZagPoint]]:
        """返回未识别形态的点列表"""
        return self.none_patterns