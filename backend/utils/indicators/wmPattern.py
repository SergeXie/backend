import backtrader as bt
import pandas as pd
import numpy as np
import math
import random


class WMData(bt.Indicator):
    # 定义指标线：zigzag连线、高点、低点
    lines = ('zigzag', 'high', 'low')

    # 定义参数，与原MQ4代码保持一致
    params = (
        ('inp_depth', 12),  # 寻找极值的K线范围
        ('inp_deviation', 5),  # 波动阈值
        ('inp_backstep', 3),  # 回退步数，清理附近无效极值
    )

    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data_dict = dict()


        # 初始化状态变量
        self.whatlookfor = 0  # 0=寻找初始极值，1=寻找高点，-1=寻找低点
        self.last_low = 0.0
        self.last_high = 0.0

        self.high_data = np.array(self.data.high)
        self.low_data = np.array(self.data.low)

        self.zigzag = []
        self.zigzagPivots = []
        self.is_new_zigzag = False

        self.test = []
        self.test2 = []

        self.M = []

        self.title = []

        self.dict_index2ts = {}
        self.dict_ts2index = {}



        # 缓存历史高低点，用于极值过滤
        self.high_buffer = np.zeros(len(self.high_data))
        self.low_buffer = np.zeros(len(self.low_data))

        # 确保数据长度足够时再开始计算
        self.addminperiod(self.p.inp_depth)

    def i_lowest(self, data):
        # print(self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),data)
        # """寻找指定范围内的最低值（Backtrader版本）"""
        return np.min(data)

    def i_highest(self, data):
        """寻找指定范围内的最高值"""
        return np.max(data)

    def next(self):
        current_kline_id = int(self.data.klineId[0])
        index=len(self)
        ts=self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')
        self.dict_index2ts[index] = ts
        self.dict_ts2index[ts] = index


        if len(self) < self.p.inp_depth:
            return

        i = len(self)
        # --------------------- 计算低点极值 ---------------------
        extremum1 = self.i_lowest(self.data.low.get(size=self.p.inp_depth))   # 12范围内的最小值
        # print(extremum)
        if extremum1 == self.last_low:  # 保留极值点的位置
            extremum1 = 0.0
        else:  # 表示极值点的位置
            # self.last_low = extremum1
            # 直接比较价格差
            if self.low_data[i] - extremum1 > 0:  # 如果价差大于阈值，就更新
                extremum = 0.0
            else:
                # 修复：确保pos不超过数据长度
                for back in range(0, -3):
                    pos = i + back
                    if self.low_buffer[pos] != 0 and self.low_buffer[pos] > extremum1:
                        self.low_buffer[pos] = 0.0

        if extremum1 != 0 and self.data.low[0]==extremum1:
            # print(extremum1)
            self.low_buffer[i] = extremum1
            self.test.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price":  extremum1,
            })

        # --------------------- 计算高点极值 ---------------------
        extremum = self.i_highest(self.data.high.get(size=self.p.inp_depth))

        if extremum == self.last_high:
            extremum = 0.0
        else:
            # self.last_high = extremum
            if extremum - self.high_data[i] > 0:
                extremum = 0.0
            else:
                # 修复：确保pos不超过数据长度
                for back in range(0, -3):
                    pos = i + back
                    if self.high_buffer[pos] != 0 and self.high_buffer[pos] < extremum:
                        self.high_buffer[pos] = 0.0

        if extremum != 0 and self.data.high[0]==extremum:

            self.high_buffer[i] = extremum
            self.test2.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price":  extremum,
            })

        # --------------------- 生成ZigZag连线 ---------------------
        # 1低点找高，-1找低
        # print(self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),self.whatlookfor, self.high_buffer[i], self.low_buffer[i])
        # print(self.last_high, self.last_low)

        self.is_new_zigzag = False

        if self.whatlookfor == 0:
            if self.lines.high[0] != 0:
                self.last_high = self.high_data[i]
                self.whatlookfor = -1
                # self.lines.zigzag[0] = self.last_high
                self.zigzag.append({
                    "kLineId": current_kline_id,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.last_high,
                    "index": len(self),
                })
                self.is_new_zigzag = True
            if self.lines.low[0] != 0:
                self.last_low = self.low_data[i]
                self.whatlookfor = 1
                # self.lines.zigzag[0] = self.last_low
                self.zigzag.append({
                    "kLineId": current_kline_id,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.last_low,
                    "index": len(self),
                })
                self.is_new_zigzag = True
        elif self.whatlookfor == 1:
            if self.low_buffer[i] != 0 and self.low_buffer[i] < self.last_low and self.high_buffer[i] == 0:  # 更大？
                self.last_low = self.low_buffer[i]
                # self.lines.zigzag[0] = self.last_low
                self.zigzag.pop(-1)
                self.zigzag.append({
                    "kLineId": current_kline_id,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.last_low,
                    "index": len(self),
                })
                self.is_new_zigzag = True
            if self.high_buffer[i] != 0 and self.low_buffer[i] == 0:  # 反向
                self.last_high = self.high_buffer[i]
                self.last_low = self.data.low[0]
                # self.lines.zigzag[0] = self.last_high
                self.zigzag.append({
                    "kLineId": current_kline_id,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.last_high,
                    "index": len(self),
                })
                self.whatlookfor = -1
                self.is_new_zigzag = True
        elif self.whatlookfor == -1:
            if self.high_buffer[i] != 0 and self.high_buffer[i] > self.last_high and self.low_buffer[i] == 0:
                self.last_high = self.high_buffer[i]
                # self.lines.zigzag[0] = self.last_high
                self.zigzag.pop(-1)
                self.zigzag.append({
                    "kLineId": current_kline_id,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.last_high,
                    "index": len(self),
                })
                self.is_new_zigzag = True
            if self.low_buffer[i] != 0 and self.high_buffer[i] == 0:
                self.last_low = self.low_buffer[i]
                self.last_high = self.data.high[0]
                # self.lines.zigzag[0] = self.last_low
                self.zigzag.append({
                    "kLineId": current_kline_id,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.last_low,
                    "index": len(self),
                })
                self.whatlookfor = 1
                self.is_new_zigzag = True

        # print(self.zigzag[0])

        if self.is_new_zigzag == True and len(self.zigzag) > 5:
            self.judgment_m_pattern()
            self.judgment_w_pattern()

    def judgment_m_pattern(self):
        l_val = self.zigzag[-4]['price']
        r_val = self.zigzag[-2]['price']
        l_d_val = self.zigzag[-5]['price']
        r_d_val = self.zigzag[-1]['price']
        head_val = self.zigzag[-3]['price']

        # 距离20根
        con1 = (self.zigzag[-3]['index'] - self.zigzag[-5]['index']) > 20
        # 影线
        # con2 = l_d_val > r_d_val
        # 左肩高
        con3 = l_val > r_val
        # 脚最低
        con4 = head_val > max(l_d_val, r_d_val) and head_val < min(l_val, r_val)

        # 不重复
        con5 = True
        if len(self.title) > 1:
            if self.zigzag[-3]['timestamp'] == self.title[-1]['timestamp']:
                con5 = False

        if con1 and con3 and con4 and con5:
            self.title.append({
                "kLineId": self.zigzag[-3]['kLineId'],
                "timestamp": self.zigzag[-3]['timestamp'],
                "price": self.zigzag[-3]['price'],
                "value": "M形态",
                "start": self.zigzag[-5]['timestamp'],
                "end": self.zigzag[-1]['timestamp'],
                "high": self.zigzag[-4]['price'],
                "low": min(self.zigzag[-1]['price'], self.zigzag[-5]['price']),
            })

    def judgment_w_pattern(self):
        l_val = self.zigzag[-4]['price']
        r_val = self.zigzag[-2]['price']
        l_d_val = self.zigzag[-5]['price']
        r_d_val = self.zigzag[-1]['price']
        head_val = self.zigzag[-3]['price']

        # 距离20根
        con1 = (self.zigzag[-3]['index'] - self.zigzag[-5]['index']) > 20
        # 影线
        # con2 = l_d_val > r_d_val
        # 左肩高
        con3 = l_val < r_val
        # 脚最低
        con4 = head_val < min(l_d_val, r_d_val) and head_val > max(l_val, r_val)

        # 不重复
        con5 = True
        if len(self.title) > 1:
            if self.zigzag[-3]['timestamp'] == self.title[-1]['timestamp']:
                con5 = False

        if con1 and con3 and con4 and con5:
            self.title.append({
                "kLineId": self.zigzag[-3]['kLineId'],
                "timestamp": self.zigzag[-3]['timestamp'],
                "price": self.zigzag[-3]['price'],
                "value": "W形态",
                "start": self.zigzag[-5]['timestamp'],
                "end": self.zigzag[-1]['timestamp'],
                "high": self.zigzag[-4]['price'],
                "low": min(self.zigzag[-1]['price'], self.zigzag[-5]['price']),
            })

    def stop(self):
        print('有被调用')
        for i in self.title:
            start = i.get('start')
            end = i.get('end')
            high = i.get('high')
            low = i.get('low')
            # print(start, end, high, low)

            ind_start = self.dict_ts2index.get(start)
            start_time = ind_start
            ind_end = self.dict_ts2index.get(end)
            end_time = ind_end
            if ind_start > 400:
                # 生成一个10到99之间的随机整数（包括10和99）
                random_number = random.randint(100, 400)
                start_time -= random_number  # 是整型
            if self.data.buflen() - ind_end > 400:
                random_number = random.randint(100, 400)
                end_time += random_number

            self.M.append({
                "time": [self.dict_index2ts.get(start_time), self.dict_index2ts.get(end_time)],
                "leftTop": {
                    "time": start,
                    "price": high
                },
                "rigthBottom": {
                    "time": end,
                    "price": low
                },
            })
            print(self.M[-1])


class ResponseWMData(bt.Strategy):
    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data_dict = {}

        self.WM = WMData(self.data, indicator_params=self.indicator_params,
                         indicator_name=self.indicator_name, comments=self.comments)
    def get_analysis(self):
        # print(self.zigzagPivots)
        # 组织数据结构
        self.result_data_dict["lines"] = [
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'top',
                "data": self.WM.title
            },
            # {
            #     "type": "brokenline",
            #     "color": self.indicator_params.get("UpColor", "#FF0000"),
            #     "data": self.test
            # },
            # {
            #     "type": "brokenline",
            #     "color": self.indicator_params.get("UpColor", "#FF0000"),
            #     "data": self.test2
            # },
            {
                "type": "picture",
                "data": self.WM.M
            },
            {
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FFFF"),
                "data": self.WM.zigzag
            },
        ]

        return [self.result_data_dict["lines"],
                self.datas[0].datetime.datetime(
                    self.indicator_params.get("Periods", 10) - self.data.buflen() + 1).strftime(
                    '%Y-%m-%d %H:%M:%S'),  # 开始时间
                self.datas[0].datetime.datetime(0).strftime(
                    '%Y-%m-%d %H:%M:%S')]  # 结束时间
