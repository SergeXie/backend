import backtrader as bt
import numpy as np

import backtrader as bt
# 检查符号发生变化的点
def find_sign_change_indices(data):
    # 将数据转换为 numpy 数组
    data_array = np.array(data)

    # 计算前后元素乘积
    product = data_array[:-1] * data_array[1:]

    # 找到乘积为负的索引位置
    indices = np.where(product < 0)[0] + 1

    return indices.tolist()

# 检查背离点的索引对
def find_divergence_indices(data, state, signal):
    # K线值（对应柱线极值），柱线极值， 极值索引， 慢线穿0点, 方向, 开始索引, 结束索引
    signal = np.array(signal.array)
    return_index = []
    l = len(data)
    for i in range(l-1):
        # print('@@@@@@@@@@@@@@@@@@@',state, data[i][2], data[i][3])
        # print(data[i][6], data[i+1][5])
        # print(data[i][6]-len(signal), data[i+1][5]-len(signal))
        find_signchange_signal = signal[data[i][6]: data[i+1][5]]
        change_list = find_sign_change_indices(find_signchange_signal)  # 两端之间是否存在过0点
        # print(change_list)
        if state == 0 and len(change_list)>0:  # 下一根穿了0线，当前的跳过0点前的点
            continue

        base_k = data[i][0][-1]
        base_s = data[i][1][-1]
        next_k = np.array(data[i+1][0])
        next_s = np.array(data[i+1][1])
        tmp = np.array(data[i+1][2])

        ind = (next_k - base_k) * (next_s - base_s) < 0
        # ind = ind & ind2

        # 多重山的情况下，如果最高峰不符合条件，那么后的峰都不符合条件
        next_s = np.abs(next_s)
        next_s_max_index = np.argmax(next_s)
        # print(next_s_max_index)
        # if not ind[next_s_max_index]:
        #     ind[next_s_max_index:] = [False] * (len(ind) - next_s_max_index)


        tmp2= [[data[i][5] + data[i][2][-1] , data[i+1][5]+j] for j in tmp[ind]]
        # print(tmp2)
        bool_arr = np.array((next_k - base_k)[ind]>0)
        tmp2 = np.array(tmp2)
        extended_list = []
        if len(bool_arr)>0:
            extended_list = np.hstack((tmp2, bool_arr[:, np.newaxis])).tolist()  # 组合索引和方向
        return_index.append(extended_list)
    # for i in range(len(return_index)):
    #     print(return_index[i])
    # print('ooooooooooooooooooooo',return_index)
    return return_index


# 创建一个策略
class ResponseMACDData_v1(bt.Strategy):
    # lines = ('up_line', 'down_line')
    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
    )

    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments

        self.result_data_line = []
        self.result_data_signal = []
        self.result_data_histo = []
        self.result_data_dict = dict()

        self.options_price = {0: self.data.close, 1: self.data.open, 2: self.data.high, 3: self.data.low}
        source_index = int(self.indicator_params.get("Source", 0))

        # 添加MACD指标
        self.macd = bt.indicators.MACDHisto(
            self.options_price[source_index],
            period_me1=int(self.indicator_params.get("fast_period", 12)),
            period_me2=int(self.indicator_params.get("slow_period", 26)),
            period_signal=int(self.indicator_params.get("signal_period", 9)),
        )

        self.macd_signal = self.macd.signal
        self.macd_line = self.macd.macd
        self.macd_histo = self.macd.histo
        self.state = []

        self.up_array = []  # 返回K线值（对应柱线极值），柱线极值， 极值索引， 慢线穿0点, 方向, 开始索引
        self.down_array = []

        self.last_index = 0
        self.num = 0

        self.line1 = []
        self.plot_line1 = []
        self.plot_line2 = []

    def next(self):
        now_index = len(self)
        current_kline_id = int(self.data.klineId[0])
        dir = 1 if self.macd_histo[0] > 0 else -1

        # 第2组红柱和率柱出现才开始
        if len(self.state) > 1:
            if dir != self.state[-1]:
                # 寻找所有的极值点，接收开始索引和结束索引，按索引切数据
                # K线值（对应柱线极值），柱线极值， 极值索引， 慢线穿0点
                k_array, values, index, coss = self.CheckExtremePoints(self.last_index, now_index, self.state[-1])
                if self.state[-1] == 1:  # 表示红柱
                    self.up_array.append([k_array, values, index, coss, 1, self.last_index, now_index])
                elif self.state[-1] == -1:
                    self.down_array.append([k_array, values, index, coss, -1, self.last_index, now_index])
                self.last_index = now_index+1
        elif len(self.state)==1:
            self.last_index = now_index
        self.state.append(dir)
        # 最后一次循环时执行
        if now_index == self.data.buflen():
            # 寻找所有背离点的索引，[912,936]的格式
            self.plot_line1 = find_divergence_indices(self.up_array, self.indicator_params.get("allowCrossZero"), self.macd_signal)
            self.plot_line2 = find_divergence_indices(self.down_array, self.indicator_params.get("allowCrossZero"), self.macd_signal)

        # 将数据添加到结果列表
        self.result_data_line.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": self.macd_line[0]+2300 if not np.isnan(self.macd_line[0]) else None,
        })
        self.result_data_signal.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": self.macd_signal[0]+2300 if not np.isnan(self.macd_signal[0]) else None,
        })
        self.result_data_histo.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": self.macd_histo[0]+2300 if not np.isnan(self.macd_signal[0]) else None,
        })
        self.num += 1


    def CheckExtremePoints(self,start,end, dir):  # 返回K线值（对应柱线极值），柱线极值， 极值索引， 慢线穿0点
        data = self.data.high if dir == 1 else self.data.low
        k_array = []
        histo_array = []
        signal_array = []
        C_start = start - len(self)-1
        C_end = end - len(self)-1

        # print('lllllllllllllllllllllllllll', start, end, C_start, C_end, dir)
        for i in range(start-len(self)-1, end - len(self)):
            k_array.append(data[i])
            histo_array.append(self.macd_histo[i])
            signal_array.append(self.macd_signal[i])
        data_np = np.array(histo_array)

        # 寻找极大值极小值
        if dir == 1:  # 红柱的情况
            local_maxima = (np.diff(np.sign(np.diff(data_np))) < 0).nonzero()[0] + 1
        else:
            local_maxima = (np.diff(np.sign(np.diff(data_np))) > 0).nonzero()[0] + 1
        local_maxima = local_maxima[local_maxima != 0]

        # 极值和索引
        values = data_np[local_maxima].tolist()
        indices = local_maxima.tolist()

        if len(values) == 0:  #  如果单调就找绝对值的最大值
            data_np = abs(data_np)
            t_value = max(data_np)
            t_indices = np.argmax(data_np)
            values.append(t_value)
            indices.append(t_indices)
        # 计算对应macd柱线极值的k线值
        k_values = [k_array[i] for i in indices]
        # 计算与0有交点的索引
        cross = find_sign_change_indices(signal_array)
        # print(k_values, values, indices, cross)
        return k_values, values, indices, cross


    def get_analysis(self):
        self.result_data_dict["lines"] = []
        if self.indicator_params.get("showoriginalmacd"):
            self.result_data_dict["lines"].append(
                {
                    "type": 'line',
                    "color": self.indicator_params.get("TrendDMAColor"),
                    # "lineStyle": self.indicator_params.get("macdstyle"),
                    "data": self.result_data_line
                })
            self.result_data_dict["lines"].append(
                {
                    "type": "line",
                    "color": self.indicator_params.get("TrendSignalColor"),
                    "data": self.result_data_signal
                })
            self.result_data_dict["lines"].append(
                {
                    "type": "line",
                    "color": self.indicator_params.get("TrendhistolColor"),
                    "data": self.result_data_histo
                }
            )

        for i in self.plot_line1:
            if len(i) > 0:
                for j in i:
                    tmp_c = self.indicator_params.get("DivergenceColor") if j[2] == 1 else self.indicator_params.get("ConvergenceColor")
                    if j[2] == 1 and self.indicator_params.get("allowDivergence")==0: continue
                    if j[2] == 0 and self.indicator_params.get("allowConvergence")==0: continue
                    l = self.data.buflen()
                    a = j[0]-l-1
                    b = j[1]-l-1
                    # print(a, b, j[0], j[1], l)
                    if j == i[-1]:
                        ls = 0
                    else:
                        ls = self.indicator_params.get("macdstyle")
                    self.result_data_dict["lines"].append(
                        {
                            "type": 'brokenline',
                            "color": tmp_c,
                            "lineStyle": ls,
                            "data": [{
                                "kLineId": int(self.data.klineId[a]),
                                "timestamp": self.datas[0].datetime.datetime(a).strftime('%Y-%m-%d %H:%M:%S'),
                                "price": self.data.high[a],
                            },
                            {
                                "kLineId": int(self.data.klineId[b]),
                                "timestamp": self.datas[0].datetime.datetime(b).strftime('%Y-%m-%d %H:%M:%S'),
                                "price": self.data.high[b],
                            }
                            ]
                        })
        for i in self.plot_line2:
            if len(i) > 0:
                for j in i:
                    tmp_c = self.indicator_params.get("ConvergenceColor") if j[2] == 0 else self.indicator_params.get("DivergenceColor")
                    if j[2] == 1 and self.indicator_params.get("allowDivergence")==0: continue
                    if j[2] == 0 and self.indicator_params.get("allowConvergence")==0: continue
                    l = self.data.buflen()
                    a = j[0]-l-1
                    b = j[1]-l-1
                    # print(a, b, j[0], j[1], l)
                    if j == i[-1]:
                        ls = 0
                    else:
                        ls = self.indicator_params.get("macdstyle")
                    self.result_data_dict["lines"].append(
                        {
                            "type": 'brokenline',
                            "color": tmp_c,
                            "lineStyle": ls,
                            "data": [{
                                "kLineId": int(self.data.klineId[a]),
                                "timestamp": self.datas[0].datetime.datetime(a).strftime('%Y-%m-%d %H:%M:%S'),
                                "price": self.data.low[a],
                            },
                            {
                                "kLineId": int(self.data.klineId[b]),
                                "timestamp": self.datas[0].datetime.datetime(b).strftime('%Y-%m-%d %H:%M:%S'),
                                "price": self.data.low[b],
                            }
                            ]
                        })

        return [self.result_data_dict["lines"],
                self.result_data_line[0].get('timestamp'),  # 开始时间
                self.result_data_line[-1].get('timestamp')
                ]  # 结束时间





