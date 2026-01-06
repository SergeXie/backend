from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class ZigZagPoint:
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


class ZigZagPointManager:
    """ZigZag转折点管理器"""

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