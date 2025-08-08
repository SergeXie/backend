import random

class WMPatternRecognizer:
    """
    负责识别M和W形态的独立算法类。
    """

    def __init__(self):
        self.detected_patterns = []  # 存储M/W形态结果
        self._last_processed_zigzag_len = 0  # 跟踪已处理的zigzag点数量，避免重复判断
        self.zigzag_points = []

    def analyze_zigzag_points(self, zigzag_points, dict_index2ts, dict_ts2index):
        """
        分析ZigZag点列表，识别M和W形态。
        Args:
            zigzag_points (list): 从ZigZagCalculator获取的ZigZag转折点列表。
            dict_index2ts (dict): 内部K线索引到时间戳的映射。
            dict_ts2index (dict): 时间戳到内部K线索引的映射。
        """
        # 只有当zigzag点数量增加且至少有5个点时才进行判断
        if len(zigzag_points) >= 5 and len(zigzag_points) > self._last_processed_zigzag_len:
            self._judgment_m_pattern(zigzag_points, dict_index2ts, dict_ts2index)
            self._judgment_w_pattern(zigzag_points, dict_index2ts, dict_ts2index)
            self._last_processed_zigzag_len = len(zigzag_points)  # 更新已处理的长度
            self.zigzag_points = zigzag_points

    def _judgment_m_pattern(self, zigzag_points, dict_index2ts, dict_ts2index):
        """判断M形态 (双顶)"""
        # M形态需要至少5个点: L-D-H-D-L (或 H-D-H-D-H)
        # 这里的zigzag_points[-5:]是最近的5个点
        # 原始代码的M形态定义：l_d_val -> l_val -> head_val -> r_val -> r_d_val
        # 对应zigzag_points: [-5] -> [-4] -> [-3] -> [-2] -> [-1]

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

        if con1 and con3 and con4 and con5:
            self.detected_patterns.append({
                "kLineId": zigzag_points[-3]['kLineId'],
                "timestamp": zigzag_points[-3]['timestamp'],
                "price": zigzag_points[-3]['price'],
                "four_price": zigzag_points[-2]['price'],
                "value": "M形态",
                "start": zigzag_points[-5]['timestamp'],
                "start_two": zigzag_points[-4]['timestamp'],
                "end": zigzag_points[-1]['timestamp'],
                "high": max(l_val, r_val),  # 形态的最高点是左右肩中较高的那个
                "low": head_val,  # 形态的最低点是颈线
            })

    def _judgment_w_pattern(self, zigzag_points, dict_index2ts, dict_ts2index):
        """判断W形态 (双底)"""
        # W形态需要至少5个点: H-D-L-D-H (或 L-D-L-D-L)
        # 原始代码的W形态定义：l_d_val -> l_val -> head_val -> r_val -> r_d_val
        # 对应zigzag_points: [-5] -> [-4] -> [-3] -> [-2] -> [-1]

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

        if con1 and con3 and con4 and con5:
            self.detected_patterns.append({
                "kLineId": zigzag_points[-3]['kLineId'],
                "timestamp": zigzag_points[-3]['timestamp'],
                "price": zigzag_points[-3]['price'],
                "four_price": zigzag_points[-2]['price'],
                "value": "W形态",
                "start": zigzag_points[-5]['timestamp'],
                "start_two": zigzag_points[-4]['timestamp'],
                "end": zigzag_points[-1]['timestamp'],
                "high": head_val,  # 形态的最高点是颈线
                "low": min(l_val, r_val),  # 形态的最低点是左右肩中较低的那个
            })

    def get_pattern_titles(self):
        """返回检测到的M/W形态标题的原始列表。"""
        return self.detected_patterns

    def get_zigzag_points(self):
        return self.zigzag_points

    def get_formatted_m_w_patterns(self, dict_index2ts, dict_ts2index):
        """
        返回格式化后的M/W形态数据，包含时间范围和高低点信息。
        需要传入映射关系以便可能处理时间戳或索引。
        """
        formatted_list = []
        for p in self.detected_patterns:
            start_ts = p.get('start')
            end_ts = p.get('end')
            high_price = p.get('high')
            low_price = p.get('low')

            # 原始代码中有随机偏移，但在独立算法中通常不建议，
            # 这里直接使用形态的起止时间戳，如果需要随机偏移应由外部可视化逻辑处理。

            formatted_list.append({
                "time": [start_ts, end_ts],
                "leftTop": {
                    "time": start_ts,
                    "price": high_price
                },
                "rigthBottom": {
                    "time": end_ts,
                    "price": low_price
                },
                "value": p.get('value')  # 添加形态类型
            })
        return formatted_list