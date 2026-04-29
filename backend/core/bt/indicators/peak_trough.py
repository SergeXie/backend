import datetime
from enum import IntEnum
import backtrader as bt
import numpy as np
from typing import List, Dict, Optional
from utils.time_utils import LZSDTimeUtils


# 定义顶底的类型枚举
class PeakTroughType(IntEnum):
    Normal = 0  # 无/普通状态
    Peak = 1  # 顶（波峰）
    Trough = -1  # 底（波谷）

    def __str__(self):
        if self == PeakTroughType.Normal:
            return ""
        elif self == PeakTroughType.Peak:
            return "顶"
        elif self == PeakTroughType.Trough:
            return "底"


# 定义一个类来存储找到的顶或底的信息
class PTPoint:
    def __init__(self):
        self.k_center_ts: datetime = None  # 顶或底那一根K线的时间
        self.k_right_ts: datetime = None  # 确认该形态完成的那一根右侧K线的时间
        self.k_center_low: float = 0  # 中心K线的最低价
        self.k_center_high: float = 0  # 中心K线的最高价
        self.type: PeakTroughType = PeakTroughType.Normal  # 类型：顶或底

    def __str__(self):
        return f"type:{str(self.type)} center:{LZSDTimeUtils.fmt_iso(self.k_center_ts)} r:{LZSDTimeUtils.fmt_iso(self.k_right_ts)}"


class PeakTroughIndicator(bt.Indicator):
    """
    峰值连线指标 (自定义ZigZag风格指标)
    """
    """
    Line输出说明:
    pt_r: 标记在确认K线（右线）上，值为 1(顶) 或 -1(底)
    pt_center: 记录对应的中心K线（极值点）的ID（通常是时间戳或索引）
    pt_center_price: 记录中心K线的极值价格（顶为High，底为Low）
    """
    lines = ('pt_r', 'pt_center', 'pt_center_price', 'test_data')

    params = (
        ('min_peak_trough_diff', 1.0),  # 过滤参数：相邻顶底之间的最小价差
        ('is_k_right_merge', True),  # 参数目前在逻辑中似乎未被直接使用
    )
    #
    # # 指标的绘图信息
    # plotinfo = dict(
    #     subplot=False,  # 设置为 False，表示直接画在主图（K线图）上
    #     plot=True,  # 确保绘制
    #     plotname='LZSD PeakTrough',  # 指标显示的名称
    # )
    #
    # # 精细控制每条线的绘图样式
    # plotlines = dict(
    #     test_data=dict(color='blue', linestyle='-')
    # )
    #
    MIN_K_LINE = 3  # 构成顶底分型所需的最小K线数 (左1 + 中1 + 右1)

    def __init__(self):
        self.last_pt = None  # 记录上一个确定的顶或底对象
        self.last_seek_ts = None  # 上次搜索的时间戳
        self.current_pt_type = PeakTroughType.Normal  # 当前正在寻找相反方向的状态
        self._list_pt = []

    def _find_pt(self, start_pos: int, seek_type: PeakTroughType) -> PTPoint:
        """
        核心查找逻辑：在历史K线中寻找符合条件的顶或底
        start_pos: 搜索起始位置（相对于当前的索引，通常是负数）
        seek_type: 要寻找的是顶(Peak)还是底(Trough)
        """
        while True:
            # 遍历从 start_pos 到 -2 的位置（因为需要 i+1 作为右边K线，所以只能遍历到 -2）
            # i 是分型的左边K线索引，center_k_index 是分型的中间K线（极值点）
            end_pos = -2
            for i in range(start_pos, end_pos + 1, 1):
                center_k_index = i + 1  # 潜在的顶或底的K线索引

                # === 寻找“顶”的逻辑 ===
                if seek_type == PeakTroughType.Peak:
                    # 1. 基础形态判断：中间High > 左边High 且 中间High > 右边High
                    if self.data.high[center_k_index] > self.data.high[center_k_index - 1] and self.data.high[
                        center_k_index] > self.data.high[center_k_index + 1]:
                        center_price = self.data.low[center_k_index]  # 初始确认阈值设为顶部的Low

                        # 2. 右侧确认逻辑：从顶的右边开始向当前时间遍历
                        for j in range(center_k_index + 1, 1, 1):  # j 是从顶右侧一直到当前K线(0)
                            # 如果中间出现了比当前顶更高的高点，说明这个顶无效，直接跳出
                            if self.data.high[j] > self.data.high[center_k_index]:
                                break

                            r_price = self.data.close[j]
                            # 如果收盘价跌破了阈值，并且 j==0 (表示就是当前这根K线确认了形态)
                            if r_price <= center_price and j == 0:
                                pt = PTPoint()
                                pt.type = PeakTroughType.Peak
                                pt.k_center_ts = self.data.datetime.datetime(center_k_index)  # 记录顶的时间
                                pt.k_right_ts = self.data.datetime.datetime(j)  # 记录确认时间(当前)
                                pt.k_center_low = self.data.low[center_k_index]
                                pt.k_center_high = self.data.high[center_k_index]
                                return pt  # 找到顶，返回

                            # 更新阈值：随着时间推移，要求跌破区间内的最高底（这是一种类似移动止损的逻辑，或者寻找颈线）
                            # 注意：这里用 max(low[j]) 意味着确认线在抬高，要求跌得更深才能确认
                            center_price = max(center_price, self.data.low[j])

                # === 寻找“底”的逻辑 (与顶相反) ===
                elif seek_type == PeakTroughType.Trough:
                    # 1. 基础形态判断：中间Low < 左边Low 且 中间Low < 右边Low
                    if self.data.low[center_k_index] < self.data.low[center_k_index - 1] and self.data.low[
                        center_k_index] < self.data.low[center_k_index + 1]:
                        center_price = self.data.high[center_k_index]  # 初始确认阈值设为底部的High

                        # 2. 右侧确认逻辑
                        for j in range(center_k_index + 1, 1, 1):
                            # 如果中间出现了更低的低点，当前底无效
                            if self.data.low[j] < self.data.low[center_k_index]:
                                break

                            r_price = self.data.close[j]
                            # 如果收盘价突破阈值，且是当前K线
                            if r_price >= center_price and j == 0:
                                pt = PTPoint()
                                pt.type = PeakTroughType.Trough
                                pt.k_center_ts = self.data.datetime.datetime(center_k_index)
                                pt.k_right_ts = self.data.datetime.datetime(j)
                                pt.k_center_low = self.data.low[center_k_index]
                                pt.k_center_high = self.data.high[center_k_index]
                                return pt

                            # 更新阈值：确认线在降低，要求涨得更高才能确认
                            center_price = min(center_price, self.data.high[j])

            break  # 遍历完没有找到

        return None

    def _index_of_ts(self, ts) -> int:
        """辅助函数：根据时间戳查找其在当前backtrader数据中的索引(负数)"""
        for i in range(0, 0 - len(self), -1):
            dt = self.data.datetime.datetime(i)
            if dt == ts:
                return i
        return None

    def _set_pt(self, pt: PTPoint):
        """将找到的顶底点写入指标的 lines 中，用于画图或后续策略调用"""
        k_center_index = self._index_of_ts(pt.k_center_ts)
        k_right_index = self._index_of_ts(pt.k_right_ts)
        if k_center_index is not None:
            if k_right_index is not None:
                self.pt_r[k_right_index] = pt.type  # 在确认K线位置标记 1 或 -1
                # 记录中心K线的ID (这里假设klineId存在于data中，否则可能报错，可用datetime代替)
                self.pt_center[k_right_index] = self.data.klineId[k_center_index]
                # 在中心K线位置记录极值价格
                self.pt_center_price[
                    k_center_index] = pt.k_center_high if pt.type == PeakTroughType.Peak else pt.k_center_low

    def _cancel_pt(self, pt: PTPoint):
        """取消一个顶底点（用于更新更高的高点或更低的低点时）"""
        if pt is not None:
            k_center_index = self._index_of_ts(pt.k_center_ts)
            k_right_index = self._index_of_ts(pt.k_right_ts)
            if k_center_index is not None:
                if k_right_index is not None:
                    self.pt_r[k_right_index] = 0  # 重置为0
                    self.pt_center_price[k_center_index] = np.nan  # 清空价格

    def _is_matched(self, pt1, pt2):
        """
        判断两个点是否“匹配”，即是否满足交替和距离限制
        pt1: 上一个点
        pt2: 新发现的点
        """
        while True:
            # 类型必须不同（必须是 顶->底 或 底->顶）
            if pt1.type == pt2.type:
                break

            pt1_center_k_index = self._index_of_ts(pt1.k_center_ts)
            pt2_center_k_index = self._index_of_ts(pt2.k_center_ts)
            pt1_right_k_index = self._index_of_ts(pt1.k_right_ts)

            # 1. 距离限制：新点的中心必须在上一个点的确认线之后至少2根K线
            if (pt2_center_k_index - pt1_right_k_index) < 2:
                break

            # 2. 价差限制：满足最小价差 min_peak_trough_diff
            if self.p.min_peak_trough_diff > 0:
                if pt1.type == PeakTroughType.Peak:
                    # 上个是顶，这次是底：看顶的高点和底的低点之差
                    val1 = self.data.high[pt2_center_k_index]  # 这里似乎写反了或取值逻辑有点特别？通常是 pt1.high - pt2.low
                    # 代码原文逻辑:
                    # val1 = high[新点底] (这很奇怪，底应该看low)
                    # val2 = low[旧点顶] (这也很奇怪，顶应该看high)
                    # *推测作者意图*：可能是想计算某种重叠区域或回撤幅度，但常规逻辑应该是 abs(pt1_price - pt2_price)
                    val1 = self.data.high[pt2_center_k_index]
                    val2 = self.data.low[pt1_center_k_index]
                else:
                    val2 = self.data.low[pt2_center_k_index]
                    val1 = self.data.high[pt1_center_k_index]

                # 计算价差是否足够大
                if (val2 - val1) < self.p.min_peak_trough_diff:
                    break

            return True  # 通过所有检查

        return False

    def _reset_pt(self, pt: PTPoint):
        self._set_pt(pt)
        self.last_pt = pt
        self.last_seek_ts = pt.k_right_ts

    def next(self):
        # 确定搜索的起始位置
        start_pos = 1 - len(self)  # 默认搜索整个加载的数据
        if self.last_pt:
            # 如果已有上一个点，从上一个点确认时间的下一根开始搜
            start_pos = self._index_of_ts(self.last_pt.k_right_ts) + 1

        # 尝试寻找底
        pt_trough = self._find_pt(start_pos, PeakTroughType.Trough)
        # 尝试寻找顶
        pt_peak = self._find_pt(start_pos, PeakTroughType.Peak)

        if not pt_trough and not pt_peak:
            return

        flag = False  # 标记是否有新的点被确认

        current_pt_type = PeakTroughType.Normal
        if self.last_pt:
            current_pt_type = self.last_pt.type
        # === 状态机逻辑 ===

        # 1. 初始状态：还没有找到过任何顶或底
        if current_pt_type == PeakTroughType.Normal:
            if pt_peak:
                self.last_pt = pt_peak
                self.current_pt_type = pt_peak.type
                flag = True
                self._list_pt.append(self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'))
            elif pt_trough:
                self.last_pt = pt_trough
                self.current_pt_type = pt_trough.type
                flag = True
                self._list_pt.append(self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'))

        # 2. 当前状态是“顶”，寻找“底”
        elif current_pt_type == PeakTroughType.Peak:
            # 如果找到了底，且符合匹配条件
            if pt_trough:
                ret = self._is_matched(self.last_pt, pt_trough)
                if ret:
                    self.last_pt = pt_trough
                    flag = True
                    self._list_pt.append(self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'))

            # 如果没找到底，或者底不符合条件
            if not flag:
                # 检查是否出现了更高的顶（更新逻辑）
                if pt_peak:
                    if pt_peak.k_center_high > self.last_pt.k_center_high:
                        self.last_pt = pt_peak
                        self._cancel_pt(self.last_pt)  # 取消旧顶
                        flag = True  # 标记为新顶
                        self._list_pt.pop()
                        self._list_pt.append(self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'))

        # 3. 当前状态是“底”，寻找“顶”
        elif current_pt_type == PeakTroughType.Trough:
            if pt_peak:
                ret = self._is_matched(self.last_pt, pt_peak)
                if ret:
                    self.last_pt = pt_peak
                    flag = True
                    self._list_pt.append(self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'))

            if not flag:
                # 检查是否出现了更低的底（更新逻辑）
                if pt_trough:
                    if pt_trough.k_center_low < self.last_pt.k_center_low:
                        self.last_pt = pt_trough
                        self._cancel_pt(self.last_pt)  # 取消旧底
                        flag = True
                        self._list_pt.pop()
                        self._list_pt.append(self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'))

        # 如果确认了新点或更新了点，将其写入
        if flag:
            self._set_pt(self.last_pt)
            # print("new pt:" + str(self.last_pt))

