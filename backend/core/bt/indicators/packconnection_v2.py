import backtrader as bt
import numpy as np


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
             'mountain_poit_index_sltp',  # 止赢止损价
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
                    # 原始版
                    # if self.lines.k_high[i+1] > self.lines.k_high[i+0] and self.lines.k_high[i+1] > self.lines.k_high[i+2]:
                    if self.lines.k_low[i+1] < self.lines.k_low[i+0] and self.lines.k_low[i+1] < self.lines.k_low[i+2]:
                        max_low = self.lines.k_low[i+1]  # 中线low
                        max_high = [self.lines.k_high[i],self.lines.k_high[i+1]]
                        # 如果第3线的收盘价<第2线的最低价，即为拐点
                        for k in range(2, leftover):
                            # if self.lines.k_high[i+k] > self.lines.k_high[i+1]:
                            #     break
                            if self.lines.k_close[i+k] < max_low:  # 2,  -1
                                # 顶点值，起始，终点, 属性, 最低价
                                # self.high_array.append([self.lines.k_high[i+1], i, i+k, 1, self.lines.k_low[i+1]])
                                # self.high_array.append([self.lines.k_high[i + 1], i, i + k, 1, max_low, self.lines.k_low[i+k]])
                                # self.lines.mountain_poit_h[i + 1] = self.lines.k_high[i + 1]
                                max_val = max(max_high)
                                max_index = max_high.index(max_val)
                                self.high_array.append([max_val, i, i + k, 1, max_low, self.lines.k_low[i+k], max_index])
                                self.lines.mountain_poit_h[i + 1] = self.lines.k_high[i + 1]
                                break
                            max_low = max(max_low, self.lines.k_low[i + k])
                            max_high.append(self.lines.k_high[i + k])
        except:
             pass
        try:
            if self.num == 0:
                for i in range(self.line_len -2):
                    if self.lines.k_high[i + 1] > self.lines.k_high[i + 0] and self.lines.k_high[i + 1] > self.lines.k_high[i + 2]:
                    # if self.lines.k_low[i+1] < self.lines.k_low[i+0] and self.lines.k_low[i+1] < self.lines.k_low[i+2]:
                        min_high = self.lines.k_high[i + 1]
                        min_low = [self.lines.k_low[i],self.lines.k_low[i+1]]
                        for k in range(2, leftover):
                            # if self.lines.k_low[i+k] < self.lines.k_low[i+1]:
                            #     break
                            if self.lines.k_close[i+k] > min_high:  # 2,  -1
                                # self.low_array.append([self.lines.k_low[i+1], i, i+k, -1, self.lines.k_high[i+1]])  # 顶点值，起始，终点, 属性, 最高价
                                # self.low_array.append([self.lines.k_low[i+1], i, i+k, -1, min_high, self.lines.k_high[i+k]])  # 顶点值，起始，终点, 属性, 最高价
                                # self.lines.mountain_poit_l[i+1] = self.lines.k_low[i+1]
                                min_val = min(min_low)
                                min_index = min_low.index(min_val)
                                self.low_array.append([min_val, i, i+k, -1, min_high, self.lines.k_high[i+k], min_index])  # 顶点值，起始，终点, 属性, 最高价
                                self.lines.mountain_poit_l[i+1] = self.lines.k_low[i+1]
                                break
                            min_high = min(min_high, self.lines.k_high[i + k])
                            min_low.append(self.lines.k_low[i + k])
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
            # if self.params.IsLeftKOffset:
            #     print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@')
            #     for index, i in enumerate(temp_arry1):
            #         # print(i)
            #         # 偏移时跳过第一根
            #         if i == temp_arry1[0]:
            #             temp_arry2 = [i]
            #         else:
            #             # 获取顶底的位置
            #             start_K_index = temp_arry1[index-1][1] + 2
            #             end_K_index = i[1]
            #             # 记录顶底之间的最值
            #             max_K_high = i[0]
            #             min_K_low = i[0]
            #             tmp = end_K_index
            #             for k in range(start_K_index, end_K_index):
            #                 if i[3] == 1 and self.lines.k_high[k] > max_K_high:
            #                     max_K_high = self.lines.k_high[k]
            #                     tmp = k
            #                 elif i[3] == -1 and self.lines.k_low[k] < min_K_low:
            #                     min_K_low = self.lines.k_low[k]
            #                     tmp = k
            #             # 更新顶
            #             if i[3] == 1 and max_K_high > self.lines.k_high[end_K_index + 1]:
            #                 temp_arry2.append([max_K_high, tmp - 1])
            #             elif i[3] == 1 and max_K_high == self.lines.k_high[end_K_index + 1]:
            #                 temp_arry2.append(i)
            #             # 更新底
            #             if i[3] == -1 and min_K_low < self.lines.k_low[end_K_index + 1]:
            #                 temp_arry2.append([min_K_low, tmp - 1])
            #             elif i[3] == -1 and min_K_low == self.lines.k_low[end_K_index + 1]:
            #                 temp_arry2.append(i)

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
                for i in temp_arry1:  # 用于绘制峰线
                    # print('派蒙', i)
                    self.lines.mountain_poit[i[1] + i[6]] = i[0]
            else:
                for i in temp_arry1:  # 用于绘制峰线
                    self.lines.mountain_poit[i[1] + 1] = i[0]
            for i in temp_arry1:  # 用于绘制峰线
                self.lines.mountain_poit_original[i[1] + 1] = i[0]
            # print(temp_arry)
            for i in temp_arry:  # 用于进行买卖
                # print(i)
                self.lines.mountain_poit_index[i[2]] = i[3]
                self.lines.mountain_poit_index_sltp[i[2]] = i[0]
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

class ResponsePCDataV2(bt.Strategy):
    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments, begin_time=None):
        self.indicator_name = indicator_name
        self.comments = comments
        self.indicator_params = indicator_params
        # print(self.indicator_params)
        self.PCdata = Custom_indicators(self.data, self.indicator_params)
        self.result_data_dict = dict()
        self.result_data = []
        self.result_data_original = []
        self.buy_poit = []
        self.sell_poit = []
        self.close_poit = []
        self.po_high = []
        self.po_low = []
        self.title = []
        self.title_offset = []
        self.titlepeak = []
        self.titlebottol = []
        self.titlepeak_offset = []
        self.titlebottol_offset = []

        self.ShowTitlenumber = self.indicator_params.get("ShowTitlenumber", 1)
        self.ShowTitletime = self.indicator_params.get("ShowTitletime", 1)
        self.ShowTitlespread = self.indicator_params.get("ShowTitlespread", 1)
        self.ShowKlinediff = self.indicator_params.get("ShowKlinediff", 1)

        self.ShowTitlenumberoffset = self.indicator_params.get("ShowTitlenumberoffset", 1)
        self.ShowTitletimeoffset = self.indicator_params.get("ShowTitletimeoffset", 1)
        self.ShowTitlespreadoffset = self.indicator_params.get("ShowTitlespreadoffset", 1)
        self.ShowKlinediffoffset = self.indicator_params.get("ShowKlinediffoffset", 1)

        self.peakBmp = self.indicator_params.get("peakBmp", 1)
        self.bottolBmp = self.indicator_params.get("bottolBmp", 2)
        self.IsRightKBroken = self.indicator_params.get("IsRightKBroken", 1)
        self.IsLeftKOffset = self.indicator_params.get("IsLeftKOffset", 1)
        self.OpenkLineId = int(self.data.klineId[0])
        self.orderstatus = ''


        self.TI = TempInd(self.data, diff=self.indicator_params.get("NumericalDifference", 1),
                          IsRightKBroken = self.indicator_params.get("IsRightKBroken", 1),
                          IsLeftKOffset=self.indicator_params.get("IsLeftKOffset", 1),
                          )
        self.CI = Custom_indicators(self.data, self.indicator_params)
        self.mountain_poit_index = self.TI.lines.mountain_poit_index
        # self.mountain_poit_original = self.TI.lines.mountain_poit_original
        # self.abc = self.TI.lines.mountain_poit
        self.open_list = []
        self.date = []
        self.order = None
        self.trades = []
        self.last_cash = self.broker.get_cash()
        self.last_value = self.broker.getvalue()
        self.data_line_count = 0
        self.trend_change_last = 0
        self.tm = 0  # tm用于判断平仓后要不要进行买卖

    def next(self):

        # pass
        # print(self.position.size)
        self.mountain_poit = self.PCdata.lines.mountain_poit_line[0]
        if np.isnan(self.mountain_poit):
            self.mountain_poit = None

        current_kline_id = int(self.data.klineId[0])

        self.data_line_count += 1


        # 将顶底数据添加到结果列表（偏移）
        self.mountain_poit2 = self.TI.lines.mountain_poit[0]
        if np.isnan(self.mountain_poit2):
            self.mountain_poit2 = None
        else:
            self.result_data.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.mountain_poit2,
            })
        # 将顶底数据添加到结果列表（原始）
        self.mountain_poit3 = self.TI.lines.mountain_poit_original[0]
        if np.isnan(self.mountain_poit3):
            self.mountain_poit3 = None
        else:
            self.result_data_original.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.mountain_poit3,
            })

        if not np.isnan(self.TI.lines.mountain_poit_h_po[0]) and self.TI.lines.mountain_poit_h_po[0] != self.TI.lines.mountain_poit[0]:
            self.po_high.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.TI.lines.mountain_poit_h_po[0],
            })
        if not np.isnan(self.TI.lines.mountain_poit_l_po[0]) and self.TI.lines.mountain_poit_l_po[0] != self.TI.lines.mountain_poit[0]:
            self.po_low.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.TI.lines.mountain_poit_l_po[0],
            })

    def stop(self):
        # 绘图序列（根据参数为偏点或原点）
        arr1 = np.array(self.TI.lines.mountain_poit.array)
        arr1 = arr1[~np.isnan(arr1)]
        # print(len(arr1), arr1)
        if len(arr1) <= 1:  # 当没有顶低点的时候
            self.notnallpoint = []
            return False
        # 原始序列
        arr2 = np.array(self.TI.lines.mountain_poit_original.array)
        arr2 = arr2[~np.isnan(arr2)]
        # print(len(arr2), arr2)
        offset_index = [True if i in arr1 else False for i in arr2][::-1] # 逆序了，第一个值日期最新 ，ture表示两个值相同即没有偏移
        # print("是否偏移", offset_index)
        # 得到非空的绘画点
        self.notnallpoint = [[index, value] for index, value in enumerate(self.TI.lines.mountain_poit.array) if
                             not np.isnan(value)]
        # print("绘图点的index（针对全长）和value", self.notnallpoint)
        false_indices = [i for i, value in enumerate(offset_index) if value is False]
        # print("是否偏移index（针对顶底点）", false_indices)
        # print(len(self.result_data), len(self.result_data_original), len(offset_index))
        #---------------------------------画线点的处理---------------------------------#
        self.notnallpoint = [[index, value] for index, value in enumerate(self.TI.lines.mountain_poit.array) if not np.isnan(value)]
        # 看最后一个值1还是-1
        arr = np.array(self.TI.lines.mountain_poit_index.array)
        tmp = arr[~np.isnan(arr)][-1]
        xuhao = 0  # 顶底的序号
        digits = int(self.datas[0].digits[0])  # 精度

        offset_allvalue_array = []
        # 生成顶底的标题
        for index, value in enumerate(reversed(self.result_data)):
            # print(index, value)
            # 计算序号
            spread = 0
            if index % 2 == 0 and index != 0:
                xuhao += 1
            dd = '顶' if tmp == 1 else '底'
            tmp *= -1

            # 计算价差
            if index + 1 < len(self.result_data):
                spread = value.get('price') - self.result_data[len(self.result_data) - index - 2].get('price')
                spread = "{:.{digits}f}".format(spread, digits=digits)

            # 计算K线差
            if index + 1 < len(self.result_data):
                kidff = self.notnallpoint[len(self.result_data) - index - 1][0] - self.notnallpoint[len(self.result_data) - index - 2][0]

            # 计算时间戳
            timestamp = value.get("timestamp")

            title_str1 = dd + str(xuhao) + " " + str(spread) + " " + str(kidff) + " " + str(timestamp)

            title_str = ''
            if self.ShowTitlenumber == 1:
                title_str = title_str + dd + str(xuhao)
            if self.ShowTitlespread == 1:
                title_str += ' '
                title_str += str(spread)
            if self.ShowKlinediff == 1:
                title_str += ' K'
                title_str += str(kidff)
            if self.ShowTitletime == 1:
                title_str += ' \n '
                title_str = title_str + str(timestamp)
            else:
                title_str += ' \n '

            self.title.append({
                    "kLineId": value.get("kLineId"),
                    "timestamp": value.get("timestamp"),
                    "price":  value.get("price"),
                    "value": title_str,
                })
            try:  # 添加的是画图点中的价差等即  正点：偏移点
                if not offset_index[index+1]:
                    offset_allvalue_array.append(title_str1)
                else:
                    offset_allvalue_array.append('')
            except:
                pass
        #---------------------被偏移的原始点的处理---------------------#
        # 被偏移的原始点的处理
        self.notnallpoint = [[index, value] for index, value in enumerate(self.TI.lines.mountain_poit_original.array) if
                             not np.isnan(value)]
        tmp = arr[~np.isnan(arr)][-1]
        for index, i in enumerate(self.title):
            if not offset_index[index]:
                i['value'] = i['value'].replace('底', '偏底')
                i['value'] = i['value'].replace('顶', '偏顶')
            if tmp == 1 and index % 2 == 0:
                self.titlepeak.append(i)
            elif tmp == 1 and index % 2 == 1:
                self.titlebottol.append(i)
            elif tmp == -1 and index % 2 == 0:
                self.titlebottol.append(i)
            elif tmp == -1 and index % 2 == 1:
                self.titlepeak.append(i)
            try:
                if not offset_index[index+1] and offset_index[index]:
                    i['value'] = ''
            except:
                pass

        arr = np.array(self.TI.lines.mountain_poit_index.array)
        tmp = arr[~np.isnan(arr)][-1]
        xuhao = 0  # 顶底的序号
        # 得到偏点的文字
        for index, value in enumerate(reversed(self.result_data_original)):
            # print(index, value)
            # 计算序号
            spread = 0
            if index % 2 == 0 and index != 0:
                xuhao += 1
            dd = '顶' if tmp == 1 else '底'
            tmp *= -1
            # 计算价差
            if index + 1 < len(self.result_data_original):
                spread = value.get('price') - self.result_data_original[len(self.result_data_original) - index - 2].get('price')
                spread = "{:.{digits}f}".format(spread, digits=digits)
            # 计算K线差
            if index + 1 < len(self.result_data_original):
                kidff = self.notnallpoint[len(self.result_data_original) - index - 1][0] - self.notnallpoint[len(self.result_data_original) - index - 2][0]
            # 计算时间戳
            timestamp = value.get("timestamp")

            # title_str = dd + str(xuhao) + " " + str(spread) + " " + str(kidff) + "\n" + str(timestamp)
            # if self.ShowTitlespread == 0 and self.ShowTitlenumber == 0 and self.ShowKlinediff == 0 and self.ShowTitletime == 0:
            #     title_str = ''
            title_str = ''
            if self.ShowTitlenumberoffset == 1:
                title_str = title_str + dd + str(xuhao)
            if self.ShowTitlespreadoffset == 1:
                title_str += ' '
                title_str += str(spread)
            if self.ShowKlinediffoffset == 1:
                title_str += ' K'
                title_str += str(kidff)
            if self.ShowTitletimeoffset == 1:
                title_str += ' \n '
                title_str = title_str + str(timestamp)

            if not offset_index[index]:  # 添加的是 偏移点 ：正点
                self.title_offset.append({
                        "kLineId": value.get("kLineId"),
                        "timestamp": value.get("timestamp"),
                        "price":  value.get("price"),
                        "value": title_str,
                        "state": dd,
                    })
                pass
            try:  # 添加的是  正点：正点
                if not offset_index[index+1]:
                    str_split = offset_allvalue_array[index].split(' ')
                    tmp_str = ''
                    if self.ShowTitlenumberoffset == 1:
                        tmp_str += ' '
                        tmp_str += str_split[0]
                    if self.ShowTitlespreadoffset == 1:
                        tmp_str += ' '
                        tmp_str += str_split[1]
                    if self.ShowKlinediffoffset == 1:
                        tmp_str += ' K'
                        tmp_str += str_split[2]
                    if self.ShowTitletimeoffset == 1:
                        tmp_str += ' \n '
                        tmp_str = tmp_str + str_split[3] + str_split[4]
                    title_str2 = ''
                    if self.ShowTitlenumber == 1:
                        title_str2 = title_str2 + dd + str(xuhao)
                    if self.ShowTitlespread == 1:
                        title_str2 += ' '
                        title_str2 += str(spread)
                    if self.ShowKlinediff == 1:
                        title_str2 += ' K'
                        title_str2 += str(kidff)
                    if self.ShowTitletime == 1:
                        title_str2 += ' \n '
                        title_str2 = title_str2 + str(timestamp)
                    if self.ShowTitlenumberoffset == 1 or self.ShowTitlespreadoffset == 1 or self.ShowKlinediffoffset == 1 or self.ShowTitletimeoffset == 1:
                        title_str2 = title_str2 + ' \n (偏)' + tmp_str
                    self.title_offset.append({
                        "kLineId": value.get("kLineId"),
                        "timestamp": value.get("timestamp"),
                        "price": value.get("price"),
                        "value": title_str2,
                        "state": dd,
                    })
            except:
                pass

        for index, i in enumerate(self.title_offset):
            # print(i)
            if i.get('state') == '顶':
                self.titlepeak_offset.append(i)
            if i.get('state') == '底':
                self.titlebottol_offset.append(i)


    def get_analysis(self):
        # 组织数据结构
        self.result_data_dict["lines"] = [
            {
                "type": "brokenline",
                "color": self.indicator_params.get("TrendPackconnectionColor", "#00FF00"),
                "data": self.result_data
            },
            {
                "type": "bmp",  # 表示破顶
                "arrow": self.peakBmp,
                "data": self.po_high
            },
            {
                "type": "bmp",  # 表示破底
                "arrow": self.bottolBmp,
                "data": self.po_low
            },
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'top',
                "data": self.titlepeak[::-1]
            },
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'bottom',
                "data": self.titlebottol[::-1]
            },
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'top',
                "data": self.titlepeak_offset[::-1]
            },
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'bottom',
                "data": self.titlebottol_offset[::-1]
            },
        ]

        if len(self.notnallpoint) > 2:
            startime = self.datas[0].datetime.datetime(self.notnallpoint[1][0] - self.data.buflen()).strftime('%Y-%m-%d %H:%M:%S')
            endtime  = self.datas[0].datetime.datetime(self.notnallpoint[-2][0] - self.data.buflen()).strftime('%Y-%m-%d %H:%M:%S')
        else:
            startime = None
            endtime = None
        return [self.result_data_dict["lines"],
                startime,  #  开始时间
                endtime,  #  结束时间
                None
                ]
