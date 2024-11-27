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
        self.lines.target_dn = self.src + self.atr * self.p.multiplier
        self.lines.target_up = self.src - self.atr * self.p.multiplier
        self.change = 1  # 初始化趋势 1 上趋势 -1 下趋势

    def next(self):
        # 保留两位小数
        self.lines.target_dn[-1] = round(self.lines.target_dn[-1], 2) if not np.isnan(
            self.lines.target_dn[-1]) else np.nan
        self.lines.target_up[-1] = round(self.lines.target_up[-1], 2) if not np.isnan(
            self.lines.target_up[-1]) else np.nan

        # 计算趋势变化
        if self.data.close[0] > self.lines.target_dn[-1]:
            self.change = 1
        elif self.data.close[0] < self.lines.target_up[-1]:
            self.change = -1

        self.lines.trend_change[0] = self.change

        # 更新目标上下限
        self.lines.target_dn[0] = min(self.lines.target_dn[0], self.lines.target_dn[-1])
        self.lines.target_up[0] = max(self.lines.target_up[0], self.lines.target_up[-1])

        # 根据趋势变化更新上下限
        if self.lines.trend_change[0] == 1:
            self.lines.target_dn[0] = np.nan
        elif self.lines.trend_change[0] == -1:
            self.lines.target_up[0] = np.nan


class TempInd(bt.Indicator):
    params = (
        ('diff', 1),
        ('dis', False),  # True:间隔两个K线即可  False:左线大于右线
        ('plot_po', False),   # True:绘制破点  False:绘制买卖的顶底点
    )
    # mountain_poit 用于获取峰值（顶的最高，底的最低）
    # mountain_poit_index 用于标记取点的状态{1：取高点；-1：取低点；2：高低均可取；0：初始和结束状态}
    # mountain_poit_h和mountain_poit_l 表示全部的顶和底
    # mountain_poit_h_po和mountain_poit_l_po 表示筛选后，的顶底和被破的顶和底
    # left 记录一组顶或底中，右线到中线的距离
    lines = ('mountain_poit', 'mountain_poit_index',
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
        self.high_array = []  #
        self.low_array = []
        self.point_array = []

    def next(self):
        # self.num += 1  # 获取第几次循环
        leftover = self.line_len - self.num  # 剩余数组的长度
        try:
            if self.num == 0:
                for i in range(self.line_len):
                    if self.lines.k_high[i+1] > self.lines.k_high[i+0] and self.lines.k_high[i+1] > self.lines.k_high[i+2]:

                        # 如果第3线的收盘价<第2线的最低价，即为拐点
                        for k in range(2, leftover):
                            if self.lines.k_close[i+k] < self.lines.k_low[i+k-1]:  # 2,  -1
                                # 顶点值，起始，终点, 属性, 最低价
                                self.high_array.append([self.lines.k_high[i+1], i, i+k, 1, self.lines.k_low[i+1]])
                                self.lines.mountain_poit_h[i+1] = self.lines.k_high[i+1]
                                break
        except:
             pass
        try:
            if self.num == 0:
                for i in range(self.line_len -2):
                    if self.lines.k_low[i+1] < self.lines.k_low[i+0] and self.lines.k_low[i+1] < self.lines.k_low[i+2]:
                        for k in range(2, leftover):
                            if self.lines.k_close[i+k] > self.lines.k_high[i+k-1]:  # 2,  -1
                                self.low_array.append([self.lines.k_low[i+1], i, i+k, -1, self.lines.k_high[i+1]])  # 顶点值，起始，终点, 属性, 最高价
                                self.lines.mountain_poit_l[i+1] = self.lines.k_low[i+1]
                                break
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
                    if con and ((i[4] - temp_arry1[-1][4])*i[3] > self.params.diff):
                        temp_arry1.append(i)
                        temp_arry.append(i)
            for i in temp_arry1:  # 用于绘制峰线
                self.lines.mountain_poit[i[1] + 1] = i[0]
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
    )
    lines = ('mountain_poit_line',)

    plotinfo = dict(subplot=False, plotlinelabels=True)  # 将指标放在主图表中

    def __init__(self, indicator_params):
        self.indicator_params = indicator_params
        self.TI = TempInd(self.data, diff=self.indicator_params.get("NumericalDifference", 1))
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