"""
用在wm指标中，对峰值连线创建的顶底，整理为专用的point格式
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
from utils.indicators.peak_trough import PeakTroughType
from utils.module.point import ZigZagPoint, ZigZagPointManager

@dataclass
class PeakTroughPoint:
    """ZigZag转折点数据类"""
    kLineId: str  # K线唯一标识
    timestamp: int  # 时间戳（毫秒/秒）
    price: float  # 转折点价格
    index: int  # 内部索引
    high: float  # K线最高价
    low: float  # K线最低价
    close: float  # K线收盘价
    open: float  # K线开盘价

    @property
    def hloc(self) -> tuple:
        """返回hloc元组"""
        return (self.high, self.low, self.close, self.open)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "kLineId": self.kLineId,
            "timestamp": self.timestamp,
            "price": self.price,
            "index": self.index,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "open": self.open,
            "hloc": self.hloc
        }



class PeakTroughPointManager:
    """PK转折点管理器"""

    def __init__(self):
        self._points: List[ZigZagPoint] = []

    @property
    def points(self) -> List[ZigZagPoint]:
        """获取所有转折点（只读）"""
        return self._points.copy()

    @property
    def last_point(self) -> Optional[ZigZagPoint]:
        """获取最后一个转折点"""
        return self._points[-1] if self._points else None

    @property
    def count(self) -> int:
        """获取转折点数量"""
        return len(self._points)

    def add_point(self, point: ZigZagPoint) -> None:
        """添加新的转折点"""
        self._points.append(point)

    def remove_last_point(self) -> Optional[ZigZagPoint]:
        """移除最后一个转折点并返回"""
        if self._points:
            return self._points.pop()
        return None

    def clear(self) -> None:
        """清空所有转折点"""
        self._points.clear()

    def get_points_as_dicts(self) -> List[dict]:
        """以字典列表形式返回所有转折点"""
        return [point.to_dict() for point in self._points]

    def get_point_by_index(self, index: int) -> Optional[ZigZagPoint]:
        """通过内部索引查找转折点"""
        for point in self._points:
            if point.index == index:
                return point
        return None

    def get_points_in_time_range(self, start_ts: int, end_ts: int) -> List[ZigZagPoint]:
        """获取指定时间范围内的转折点"""
        return [
            point for point in self._points
            if start_ts <= point.timestamp <= end_ts
        ]


class PeakTroughPointCalculator:

    def __init__(self):
        # 使用转折点管理器替代原始列表
        self.point_manager = PeakTroughPointManager()
        self._kline_index_counter = 0
        self.last_pt_type = None

    def process_point(self, point: Dict, pt_type: PeakTroughType) -> None:
        # print(pt_type,pt_type == PeakTroughType.Peak, pt_type == PeakTroughType.Trough, point)
        current_kline_id = point['kLineId']
        timestamp = point['timestamp']
        current_high = point['high']
        current_low = point['low']
        current_close = point['close']
        current_open = point['open']

        self._kline_index_counter += 1
        current_index = self._kline_index_counter
        if pt_type == PeakTroughType.Normal:
            return


        if pt_type != self.last_pt_type:
            current_price = current_high if pt_type == PeakTroughType.Peak else current_low
            new_point = ZigZagPoint(
                kLineId=current_kline_id,
                timestamp=timestamp,
                price=current_price,
                index=current_index,
                high=current_high,
                low=current_low,
                close=current_close,
                open=current_open,
                hloc=(current_high, current_low, current_close, current_open)
            )
            self.point_manager.add_point(new_point)
        if pt_type == self.last_pt_type:
            self.point_manager.remove_last_point()
            current_price = current_high if pt_type == PeakTroughType.Peak else current_low
            new_point = ZigZagPoint(
                kLineId=current_kline_id,
                timestamp=timestamp,
                price=current_price,
                index=current_index,
                high=current_high,
                low=current_low,
                close=current_close,
                open=current_open,
                hloc=(current_high, current_low, current_close, current_open)
            )
            self.point_manager.add_point(new_point)

        self.last_pt_type = pt_type

    def get_PeakTrough_points(self, as_dict: bool = True) -> List:
        if as_dict:
            return self.point_manager.get_points_as_dicts()
        return self.point_manager.points




