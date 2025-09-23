import datetime
from enum import IntEnum
import backtrader as bt
import numpy as np
from utils.time_utils import LZSDTimeUtils


class PeakTroughType(IntEnum):
    Normal = 0
    Peak = 1
    Trough = -1
    def __str__(self):
        if self == PeakTroughType.Normal:
            return ""
        elif self == PeakTroughType.Peak:
            return "顶"
        elif self == PeakTroughType.Trough:
            return "底"

class PTPoint:
    def __init__(self):
        self.k_center_ts:datetime = None
        self.k_right_ts:datetime = None
        self.k_center_low:float = 0
        self.k_center_high:float = 0
        self.type:PeakTroughType = PeakTroughType.Normal

    def __str__(self):
        return f"type:{str(self.type)} center:{LZSDTimeUtils.fmt_iso(self.k_center_ts)} r:{LZSDTimeUtils.fmt_iso(self.k_right_ts)}"

class PeakTroughIndicator(bt.Indicator):
    """
    峰值连线指标
    """
    """
    pt_r 右线所在形态 1或者-1
    pt_center 右线形态所属的中线k线unix时间戳
    """
    lines = ('pt_r', 'pt_center', 'pt_center_price', 'test_data')
    params = (
        ('min_peak_trough_diff', 1.0),  # 中线顶底价差最小值
        ('is_k_right_merge', True),  # 右线是否合并
    )

    # 指标的绘图信息
    plotinfo = dict(
        subplot=False,  # 在主图表上绘制
        plot=True,  # 确保绘制
        plotname='LZSD PeakTrough',  # 绘制名称
    )

    # 精细控制每条线的绘图
    plotlines = dict(
        test_data=dict(color='blue', linestyle='-')
    )

    MIN_K_LINE = 3

    def __init__(self):
        self.last_pt = None
        self.last_seek_ts = None
        self.current_pt_type = PeakTroughType.Normal


    def _find_pt(self, start_pos:int, seek_type:PeakTroughType)->PTPoint:
        while True:

            end_pos = -2
            for i in range(start_pos, end_pos + 1, 1):
                center_k_index = i + 1

                if seek_type == PeakTroughType.Peak:
                    if self.data.high[center_k_index] > self.data.high[center_k_index - 1] and self.data.high[center_k_index] > self.data.high[center_k_index + 1]:
                        center_price = self.data.low[center_k_index]

                        for j in range(center_k_index + 1, 1, 1):
                            if self.data.high[j] > self.data.high[center_k_index]:
                                break

                            r_price = self.data.close[j]
                            if r_price <= center_price and j == 0:
                                pt = PTPoint()
                                pt.type = PeakTroughType.Peak
                                pt.k_center_ts = self.data.datetime.datetime(center_k_index)
                                pt.k_right_ts = self.data.datetime.datetime(j)
                                pt.k_center_low = self.data.low[center_k_index]
                                pt.k_center_high = self.data.high[center_k_index]
                                return pt

                            center_price = max(center_price, self.data.low[j])

                elif seek_type == PeakTroughType.Trough:
                    if self.data.low[center_k_index] < self.data.low[center_k_index - 1] and self.data.low[
                        center_k_index] < self.data.low[center_k_index + 1]:
                        center_price = self.data.high[center_k_index]

                        for j in range(center_k_index + 1, 1, 1):
                            if self.data.low[j] < self.data.low[center_k_index]:
                                break

                            r_price = self.data.close[j]
                            if r_price >= center_price and j == 0:
                                pt = PTPoint()
                                pt.type = PeakTroughType.Trough
                                pt.k_center_ts = self.data.datetime.datetime(center_k_index)
                                pt.k_right_ts = self.data.datetime.datetime(j)
                                pt.k_center_low = self.data.low[center_k_index]
                                pt.k_center_high = self.data.high[center_k_index]
                                return pt

                            center_price = min(center_price, self.data.high[j])

            break

        return None

    def _index_of_ts(self, ts)->int:
        for i in range(0, 0 - len(self), -1):
            dt = self.data.datetime.datetime(i)
            if dt == ts:
                return i
        return None

    def _set_pt(self, pt:PTPoint):
        k_center_index = self._index_of_ts(pt.k_center_ts)
        k_right_index = self._index_of_ts(pt.k_right_ts)
        if k_center_index is not None:
            if k_right_index is not None:
                self.pt_r[k_right_index] = pt.type
                self.pt_center[k_right_index] = self.data.klineId[k_center_index]
                self.pt_center_price[k_center_index] = pt.k_center_high if pt.type == PeakTroughType.Peak else pt.k_center_low

    def _cancel_pt(self, pt:PTPoint):
        if pt is not None:
            k_center_index = self._index_of_ts(pt.k_center_ts)
            k_right_index = self._index_of_ts(pt.k_right_ts)
            if k_center_index is not None:
                if k_right_index is not None:
                    self.pt_r[k_right_index] = 0
                    self.pt_center_price[k_center_index] = np.nan

    def _is_matched(self, pt1, pt2):
        while True:
            if pt1.type == pt2.type:
                break

            pt1_center_k_index = self._index_of_ts(pt1.k_center_ts)
            pt2_center_k_index = self._index_of_ts(pt2.k_center_ts)
            pt1_right_k_index = self._index_of_ts(pt1.k_right_ts)

            """
            中线之间k线数量必须不小于2
            """
            if (pt2_center_k_index - pt1_right_k_index) < 2:
                break

            """
            中线价差满足条件
            """
            if self.p.min_peak_trough_diff > 0:
                if pt1.type == PeakTroughType.Peak:
                    val1 = self.data.high[pt2_center_k_index]
                    val2 = self.data.low[pt1_center_k_index]
                else:
                    val2 = self.data.low[pt2_center_k_index]
                    val1 = self.data.high[pt1_center_k_index]
                if (val2 - val1) < self.p.min_peak_trough_diff:
                    break

            return True

        return False

    def _reset_pt(self, pt:PTPoint):
        self._set_pt(pt)
        self.last_pt = pt
        self.last_seek_ts = pt.k_right_ts

    def next(self):
        start_pos = 1 - len(self)
        if self.last_pt:
            start_pos = self._index_of_ts(self.last_pt.k_right_ts) + 1

        pt_trough = self._find_pt(start_pos, PeakTroughType.Trough)
        pt_peak = self._find_pt(start_pos, PeakTroughType.Peak)

        if not pt_trough:
            if not pt_peak:
                return

        flag = False

        current_pt_type = PeakTroughType.Normal
        if self.last_pt:
            current_pt_type = self.last_pt.type

        if current_pt_type == PeakTroughType.Normal:
            if pt_peak:
                self.last_pt = pt_peak
                self.current_pt_type = pt_peak.type
                flag = True
            elif pt_trough:
                self.last_pt = pt_trough
                self.current_pt_type = pt_trough.type
                flag = True

        elif current_pt_type == PeakTroughType.Peak:
            if pt_trough:
                ret = self._is_matched(self.last_pt, pt_trough)
                if ret:
                    self.last_pt = pt_trough
                    flag = True

            if not flag:
                if pt_peak:
                    if pt_peak.k_center_high > self.last_pt.k_center_high:
                        self.last_pt = pt_peak
                        self._cancel_pt(self.last_pt)
                        flag = True

        elif current_pt_type == PeakTroughType.Trough:
            if pt_peak:
                ret = self._is_matched(self.last_pt, pt_peak)
                if ret:
                    self.last_pt = pt_peak
                    flag = True

            if not flag:
                if pt_trough:
                    if pt_trough.k_center_low < self.last_pt.k_center_low:
                        self.last_pt = pt_trough
                        self._cancel_pt(self.last_pt)
                        flag = True

        if flag:
            self._set_pt(self.last_pt)
            print("new pt:" + str(self.last_pt))