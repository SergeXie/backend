import backtrader as bt
import numpy as np


class ATRStopLoss(bt.Indicator):
    lines = ('target_dn', 'target_up', "trend_change", "ATR",)

    params = (
        ('atr_len', 10),  # 周期 计算 ATR（平均真实波动范围），使用周期为 atr_len 的数据
        ('multiplier', 3.0),  # 上下价的乘数
    )

    plotinfo = dict(subplot=False, plotlinelabels=True)  # 将指标放在主图表中

    def __init__(self):
        self.lines_names = []
        self.atr = bt.indicators.AverageTrueRange(self.data, period=self.params.atr_len)
        self.src = (self.data.high + self.data.low) / 2
        self.lines.target_dn = self.src + self.p.multiplier * self.atr
        self.lines.target_up = self.src - self.p.multiplier * self.atr
        self.change = 0  # 初始化趋势 1 上趋势 -1 下趋势

    def next(self):
        d_change = self.lines.trend_change[-1]
        if np.isnan(d_change):
            self.lines.trend_change[0] = 1
        else:
            up1 = self.lines.target_up[-1]
            dn1 = self.lines.target_dn[-1]

            # 更新 target_up 和 target_dn
            self.lines.target_up[0] = max(self.lines.target_up[0], up1) if self.data.close[-1] > up1 else \
            self.lines.target_up[0]
            self.lines.target_dn[0] = min(self.lines.target_dn[0], dn1) if self.data.close[-1] < dn1 else \
            self.lines.target_dn[0]

            # 获取前一个趋势
            trend1 = self.lines.trend_change[-1]

            if trend1 == -1 and self.data.close[0] > self.lines.target_dn[-1]:
                self.lines.trend_change[0] = 1
            else:
                if trend1 == 1 and self.data.close[0] < self.lines.target_up[-1]:
                    self.lines.trend_change[0] = -1
                else:
                    self.lines.trend_change[0] = trend1

            # 根据趋势变化更新上下限
            if self.lines.trend_change[0] == 1:
                self.lines.target_dn[0] = np.nan
            elif self.lines.trend_change[0] == -1:
                self.lines.target_up[0] = np.nan

        # print(f"datetime: {self.datas[0].datetime.datetime(0)}, close: {self.data.close[0]},"
        #       f" trend0: {self.lines.trend_change[0]}  trend-1: {self.lines.trend_change[-1]}")



class TempInd(bt.Indicator):
    params = (
        ('diff', 0),
        ('dis', False),  # True:间隔两个K线即可  False:左线大于右线
        ('plot_po', False),   # True:绘制破点  False:绘制买卖的顶底点
        ('IsRightKBroken', 1),
        ('IsLeftKOffset', 1),
    )
    # mountain_poit 用于获取峰值（顶的最高，底的最低）
    # mountain_poit_index 用于标记取点的状态{1：取高点；-1：取低点；2：高低均可取；0：初始和结束状态}
    # mountain_poit_h和mountain_poit_l 表示全部的顶和底
    # mountain_poit_h_po和mountain_poit_l_po 表示筛选后，的顶底和被破的顶和底
    # left 记录一组顶或底中，右线到中线的距离
    lines = ('mountain_poit', # 用于画线的
             'mountain_poit_index',
             'mountain_poit_original',  # 当前版本表示原始连线（即没有左偏）
             'mountain_poit_h', 'mountain_poit_l',
             'mountain_poit_h_po', 'mountain_poit_l_po',
             'left',
             )

    plotinfo = dict(subplot=False, plotlinelabels=True)  # 将指标放在主图表中

    plotlines = dict(
        mountain_poit_h_po=dict(marker='*', markersize=8.0, color='red', fillstyle='full'),
        mountain_poit_l_po=dict(marker='^', markersize=8.0, color='red', fillstyle='full'),
    )

    def __init__(self):
        self.lines.k_high = self.data.high
        self.lines.k_low = self.data.low
        self.lines.k_close = self.data.close
        self.lines.k_open = self.data.open

        self.line_len = self.data.buflen()  # 数据的长度
        self.num = 0
        self.high_array = []
        self.low_array = []
        self.point_array = []

    def next(self):
        # self.num += 1  # 获取第几次循环
        leftover = self.line_len - self.num  # 剩余数组的长度
        try:
            if self.num == 0:
                for i in range(self.line_len):
                    if self.lines.k_high[i+1] > self.lines.k_high[i+0] and self.lines.k_high[i+1] > self.lines.k_high[i+2]:
                        max_low = self.lines.k_low[i+1]
                        # 如果第3线的收盘价<第2线的最低价，即为拐点
                        for k in range(2, leftover):
                            if self.lines.k_high[i+k] > self.lines.k_high[i+1]:
                                break
                            if self.lines.k_close[i+k] < max_low:  # 2,  -1
                                # 顶点值，起始，终点, 属性, 最低价
                                # self.high_array.append([self.lines.k_high[i+1], i, i+k, 1, self.lines.k_low[i+1]])
                                self.high_array.append([self.lines.k_high[i + 1], i, i + k, 1, max_low, self.lines.k_low[i+k]])
                                self.lines.mountain_poit_h[i+1] = self.lines.k_high[i+1]
                                break
                            max_low = max(max_low, self.lines.k_low[i + k])
        except:
             pass
        try:
            if self.num == 0:
                for i in range(self.line_len -2):
                    if self.lines.k_low[i+1] < self.lines.k_low[i+0] and self.lines.k_low[i+1] < self.lines.k_low[i+2]:
                        min_high = self.lines.k_high[i + 1]
                        for k in range(2, leftover):
                            if self.lines.k_low[i+k] < self.lines.k_low[i+1]:
                                break
                            if self.lines.k_close[i+k] > min_high:  # 2,  -1
                                # self.low_array.append([self.lines.k_low[i+1], i, i+k, -1, self.lines.k_high[i+1]])  # 顶点值，起始，终点, 属性, 最高价
                                self.low_array.append([self.lines.k_low[i+1], i, i+k, -1, min_high, self.lines.k_high[i+k]])  # 顶点值，起始，终点, 属性, 最高价
                                self.lines.mountain_poit_l[i+1] = self.lines.k_low[i+1]
                                break
                            min_high = min(min_high, self.lines.k_high[i + k])
        except:
            pass

        if self.num == 0:
            # print(self.high_array)
            # 将顶数组和底数组合并，以数组中的第一个值的大小进行比较，将小的放进point_array数组，当一个数组为空时，将非空的数组直接放进去
            while len(self.high_array) != 0 and len(self.low_array) != 0:
                if self.high_array[0][1] < self.low_array[0][1]:
                    self.point_array.append(self.high_array[0])
                    self.high_array.pop(0)
                else:
                    self.point_array.append(self.low_array[0])
                    self.low_array.pop(0)
            if len(self.high_array) != 0:
                self.point_array = self.point_array + self.high_array
            else:
                self.point_array = self.point_array + self.low_array


            temp_arry = [self.point_array[0]]   # 长的 含破点(用于买卖)
            temp_arry1 = [self.point_array[0]]  #  短的 只含峰点
            for i in self.point_array:
                # 顶点值，起始，终点, 属性, 最低价, 右线最高/低
                if i[3] == temp_arry1[-1][3]:  # 同顶底的情况 留最值
                    if i[3] == -1:
                        if i[0] < temp_arry1[-1][0]:
                            temp_arry.append(i)
                            temp_arry1.pop(-1)
                            temp_arry1.append(i)

                    if i[3] == 1:
                        if i[0] > temp_arry1[-1][0]:
                            temp_arry.append(i)
                            temp_arry1.pop(-1)
                            temp_arry1.append(i)

                elif i[3] != temp_arry1[-1][3]:  # 与上一条不同
                    if self.params.dis:  # 设置底的保留情况，True：顶底可以共线，中线距离大于3艮即可， False：不可共线
                        con = i[1] - temp_arry[-1][1] >= 3
                    else:
                        con = temp_arry1[-1][2] < i[1]
                    if self.params.IsRightKBroken and (i[5] - temp_arry1[-1][0]) * temp_arry1[-1][3] > 0:
                        con2 = False
                    else:
                        con2 = True
                    if con and ((i[4] - temp_arry1[-1][4]) * i[3] > self.params.diff) and con2:
                        temp_arry1.append(i)
                        temp_arry.append(i)
            # 对点进行偏移，得到temp_arry2
            if self.params.IsLeftKOffset:
                for index, i in enumerate(temp_arry1):
                    # print(i)
                    # 偏移时跳过第一根
                    if i == temp_arry1[0]:
                        temp_arry2 = [i]
                    else:
                        # 获取顶底的位置
                        start_K_index = temp_arry1[index-1][1] + 2
                        end_K_index = i[1]
                        # 记录顶底之间的最值
                        max_K_high = i[0]
                        min_K_low = i[0]
                        tmp = end_K_index
                        for k in range(start_K_index, end_K_index):
                            if i[3] == 1 and self.lines.k_high[k] > max_K_high:
                                max_K_high = self.lines.k_high[k]
                                tmp = k
                            elif i[3] == -1 and self.lines.k_low[k] < min_K_low:
                                min_K_low = self.lines.k_low[k]
                                tmp = k
                        # 更新顶
                        if i[3] == 1 and max_K_high > self.lines.k_high[end_K_index + 1]:
                            temp_arry2.append([max_K_high, tmp - 1])
                        elif i[3] == 1 and max_K_high == self.lines.k_high[end_K_index + 1]:
                            temp_arry2.append(i)
                        # 更新底
                        if i[3] == -1 and min_K_low < self.lines.k_low[end_K_index + 1]:
                            temp_arry2.append([min_K_low, tmp - 1])
                        elif i[3] == -1 and min_K_low == self.lines.k_low[end_K_index + 1]:
                            temp_arry2.append(i)

            # for i in temp_arry1:  # 用于绘制峰线
            #     # self.lines.mountain_poit[i[1] + 1] = i[0]
            #     self.lines.mountain_poit_original[i[1] + 1] = i[0]
            # for i in temp_arry:  # 用于进行买卖
            #     self.lines.mountain_poit_index[i[2]] = i[3]
            #     self.lines.left[i[2]] = i[2] - i[1]
            #
            #     if not self.params.plot_po:  #  将破点添加
            #         if i[3] == 1:
            #             self.lines.mountain_poit_h_po[i[1] + 1] = i[0]
            #         elif i[3] == -1:
            #             self.lines.mountain_poit_l_po[i[1] + 1] = i[0]
            #
            # # 对点进行偏移时更新mountain_poit
            # if self.params.IsLeftKOffset:
            #     for i in temp_arry1:
            #         self.lines.mountain_poit[i[1] + 1] = np.nan
            #     for i in temp_arry2:  # 用于绘制峰线
            #         self.lines.mountain_poit[i[1] + 1] = i[0]
            if self.params.IsLeftKOffset:
                for i in temp_arry2:  # 用于绘制峰线
                    self.lines.mountain_poit[i[1] + 1] = i[0]
            else:
                for i in temp_arry1:  # 用于绘制峰线
                    self.lines.mountain_poit[i[1] + 1] = i[0]
            for i in temp_arry1:  # 用于绘制峰线
                self.lines.mountain_poit_original[i[1] + 1] = i[0]
            for i in temp_arry:  # 用于进行买卖
                self.lines.mountain_poit_index[i[2]] = i[3]
                self.lines.left[i[2]] = i[2] - i[1]

                if not self.params.plot_po:  #  将破点添加
                    if i[3] == 1:
                        self.lines.mountain_poit_h_po[i[1] + 1] = i[0]
                    elif i[3] == -1:
                        self.lines.mountain_poit_l_po[i[1] + 1] = i[0]

        self.num += 1  # 获取第几次循环




class Custom_indicators(bt.Indicator):  # 等差数列填充
    params = (
        ('diff', 1),
        ('IsRightKBroken', 1),
        ('IsLeftKOffset', 1),
    )
    lines = ('mountain_poit_line',)

    plotinfo = dict(subplot=False, plotlinelabels=True)  # 将指标放在主图表中

    def __init__(self, indicator_params):
        self.indicator_params = indicator_params
        self.TI = TempInd(self.data, diff=self.indicator_params.get("NumericalDifference", 1),
                          IsRightKBroken=self.indicator_params.get("IsRightKBroken", 1),
                          IsLeftKOffset=self.indicator_params.get("IsLeftKOffset", 1),
                          )
        self.lines.mountain_poit_line = self.TI.lines.mountain_poit

    def next(self):
        # 此时全部顶和底已经确认，开始填充空值
        if len(self) == self.TI.line_len:  # 表示在最后一次迭代填充
            start = 1-self.TI.line_len
            end = 1-self.TI.line_len
            for i in range(1-self.TI.line_len, 0, 1):
                if not np.isnan(self.lines.mountain_poit_line[i+1]):
                    continue
                for j in range(i + 1, 1):
                    if np.isnan(self.lines.mountain_poit_line[j]):
                        end += 1
                    else:  # 非空时退出循环
                        if not end == start:
                            common_difference = (self.lines.mountain_poit_line[j] - self.lines.mountain_poit_line[i])/(end - start +1)
                            for k in range(1, end - start+1):
                                self.lines.mountain_poit_line[i+k] = self.lines.mountain_poit_line[i] + k * common_difference
                            break
                start = end