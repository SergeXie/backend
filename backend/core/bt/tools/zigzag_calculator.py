import pandas as pd
import numpy as np
import math


class ZigZagCalculator:
    """
    负责计算ZigZag指标的独立算法类。
    """

    def __init__(self, inp_depth=12):
        self.inp_depth = inp_depth

        # 算法状态变量
        self.whatlookfor = 0  # 0=寻找初始极值，1=寻找高点，-1=寻找低点
        self.last_low_val = 0.0  # 记录上一个确定的ZigZag低点值
        self.last_high_val = 0.0  # 记录上一个确定的ZigZag高点值
        self.zigzag_points = []  # 存储ZigZag转折点 {kLineId, timestamp, price, index}

        # 缓存最近inp_depth的高低点值
        self.recent_highs_buffer = []
        self.recent_lows_buffer = []

        # 辅助映射，用于记录K线处理进度和时间戳
        self._kline_index_counter = 0  # 模拟Backtrader的len(self)，从1开始计数
        self.dict_index2ts = {}  # 映射内部索引到时间戳
        self.dict_ts2index = {}  # 映射时间戳到内部索引

    def _i_lowest(self, data_series):
        """寻找指定序列中的最低值"""
        if not data_series:
            return 0.0  # 或抛出错误，取决于预期行为
        return np.min(data_series)

    def _i_highest(self, data_series):
        """寻找指定序列中的最高值"""
        if not data_series:
            return 0.0  # 或抛出错误
        return np.max(data_series)

    def process_kline(self, kline_data):
        """
        处理单根K线数据，更新ZigZag状态。

        Args:
            kline_data (dict): 包含 'kLineId', 'timestamp', 'high', 'low', 'close' 的字典。
        Returns:
            bool: 如果有新的ZigZag点产生或上一个ZigZag点被修正，返回True，否则返回False。
        """
        current_kline_id = kline_data['kLineId']
        timestamp = kline_data['timestamp']
        current_high = kline_data['high']
        current_low = kline_data['low']
        current_close = kline_data['close']
        current_open = kline_data['open']

        self._kline_index_counter += 1
        current_index = self._kline_index_counter
        self.dict_index2ts[current_index] = timestamp
        self.dict_ts2index[timestamp] = current_index

        # 更新最近高低点缓存
        self.recent_highs_buffer.append(current_high)
        self.recent_lows_buffer.append(current_low)

        if len(self.recent_highs_buffer) > self.inp_depth:
            self.recent_highs_buffer.pop(0)
            self.recent_lows_buffer.pop(0)

        # 数据长度不足时，不进行ZigZag计算
        if len(self.recent_highs_buffer) < self.inp_depth:
            return False

        # --- 局部极值判断 ---
        is_current_low_extremum = False
        extremum_low_in_depth = self._i_lowest(self.recent_lows_buffer)
        if current_low == extremum_low_in_depth:
            is_current_low_extremum = True

        is_current_high_extremum = False
        extremum_high_in_depth = self._i_highest(self.recent_highs_buffer)
        if current_high == extremum_high_in_depth:
            is_current_high_extremum = True

        # 记录本次处理是否产生了新的ZigZag点
        new_zigzag_point_generated = False

        # --- 生成ZigZag连线 ---
        if self.whatlookfor == 0:  # 寻找初始极值
            if is_current_high_extremum:
                self.last_high_val = current_high
                self.whatlookfor = -1  # 接下来找低点
                self.zigzag_points.append({
                    "kLineId": current_kline_id,
                    "timestamp": timestamp,
                    "price": self.last_high_val,
                    "index": current_index,
                    "hloc": [current_high, current_low, current_close, current_open],
                })
                new_zigzag_point_generated = True
            elif is_current_low_extremum:
                self.last_low_val = current_low
                self.whatlookfor = 1  # 接下来找高点
                self.zigzag_points.append({
                    "kLineId": current_kline_id,
                    "timestamp": timestamp,
                    "price": self.last_low_val,
                    "index": current_index,
                    "hloc": [current_high, current_low, current_close, current_open],

                })
                new_zigzag_point_generated = True

        elif self.whatlookfor == 1:  # 当前趋势向上，寻找高点或更低低点
            # 延续上升趋势：找到更低的低点 (原始代码逻辑)
            if is_current_low_extremum and current_low < self.last_low_val and not is_current_high_extremum:
                self.last_low_val = current_low
                if self.zigzag_points:
                    self.zigzag_points.pop(-1)
                self.zigzag_points.append({
                    "kLineId": current_kline_id,
                    "timestamp": timestamp,
                    "price": self.last_low_val,
                    "index": current_index,
                    "hloc": [current_high, current_low, current_close, current_open],
                })
                new_zigzag_point_generated = True
            # 趋势反转：找到高点
            elif is_current_high_extremum and not is_current_low_extremum:
                self.last_high_val = current_high
                self.whatlookfor = -1  # 趋势转为向下
                self.zigzag_points.append({
                    "kLineId": current_kline_id,
                    "timestamp": timestamp,
                    "price": self.last_high_val,
                    "index": current_index,
                    "hloc": [current_high, current_low, current_close, current_open],
                })
                new_zigzag_point_generated = True

        elif self.whatlookfor == -1:  # 当前趋势向下，寻找低点或更高高点
            # 延续下降趋势：找到更高的高点 (原始代码逻辑)
            if is_current_high_extremum and current_high > self.last_high_val and not is_current_low_extremum:
                self.last_high_val = current_high
                if self.zigzag_points:
                    self.zigzag_points.pop(-1)
                self.zigzag_points.append({
                    "kLineId": current_kline_id,
                    "timestamp": timestamp,
                    "price": self.last_high_val,
                    "index": current_index,
                    "hloc": [current_high, current_low, current_close, current_open],
                })
                new_zigzag_point_generated = True
            # 趋势反转：找到低点
            elif is_current_low_extremum and not is_current_high_extremum:
                self.last_low_val = current_low
                self.whatlookfor = 1  # 趋势转为向上
                self.zigzag_points.append({
                    "kLineId": current_kline_id,
                    "timestamp": timestamp,
                    "price": self.last_low_val,
                    "index": current_index,
                    "hloc": [current_high, current_low, current_close, current_open],
                })
                new_zigzag_point_generated = True

        return new_zigzag_point_generated  # 返回是否产生了新的zigzag点

    def get_zigzag_points(self):
        """返回当前计算出的所有ZigZag转折点列表。"""
        return self.zigzag_points

    def get_index_timestamp_maps(self):
        """返回索引到时间戳的映射，供形态识别使用。"""
        return self.dict_index2ts, self.dict_ts2index