from utils.indicators.indicators_common import TempInd, Custom_indicators
import backtrader as bt
import numpy as np
from utils.module.wm_pattern_recognizer import WMPatternRecognizer


class IndicatorDataProcessor:
    def __init__(self, data, indicator_params):
        self.data = data
        self.indicator_params = indicator_params
        self.PCdata = Custom_indicators(data, indicator_params)
        self.TI = TempInd(data, diff=indicator_params.get("NumericalDifference", 1),
                          IsRightKBroken=indicator_params.get("IsRightKBroken", 1),
                          IsLeftKOffset=indicator_params.get("IsLeftKOffset", 1))
        self.result_data = []
        self.dict_index2ts = {}
        self.dict_ts2index = {}

    def process_next_data(self):
        mountain_poit = self.PCdata.lines.mountain_poit_line[0]
        if np.isnan(mountain_poit):
            mountain_poit = None

        current_kline_id = int(self.data.klineId[0])
        timestamp = self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),

        index = len(self.data)
        self.dict_index2ts[index] = timestamp
        self.dict_ts2index[timestamp] = index


        result_data = []
        result_data_original = []
        po_high = []
        po_low = []

        mountain_poit2 = self.TI.lines.mountain_poit[0]
        if not np.isnan(mountain_poit2):
            result_data.append({
                "kLineId": current_kline_id,
                "timestamp": self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": mountain_poit2,
                "index": len(self.data),
                "hloc": [self.data.high[0], self.data.low[1], self.data.open[0], self.data.close[0]],
            })

        mountain_poit3 = self.TI.lines.mountain_poit_original[0]
        if not np.isnan(mountain_poit3):
            result_data_original.append({
                "kLineId": current_kline_id,
                "timestamp": self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": mountain_poit3,
                "index": len(self.data),
            })

        if not np.isnan(self.TI.lines.mountain_poit_h_po[0]) and self.TI.lines.mountain_poit_h_po[0] != self.TI.lines.mountain_poit[0]:
            po_high.append({
                "kLineId": current_kline_id,
                "timestamp": self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.TI.lines.mountain_poit_h_po[0],
                "index": len(self.data)
            })
        if not np.isnan(self.TI.lines.mountain_poit_l_po[0]) and self.TI.lines.mountain_poit_l_po[0] != self.TI.lines.mountain_poit[0]:
            po_low.append({
                "kLineId": current_kline_id,
                "timestamp": self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": self.TI.lines.mountain_poit_l_po[0],
                "index": len(self.data)
            })

        self.result_data = result_data

        return result_data, result_data_original, po_high, po_low

    def get_pc_points(self):
        return self.result_data

    def process_stop_data(self, result_data, result_data_original):
        arr1 = np.array(self.TI.lines.mountain_poit.array)
        arr1 = arr1[~np.isnan(arr1)]
        if len(arr1) <= 1:
            notnallpoint = []
            return notnallpoint, [], [], [], [], [], [], []

        arr2 = np.array(self.TI.lines.mountain_poit_original.array)
        arr2 = arr2[~np.isnan(arr2)]
        offset_index = [True if i in arr1 else False for i in arr2][::-1]

        notnallpoint = [[index, value] for index, value in enumerate(self.TI.lines.mountain_poit.array) if not np.isnan(value)]
        false_indices = [i for i, value in enumerate(offset_index) if value is False]

        arr = np.array(self.TI.lines.mountain_poit_index.array)
        tmp = arr[~np.isnan(arr)][-1]
        xuhao = 0
        digits = int(self.data.digits[0])

        offset_allvalue_array = []
        title = []
        titlepeak = []
        titlebottol = []
        titlepeak_offset = []
        titlebottol_offset = []
        title_offset = []

        for index, value in enumerate(reversed(result_data)):
            spread = 0
            if index % 2 == 0 and index != 0:
                xuhao += 1
            dd = '顶' if tmp == 1 else '底'
            tmp *= -1

            if index + 1 < len(result_data):
                spread = value.get('price') - result_data[len(result_data) - index - 2].get('price')
                spread = "{:.{digits}f}".format(spread, digits=digits)

            if index + 1 < len(result_data):
                kidff = notnallpoint[len(result_data) - index - 1][0] - notnallpoint[len(result_data) - index - 2][0]

            timestamp = value.get("timestamp")

            title_str = ''
            if self.indicator_params.get("ShowTitlenumber", 1) == 1:
                title_str = title_str + dd + str(xuhao)
            if self.indicator_params.get("ShowTitlespread", 1) == 1:
                title_str += ' '
                title_str += str(spread)
            if self.indicator_params.get("ShowKlinediff", 1) == 1:
                title_str += ' K'
                title_str += str(kidff)
            if self.indicator_params.get("ShowTitletime", 1) == 1:
                title_str += ' \n '
                title_str = title_str + str(timestamp)
            else:
                title_str += ' \n '

            title.append({
                "kLineId": value.get("kLineId"),
                "timestamp": value.get("timestamp"),
                "price": value.get("price"),
                "value": title_str,
            })
            try:
                if not offset_index[index + 1]:
                    offset_allvalue_array.append(title_str)
                else:
                    offset_allvalue_array.append('')
            except:
                pass

        notnallpoint = [[index, value] for index, value in enumerate(self.TI.lines.mountain_poit_original.array) if not np.isnan(value)]
        tmp = arr[~np.isnan(arr)][-1]
        for index, i in enumerate(title):
            if not offset_index[index]:
                i['value'] = i['value'].replace('底', '偏底')
                i['value'] = i['value'].replace('顶', '偏顶')
            if tmp == 1 and index % 2 == 0:
                titlepeak.append(i)
            elif tmp == 1 and index % 2 == 1:
                titlebottol.append(i)
            elif tmp == -1 and index % 2 == 0:
                titlebottol.append(i)
            elif tmp == -1 and index % 2 == 1:
                titlepeak.append(i)
            try:
                if not offset_index[index + 1] and offset_index[index]:
                    i['value'] = ''
            except:
                pass

        arr = np.array(self.TI.lines.mountain_poit_index.array)
        tmp = arr[~np.isnan(arr)][-1]
        xuhao = 0

        for index, value in enumerate(reversed(result_data_original)):
            spread = 0
            if index % 2 == 0 and index != 0:
                xuhao += 1
            dd = '顶' if tmp == 1 else '底'
            tmp *= -1

            if index + 1 < len(result_data_original):
                spread = value.get('price') - result_data_original[len(result_data_original) - index - 2].get('price')
                spread = "{:.{digits}f}".format(spread, digits=digits)

            if index + 1 < len(result_data_original):
                kidff = notnallpoint[len(result_data_original) - index - 1][0] - notnallpoint[len(result_data_original) - index - 2][0]

            timestamp = value.get("timestamp")

            title_str = ''
            if self.indicator_params.get("ShowTitlenumberoffset", 1) == 1:
                title_str = title_str + dd + str(xuhao)
            if self.indicator_params.get("ShowTitlespreadoffset", 1) == 1:
                title_str += ' '
                title_str += str(spread)
            if self.indicator_params.get("ShowKlinediffoffset", 1) == 1:
                title_str += ' K'
                title_str += str(kidff)
            if self.indicator_params.get("ShowTitletimeoffset", 1) == 1:
                title_str += ' \n '
                title_str = title_str + str(timestamp)

            if not offset_index[index]:
                title_offset.append({
                    "kLineId": value.get("kLineId"),
                    "timestamp": value.get("timestamp"),
                    "price": value.get("price"),
                    "value": title_str,
                    "state": dd,
                })
            try:
                if not offset_index[index + 1]:
                    str_split = offset_allvalue_array[index].split(' ')
                    tmp_str = ''
                    if self.indicator_params.get("ShowTitlenumberoffset", 1) == 1:
                        tmp_str += ' '
                        tmp_str += str_split[0]
                    if self.indicator_params.get("ShowTitlespreadoffset", 1) == 1:
                        tmp_str += ' '
                        tmp_str += str_split[1]
                    if self.indicator_params.get("ShowKlinediffoffset", 1) == 1:
                        tmp_str += ' K'
                        tmp_str += str_split[2]
                    if self.indicator_params.get("ShowTitletimeoffset", 1) == 1:
                        tmp_str += ' \n '
                        tmp_str = tmp_str + str_split[3] + str_split[4]
                    title_str2 = ''
                    if self.indicator_params.get("ShowTitlenumber", 1) == 1:
                        title_str2 = title_str2 + dd + str(xuhao)
                    if self.indicator_params.get("ShowTitlespread", 1) == 1:
                        title_str2 += ' '
                        title_str2 += str(spread)
                    if self.indicator_params.get("ShowKlinediff", 1) == 1:
                        title_str2 += ' K'
                        title_str2 += str(kidff)
                    if self.indicator_params.get("ShowTitletime", 1) == 1:
                        title_str2 += ' \n '
                        title_str2 = title_str2 + str(timestamp)
                    if self.indicator_params.get("ShowTitlenumberoffset", 1) == 1 or self.indicator_params.get("ShowTitlespreadoffset", 1) == 1 or self.indicator_params.get("ShowKlinediffoffset", 1) == 1 or self.indicator_params.get("ShowTitletimeoffset", 1) == 1:
                        title_str2 = title_str2 + ' \n (偏)' + tmp_str
                    title_offset.append({
                        "kLineId": value.get("kLineId"),
                        "timestamp": value.get("timestamp"),
                        "price": value.get("price"),
                        "value": title_str2,
                        "state": dd,
                    })
            except:
                pass

        for index, i in enumerate(title_offset):
            if i.get('state') == '顶':
                titlepeak_offset.append(i)
            if i.get('state') == '底':
                titlebottol_offset.append(i)

        return notnallpoint, title, titlepeak, titlebottol, title_offset, titlepeak_offset, titlebottol_offset, offset_index

    def get_index_timestamp_maps(self):
        """返回索引到时间戳的映射，供形态识别使用。"""
        return self.dict_index2ts, self.dict_ts2index

class DataAnalysisOrganizer:
    def __init__(self, indicator_params, notnallpoint, data, result_data, po_high, po_low, titlepeak, titlebottol, titlepeak_offset, titlebottol_offset):
        self.indicator_params = indicator_params
        self.notnallpoint = notnallpoint
        self.data = data
        self.result_data = result_data
        self.po_high = po_high
        self.po_low = po_low
        self.titlepeak = titlepeak
        self.titlebottol = titlebottol
        self.titlepeak_offset = titlepeak_offset
        self.titlebottol_offset = titlebottol_offset

    def get_analysis(self):
        result_data_dict = {}
        result_data_dict["lines"] = [
            {
                "type": "brokenline",
                "color": self.indicator_params.get("TrendPackconnectionColor", "#00FF00"),
                "data": self.result_data
            },
            {
                "type": "bmp",
                "arrow": self.indicator_params.get("peakBmp", 1),
                "data": self.po_high
            },
            {
                "type": "bmp",
                "arrow": self.indicator_params.get("bottolBmp", 2),
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
            startime = self.data.datetime.datetime(self.notnallpoint[1][0] - self.data.buflen()).strftime('%Y-%m-%d %H:%M:%S')
            endtime = self.data.datetime.datetime(self.notnallpoint[-2][0] - self.data.buflen()).strftime('%Y-%m-%d %H:%M:%S')
        else:
            startime = None
            endtime = None

        return [result_data_dict["lines"], startime, endtime, None]


class ResponsePCData(bt.Strategy):
    """
    指标数据返回
    """
    def __init__(self, indicator_params, indicator_name, comments, begin_time=None):
        self.indicator_name = indicator_name
        self.comments = comments
        self.indicator_params = indicator_params
        self.data_processor = IndicatorDataProcessor(self.data, indicator_params)
        self.result_data = []
        self.result_data_original = []
        self.po_high = []
        self.po_low = []
        self.title = []
        self.titlepeak = []
        self.titlebottol = []
        self.title_offset = []
        self.titlepeak_offset = []
        self.titlebottol_offset = []
        self.notnallpoint = []
        self.open_list = []
        self.date = []
        self.order = None
        self.trades = []
        self.last_cash = self.broker.get_cash()
        self.last_value = self.broker.getvalue()
        self.data_line_count = 0
        self.trend_change_last = 0
        self.tm = 0
        self.result_data_dict = dict()

        self.zigzag = []
        self.pattern_recognizer = WMPatternRecognizer()

    def next(self):
        result_data, result_data_original, po_high, po_low = self.data_processor.process_next_data()
        # print("破", po_high)
        self.result_data.extend(result_data)  # 原点
        self.result_data_original.extend(result_data_original)  # 偏点
        self.po_high.extend(po_high)  # 破高
        self.po_low.extend(po_low)  # 破低

        if len(result_data) != 0:
            self.zigzag.append(result_data[0])
            dict_index2ts, dict_ts2index = self.data_processor.get_index_timestamp_maps()
            self.pattern_recognizer.analyze_zigzag_points(self.zigzag, dict_index2ts, dict_ts2index)





    def stop(self):
        (self.notnallpoint,
         self.title, self.titlepeak, self.titlebottol, self.title_offset,
         self.titlepeak_offset, self.titlebottol_offset, offset_index) = self.data_processor.process_stop_data(self.result_data, self.result_data_original)

    def get_analysis(self):
        pattern_titles = self.pattern_recognizer.get_pattern_titles()  # 获取原始形态标题列表
        self.result_data_dict["lines"] = [
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'top',
                "data": pattern_titles
            },
        ]

        analyzer = DataAnalysisOrganizer(self.indicator_params, self.notnallpoint, self.data, self.result_data,
                                         self.po_high, self.po_low, self.titlepeak, self.titlebottol,
                                         self.titlepeak_offset, self.titlebottol_offset)
        return analyzer.get_analysis()

        # return [self.result_data_dict["lines"], None, None]


