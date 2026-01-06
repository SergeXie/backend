import pandas as pd
import numpy as np
import math
from dataclasses import dataclass
from typing import List, Dict, Optional
from utils.module.point import ZigZagPoint, ZigZagPointManager

# @dataclass
# class ZigZagPoint:
#     """ZigZag转折点数据类"""
#     kLineId: str  # K线唯一标识
#     timestamp: int  # 时间戳（毫秒/秒）
#     price: float  # 转折点价格
#     index: int  # 内部索引
#     high: float  # K线最高价
#     low: float  # K线最低价
#     close: float  # K线收盘价
#     open: float  # K线开盘价
#
#     @property
#     def hloc(self) -> tuple:
#         """返回hloc元组"""
#         return (self.high, self.low, self.close, self.open)
#
#     def to_dict(self) -> dict:
#         """转换为字典格式"""
#         return {
#             "kLineId": self.kLineId,
#             "timestamp": self.timestamp,
#             "price": self.price,
#             "index": self.index,
#             "high": self.high,
#             "low": self.low,
#             "close": self.close,
#             "open": self.open,
#             "hloc": self.hloc
#         }
#
#
# class ZigZagPointManager:
#     """ZigZag转折点管理器"""
#
#     def __init__(self):
#         self._points: List[ZigZagPoint] = []
#
#     @property
#     def points(self) -> List[ZigZagPoint]:
#         """获取所有转折点（只读）"""
#         return self._points.copy()
#
#     @property
#     def last_point(self) -> Optional[ZigZagPoint]:
#         """获取最后一个转折点"""
#         return self._points[-1] if self._points else None
#
#     @property
#     def count(self) -> int:
#         """获取转折点数量"""
#         return len(self._points)
#
#     def add_point(self, point: ZigZagPoint) -> None:
#         """添加新的转折点"""
#         self._points.append(point)
#
#     def remove_last_point(self) -> Optional[ZigZagPoint]:
#         """移除最后一个转折点并返回"""
#         if self._points:
#             return self._points.pop()
#         return None
#
#     def clear(self) -> None:
#         """清空所有转折点"""
#         self._points.clear()
#
#     def get_points_as_dicts(self) -> List[dict]:
#         """以字典列表形式返回所有转折点"""
#         return [point.to_dict() for point in self._points]
#
#     def get_point_by_index(self, index: int) -> Optional[ZigZagPoint]:
#         """通过内部索引查找转折点"""
#         for point in self._points:
#             if point.index == index:
#                 return point
#         return None
#
#     def get_points_in_time_range(self, start_ts: int, end_ts: int) -> List[ZigZagPoint]:
#         """获取指定时间范围内的转折点"""
#         return [
#             point for point in self._points
#             if start_ts <= point.timestamp <= end_ts
#         ]


class ZigZagCalculator:
    """
    负责计算ZigZag指标的独立算法类。
    """

    def __init__(self, inp_depth: int = 12):
        self.inp_depth = inp_depth

        # 算法状态变量
        self.whatlookfor = 0  # 0=寻找初始极值，1=寻找高点，-1=寻找低点
        self.last_low_val = 0.0  # 记录上一个确定的ZigZag低点值
        self.last_high_val = 0.0  # 记录上一个确定的ZigZag高点值

        # 使用转折点管理器替代原始列表
        self.point_manager = ZigZagPointManager()

        # 缓存最近inp_depth的高低点值
        self.recent_highs_buffer: List[float] = []
        self.recent_lows_buffer: List[float] = []

        # 辅助映射，用于记录K线处理进度和时间戳
        self._kline_index_counter = 0  # 模拟Backtrader的len(self)，从1开始计数
        self.dict_index2ts: Dict[int, int] = {}  # 映射内部索引到时间戳
        self.dict_ts2index: Dict[int, int] = {}  # 映射时间戳到内部索引

    def _i_lowest(self, data_series: List[float]) -> float:
        """寻找指定序列中的最低值"""
        if not data_series:
            return 0.0
        return np.min(data_series)

    def _i_highest(self, data_series: List[float]) -> float:
        """寻找指定序列中的最高值"""
        if not data_series:
            return 0.0
        return np.max(data_series)

    def process_kline(self, kline_data: dict) -> bool:
        """
        处理单根K线数据，更新ZigZag状态。

        Args:
            kline_data (dict): 包含 'kLineId', 'timestamp', 'high', 'low', 'close', 'open' 的字典。
        Returns:
            bool: 如果有新的ZigZag点产生或上一个ZigZag点被修正，返回True，否则返回False。
        """
        # 提取K线数据
        current_kline_id = kline_data['kLineId']
        timestamp = kline_data['timestamp']
        current_high = kline_data['high']
        current_low = kline_data['low']
        current_close = kline_data['close']
        current_open = kline_data['open']

        # 更新索引和时间戳映射
        self._kline_index_counter += 1
        current_index = self._kline_index_counter
        self.dict_index2ts[current_index] = timestamp
        self.dict_ts2index[timestamp] = current_index

        # 更新最近高低点缓存
        self.recent_highs_buffer.append(current_high)
        self.recent_lows_buffer.append(current_low)

        # 维护缓存长度
        if len(self.recent_highs_buffer) > self.inp_depth:
            self.recent_highs_buffer.pop(0)
            self.recent_lows_buffer.pop(0)

        # 数据长度不足时，不进行ZigZag计算
        if len(self.recent_highs_buffer) < self.inp_depth:
            return False

        # --- 局部极值判断 ---
        extremum_low_in_depth = self._i_lowest(self.recent_lows_buffer)
        is_current_low_extremum = (current_low == extremum_low_in_depth)

        extremum_high_in_depth = self._i_highest(self.recent_highs_buffer)
        is_current_high_extremum = (current_high == extremum_high_in_depth)

        # 记录本次处理是否产生了新的ZigZag点
        new_zigzag_point_generated = False

        # --- 生成ZigZag连线 ---
        if self.whatlookfor == 0:  # 寻找初始极值
            if is_current_high_extremum:
                self.last_high_val = current_high
                self.whatlookfor = -1  # 接下来找低点

                # 创建并添加新的转折点
                new_point = ZigZagPoint(
                    kLineId=current_kline_id,
                    timestamp=timestamp,
                    price=self.last_high_val,
                    index=current_index,
                    high=current_high,
                    low=current_low,
                    close=current_close,
                    open=current_open
                )
                self.point_manager.add_point(new_point)
                new_zigzag_point_generated = True

            elif is_current_low_extremum:
                self.last_low_val = current_low
                self.whatlookfor = 1  # 接下来找高点

                # 创建并添加新的转折点
                new_point = ZigZagPoint(
                    kLineId=current_kline_id,
                    timestamp=timestamp,
                    price=self.last_low_val,
                    index=current_index,
                    high=current_high,
                    low=current_low,
                    close=current_close,
                    open=current_open
                )
                self.point_manager.add_point(new_point)
                new_zigzag_point_generated = True

        elif self.whatlookfor == 1:  # 当前趋势向上，寻找高点或更低低点
            # 延续上升趋势：找到更低的低点
            if is_current_low_extremum and current_low < self.last_low_val and not is_current_high_extremum:
                self.last_low_val = current_low
                # 移除最后一个点并添加新点
                self.point_manager.remove_last_point()

                new_point = ZigZagPoint(
                    kLineId=current_kline_id,
                    timestamp=timestamp,
                    price=self.last_low_val,
                    index=current_index,
                    high=current_high,
                    low=current_low,
                    close=current_close,
                    open=current_open
                )
                self.point_manager.add_point(new_point)
                new_zigzag_point_generated = True

            # 趋势反转：找到高点
            elif is_current_high_extremum and not is_current_low_extremum:
                self.last_high_val = current_high
                self.whatlookfor = -1  # 趋势转为向下

                new_point = ZigZagPoint(
                    kLineId=current_kline_id,
                    timestamp=timestamp,
                    price=self.last_high_val,
                    index=current_index,
                    high=current_high,
                    low=current_low,
                    close=current_close,
                    open=current_open
                )
                self.point_manager.add_point(new_point)
                new_zigzag_point_generated = True

        elif self.whatlookfor == -1:  # 当前趋势向下，寻找低点或更高高点
            # 延续下降趋势：找到更高的高点
            if is_current_high_extremum and current_high > self.last_high_val and not is_current_low_extremum:
                self.last_high_val = current_high
                # 移除最后一个点并添加新点
                self.point_manager.remove_last_point()

                new_point = ZigZagPoint(
                    kLineId=current_kline_id,
                    timestamp=timestamp,
                    price=self.last_high_val,
                    index=current_index,
                    high=current_high,
                    low=current_low,
                    close=current_close,
                    open=current_open
                )
                self.point_manager.add_point(new_point)
                new_zigzag_point_generated = True

            # 趋势反转：找到低点
            elif is_current_low_extremum and not is_current_high_extremum:
                self.last_low_val = current_low
                self.whatlookfor = 1  # 趋势转为向上

                new_point = ZigZagPoint(
                    kLineId=current_kline_id,
                    timestamp=timestamp,
                    price=self.last_low_val,
                    index=current_index,
                    high=current_high,
                    low=current_low,
                    close=current_close,
                    open=current_open
                )
                self.point_manager.add_point(new_point)
                new_zigzag_point_generated = True

        return new_zigzag_point_generated

    def get_zigzag_points(self, as_dict: bool = True) -> List:
        """
        返回当前计算出的所有ZigZag转折点列表。

        Args:
            as_dict: 是否以字典形式返回，False则返回ZigZagPoint对象列表
        """
        if as_dict:
            return self.point_manager.get_points_as_dicts()
        return self.point_manager.points

    def get_index_timestamp_maps(self) -> tuple[Dict[int, int], Dict[int, int]]:
        """返回索引到时间戳的映射，供形态识别使用。"""
        return self.dict_index2ts, self.dict_ts2index


# 使用示例
if __name__ == "__main__":
    # 创建计算器实例
    calculator = ZigZagCalculator(inp_depth=5)

    # 模拟K线数据
    test_klines = [
        {"kLineId": "1", "timestamp": 1735689600000, "high": 100, "low": 90, "close": 95, "open": 98},
        {"kLineId": "2", "timestamp": 1735693200000, "high": 105, "low": 92, "close": 102, "open": 95},
        {"kLineId": "3", "timestamp": 1735696800000, "high": 108, "low": 100, "close": 105, "open": 102},
        {"kLineId": "4", "timestamp": 1735700400000, "high": 106, "low": 98, "close": 100, "open": 105},
        {"kLineId": "5", "timestamp": 1735704000000, "high": 110, "low": 95, "close": 108, "open": 100},
        {"kLineId": "6", "timestamp": 1735707600000, "high": 109, "low": 102, "close": 105, "open": 108},
    ]

    # 处理K线数据
    for kline in test_klines:
        calculator.process_kline(kline)

    # 获取转折点
    points = calculator.get_zigzag_points(as_dict=True)
    print("ZigZag转折点（字典形式）:")
    for point in points:
        print(point)

    # 获取ZigZagPoint对象形式的转折点
    point_objects = calculator.get_zigzag_points(as_dict=False)
    print("\nZigZag转折点（对象形式）:")
    for point in point_objects:
        print(f"价格: {point.price}, 时间戳: {point.timestamp}, HLOC: {point.hloc}")

    # 使用点管理器的其他功能
    print(f"\n转折点总数: {calculator.point_manager.count}")
    if calculator.point_manager.last_point:
        print(f"最后一个转折点价格: {calculator.point_manager.last_point.price}")

    # 按时间范围筛选
    filtered_points = calculator.point_manager.get_points_in_time_range(1735689600000, 1735704000000)
    print(f"\n指定时间范围内的转折点数量: {len(filtered_points)}")