from utils.indicators.indicators_common import TempInd, Custom_indicators
import backtrader as bt
import numpy as np


class ResponsePCData(bt.Strategy):
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
        trend_change_now = self.TI.lines.mountain_poit_index[0]  # 获取当前
        if not self.position and (self.data.buflen() - self.data_line_count > 1):  # 没有持仓
            if self.broker.get_cash() < 0:
                self.tm = -2
            if trend_change_now == -1 and self.tm == 0:
                # print("没有持仓，开始买入")
                self.order = self.buy()
                self.buy_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.high[0]})
                self.trend_change_last = trend_change_now
                mou_mon = self.data.close[0]
            elif trend_change_now == 1 and self.tm == 0:
                # print("没有持仓，开始卖出")
                self.order = self.sell()
                self.sell_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.low[0]})
                # print(self.position)
                self.trend_change_last = trend_change_now
                mou_mon = self.data.close[0]
            if not np.isnan(self.TI.lines.left[-1]):
                le = self.TI.lines.left[-1]
            else:
                le = 0
            # le = self.TI.lines.left[-1] if not np.isnan(self.TI.lines.left[-1]) else 0
            if self.tm == -1 and self.data.low[0] > self.data.low[-int(le)]:
                self.order = self.buy()
                self.buy_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.high[0]})
                # print("开始买入")
                self.trend_change_last = -1
            elif self.tm == 1 and self.data.high[0] < self.data.high[-int(le)]:
                self.order = self.sell()
                self.sell_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.low[0]})
                # print("开始卖出")
                self.trend_change_last = 1
            else:
                self.tm = 0
        else:
            if trend_change_now != self.trend_change_last:
                close_now = self.data.close[0]
                if trend_change_now == -1 and self.position.size < 0 :  # 如果当前为底 持有空头仓位
                    # print("平仓")
                    self.close()  # 平仓
                    self.close_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.low[0]})
                    self.trend_change_last = trend_change_now
                    self.tm = -1   # 只有当前的k的最低比底的底大 ，表明上升趋势， 开始做多

                elif trend_change_now == 1 and self.position.size > 0:  # 如果当前为顶 持有多头仓位

                    # print("对多头平仓")
                    self.close()  # 平仓
                    self.close_poit.append({
                        "kLineId": current_kline_id,
                        "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                        "price": self.data.low[0]})
                    self.trend_change_last = trend_change_now
                    self.tm = 1   # 当前的k的最高比顶的高大 ，表明下降趋势， 开始做空

        # 实现最后的平仓
        if (self.data_line_count == self.data.buflen()-1) and self.position:
            pass
            # print("end", self.position.size)
            # self.close()

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

    def notify_trade(self, trade):
        if trade.isopen:
            self.result_data_dict["buyselldata"] = [
                {
                    "type": "open",
                    "orderStatus": self.orderstatus,
                    "kLineId": int(self.data.klineId[0]),
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.data.close[0],
                },
            ]
            self.OpenkLineId = int(self.data.klineId[0])
            self.orderstatus = 'bug' if trade.size > 0 else 'sell'

        if trade.isclosed:
            self.result_data_dict["buyselldata"] = [
                {
                    "type": "close",
                    "openkLineId": self.OpenkLineId,
                    "orderStatus": self.orderstatus,
                    "kLineId": int(self.data.klineId[0]),
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": self.data.close[0],
                },
            ]

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
        print("是否偏移", offset_index)
        # 得到非空的绘画点
        self.notnallpoint = [[index, value] for index, value in enumerate(self.TI.lines.mountain_poit.array) if
                             not np.isnan(value)]
        print("绘图点的index（针对全长）和value", self.notnallpoint)
        false_indices = [i for i, value in enumerate(offset_index) if value is False]
        print("是否偏移index（针对顶底点）", false_indices)
        print(len(self.result_data), len(self.result_data_original), len(offset_index))
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
            print(i)
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
                self.result_data_dict["buyselldata"]
                ]
