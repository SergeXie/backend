import random

# class WMPatternRecognizer:
#     """
#     负责识别M和W形态的独立算法类。
#     """
#
#     def __init__(self):
#         self.detected_patterns = []  # 存储M/W形态结果
#         self._last_processed_zigzag_len = 0  # 跟踪已处理的zigzag点数量，避免重复判断
#         self.zigzag_points = []
#
#     def analyze_zigzag_points(self, zigzag_points, dict_index2ts, dict_ts2index):
#         print(zigzag_points[-1])
#         """
#         分析ZigZag点列表，识别M和W形态。
#         Args:
#             zigzag_points (list): 从ZigZagCalculator获取的ZigZag转折点列表。
#             dict_index2ts (dict): 内部K线索引到时间戳的映射。
#             dict_ts2index (dict): 时间戳到内部K线索引的映射。
#         """
#         # 只有当zigzag点数量增加且至少有5个点时才进行判断
#         if len(zigzag_points) >= 5 and len(zigzag_points) > self._last_processed_zigzag_len:
#             self._judgment_m_pattern(zigzag_points, dict_index2ts, dict_ts2index)
#             self._judgment_w_pattern(zigzag_points, dict_index2ts, dict_ts2index)
#             self._last_processed_zigzag_len = len(zigzag_points)  # 更新已处理的长度
#             self.zigzag_points = zigzag_points
#
#     def _judgment_m_pattern(self, zigzag_points, dict_index2ts, dict_ts2index):
#         """判断M形态 (双顶)"""
#         # M形态需要至少5个点: L-D-H-D-L (或 H-D-H-D-H)
#         # 这里的zigzag_points[-5:]是最近的5个点
#         # 原始代码的M形态定义：l_d_val -> l_val -> head_val -> r_val -> r_d_val
#         # 对应zigzag_points: [-5] -> [-4] -> [-3] -> [-2] -> [-1]
#
#         if len(zigzag_points) < 5:
#             return
#
#         l_val = zigzag_points[-4]['price']  # 左肩高点
#         r_val = zigzag_points[-2]['price']  # 右肩高点
#         l_d_val = zigzag_points[-5]['price']  # 左脚（形态起始低点）
#         r_d_val = zigzag_points[-1]['price']  # 右脚（形态结束低点）
#         head_val = zigzag_points[-3]['price']  # 颈线（谷底）
#
#         # 距离20根 K 线
#         con1 = (zigzag_points[-3]['index'] - zigzag_points[-5]['index']) > 20
#         # 左肩高点高于右肩高点
#         con3 = l_val > r_val
#         # 颈线（谷底）高于双脚最低点，且低于双肩最高点
#         con4 = head_val > max(l_d_val, r_d_val) and head_val < min(l_val, r_val)
#
#         # 不重复判断，避免连续识别相同的形态
#         con5 = True
#         if self.detected_patterns and zigzag_points[-3]['timestamp'] == self.detected_patterns[-1]['timestamp']:
#             con5 = False
#
#         if con1 and con3 and con4 and con5:
#             self.detected_patterns.append({
#                 "kLineId": zigzag_points[-3]['kLineId'],
#                 "timestamp": zigzag_points[-3]['timestamp'],
#                 "price": zigzag_points[-3]['price'],
#                 "four_price": zigzag_points[-2]['price'],
#                 "value": "M形态",
#                 "start": zigzag_points[-5]['timestamp'],
#                 "start_two": zigzag_points[-4]['timestamp'],
#                 "end": zigzag_points[-1]['timestamp'],
#                 "high": max(l_val, r_val),  # 形态的最高点是左右肩中较高的那个
#                 "low": head_val,  # 形态的最低点是颈线
#             })
#
#     def _judgment_w_pattern(self, zigzag_points, dict_index2ts, dict_ts2index):
#         """判断W形态 (双底)"""
#         # W形态需要至少5个点: H-D-L-D-H (或 L-D-L-D-L)
#         # 原始代码的W形态定义：l_d_val -> l_val -> head_val -> r_val -> r_d_val
#         # 对应zigzag_points: [-5] -> [-4] -> [-3] -> [-2] -> [-1]
#
#         if len(zigzag_points) < 5:
#             return
#
#         l_val = zigzag_points[-4]['price']  # 左肩低点
#         r_val = zigzag_points[-2]['price']  # 右肩低点
#         l_d_val = zigzag_points[-5]['price']  # 左高（形态起始高点）
#         r_d_val = zigzag_points[-1]['price']  # 右高（形态结束高点）
#         head_val = zigzag_points[-3]['price']  # 颈线（山顶）
#
#         # 距离20根 K 线
#         con1 = (zigzag_points[-3]['index'] - zigzag_points[-5]['index']) > 20
#         # 左肩低点低于右肩低点
#         con3 = l_val < r_val
#         # 颈线（山顶）低于双高点，且高于双低点
#         con4 = head_val < min(l_d_val, r_d_val) and head_val > max(l_val, r_val)
#
#         # 不重复判断
#         con5 = True
#         if self.detected_patterns and zigzag_points[-3]['timestamp'] == self.detected_patterns[-1]['timestamp']:
#             con5 = False
#
#         if con1 and con3 and con4 and con5:
#             self.detected_patterns.append({
#                 "kLineId": zigzag_points[-3]['kLineId'],
#                 "timestamp": zigzag_points[-3]['timestamp'],
#                 "price": zigzag_points[-3]['price'],
#                 "four_price": zigzag_points[-2]['price'],
#                 "value": "W形态",
#                 "start": zigzag_points[-5]['timestamp'],
#                 "start_two": zigzag_points[-4]['timestamp'],
#                 "end": zigzag_points[-1]['timestamp'],
#                 "high": head_val,  # 形态的最高点是颈线
#                 "low": min(l_val, r_val),  # 形态的最低点是左右肩中较低的那个
#             })
#
#     def get_pattern_titles(self):
#         """返回检测到的M/W形态标题的原始列表。"""
#         return self.detected_patterns
#
#     def get_zigzag_points(self):
#         return self.zigzag_points
#
#     def get_formatted_m_w_patterns(self, dict_index2ts, dict_ts2index):
#         """
#         返回格式化后的M/W形态数据，包含时间范围和高低点信息。
#         需要传入映射关系以便可能处理时间戳或索引。
#         """
#         formatted_list = []
#         for p in self.detected_patterns:
#             start_ts = p.get('start')
#             end_ts = p.get('end')
#             high_price = p.get('high')
#             low_price = p.get('low')
#
#             # 原始代码中有随机偏移，但在独立算法中通常不建议，
#             # 这里直接使用形态的起止时间戳，如果需要随机偏移应由外部可视化逻辑处理。
#
#             formatted_list.append({
#                 "time": [start_ts, end_ts],
#                 "leftTop": {
#                     "time": start_ts,
#                     "price": high_price
#                 },
#                 "rigthBottom": {
#                     "time": end_ts,
#                     "price": low_price
#                 },
#                 "value": p.get('value')  # 添加形态类型
#             })
#         return formatted_list

class WMPatternRecognizer:
    """
    负责识别M和W形态的独立算法类。
    """

    def __init__(self):
        self.detected_patterns = []  # 存储M/W形态结果
        self._last_processed_zigzag_len = 0  # 跟踪已处理的zigzag点数量，避免重复判断
        self.zigzag_points = []
        self.maybe_detected_patterns = []  # 存储可能的M/W形态结果
        self.maybe_w = []
        self.maybe_m = []
        self.m_zigzag_points = []
        self.w_zigzag_points = []

        self.all_5point_list = []

        self.none_patterns = []




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
        if len(zigzag_points) >= 5 :
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

        con1 = fri['price'] < thi['price'] < fou['price']< sec['price']
        con2 = (thi['index'] - fri['index']) > 20
        con5 = True
        if self.maybe_detected_patterns and zigzag_points[2]['timestamp'] == self.maybe_detected_patterns[-1]['timestamp']:
            con5 = False

        if con1 and con2 and con5:
            points_data = [
                {
                    "timestamp": point['timestamp'],
                    "kline_data": point  # 包含kLineId、price、index等完整数据
                }
                for point in zigzag_points
            ]
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
            self.maybe_m.append({
                'points': points_data,
                "timestamp": zigzag_points[2]['timestamp'],
                "price": zigzag_points[2]['price'],
                "four_price": zigzag_points[3]['price'],
                "two_price": zigzag_points[1]['price'],
                "value": "可能M形态",
                "start": zigzag_points[0]['timestamp'],
                "start_two": zigzag_points[1]['timestamp'],
                "start_third": zigzag_points[2]['timestamp'],
                "start_four": zigzag_points[3]['timestamp'],
                "end": zigzag_points[-1]['timestamp'],
                "kLineId": zigzag_points[2]['kLineId'],
                "kLineId_3": zigzag_points[3]['kLineId'],
                "start_timestamp": zigzag_points[0]['timestamp'],
                "end_timestamp": zigzag_points[-1]['timestamp']
            })
            return True
        else:
            return False

    def _maybe_w_pattern(self, zigzag_points):
        fri = zigzag_points[0]
        sec = zigzag_points[1]
        thi = zigzag_points[2]
        fou = zigzag_points[3]

        con1 = sec['price'] < fou['price'] < thi['price']< fri['price']

        con2 = (thi['index'] - fri['index']) > 20

        con5 = True
        if self.maybe_detected_patterns and zigzag_points[2]['timestamp'] == self.maybe_detected_patterns[-1]['timestamp']:
            con5 = False

        if con1 and con2 and con5:
            points_data = [
                {
                    "timestamp": point['timestamp'],
                    "kline_data": point  # 包含kLineId、price、index等完整数据
                }
                for point in zigzag_points
            ]
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
            self.maybe_w.append({
                'points': points_data,
                "kLineId": zigzag_points[2]['kLineId'],
                "timestamp": zigzag_points[2]['timestamp'],
                "price": zigzag_points[2]['price'],
                "four_price": zigzag_points[3]['price'],
                "two_price": zigzag_points[1]['price'],
                "value": "可能W形态",
                "start": zigzag_points[0]['timestamp'],
                "start_two": zigzag_points[1]['timestamp'],
                "start_third": zigzag_points[2]['timestamp'],
                "start_four": zigzag_points[3]['timestamp'],
                "end": zigzag_points[3]['timestamp'],
                "kLineId_3": zigzag_points[3]['kLineId'],
                "start_timestamp": zigzag_points[0]['timestamp'],
                "end_timestamp": zigzag_points[-1]['timestamp'],
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
                "leftTop_price": max(zigzag_points[1]['price'], zigzag_points[3]['price']),
                "rigthBottom_price": min(zigzag_points[0]['price'], zigzag_points[4]['price']),
            })
            self.m_zigzag_points.append(zigzag_points[-5:])


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
                "leftTop_price": max(zigzag_points[0]['price'], zigzag_points[4]['price']),
                "rigthBottom_price": min(zigzag_points[1]['price'], zigzag_points[3]['price'])
            })
            self.w_zigzag_points.append(zigzag_points[-5:])

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

    def get_maybe_detected_patterns(self):
        return self.maybe_detected_patterns

    def get_maybe_m_patterns(self):
        return self.maybe_m

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