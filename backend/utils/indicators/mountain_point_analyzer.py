import numpy as np

class MountainPointAnalyzer:
    def __init__(self, data, indicator_params, TI, CI):
        """
        data: Backtrader data feed (需要有 close, high, low, datetime, klineId 等)
        indicator_params: 用户传入参数 dict
        TI: TempInd 实例（已初始化）
        CI: Custom_indicators 实例（已初始化）
        """
        self.data = data
        self.indicator_params = indicator_params
        self.TI = TI
        self.CI = CI

        self.result_data = []
        self.result_data_original = []
        self.po_high = []
        self.po_low = []
        self.title = []
        self.title_offset = []
        self.titlepeak = []
        self.titlebottol = []
        self.titlepeak_offset = []
        self.titlebottol_offset = []

        # 配置项
        self.ShowTitlenumber = indicator_params.get("ShowTitlenumber", 1)
        self.ShowTitletime = indicator_params.get("ShowTitletime", 1)
        self.ShowTitlespread = indicator_params.get("ShowTitlespread", 1)
        self.ShowKlinediff = indicator_params.get("ShowKlinediff", 1)
        self.ShowTitlenumberoffset = indicator_params.get("ShowTitlenumberoffset", 1)
        self.ShowTitletimeoffset = indicator_params.get("ShowTitletimeoffset", 1)
        self.ShowTitlespreadoffset = indicator_params.get("ShowTitlespreadoffset", 1)
        self.ShowKlinediffoffset = indicator_params.get("ShowKlinediffoffset", 1)
        self.peakBmp = indicator_params.get("peakBmp", 1)
        self.bottolBmp = indicator_params.get("bottolBmp", 2)

    def calculate(self):
        arr1 = np.array(self.TI.lines.mountain_poit.array)
        arr1 = arr1[~np.isnan(arr1)]

        if len(arr1) <= 1:
            self.notnallpoint = []
            return

        arr2 = np.array(self.TI.lines.mountain_poit_original.array)
        arr2 = arr2[~np.isnan(arr2)]
        offset_index = [True if i in arr1 else False for i in arr2][::-1]

        self.notnallpoint = [
            [index, value]
            for index, value in enumerate(self.TI.lines.mountain_poit.array)
            if not np.isnan(value)
        ]

        arr = np.array(self.TI.lines.mountain_poit_index.array)
        tmp = arr[~np.isnan(arr)][-1] if len(arr[~np.isnan(arr)]) > 0 else 1
        xuhao = 0
        digits = int(self.data.digits[0])

        for index, value in enumerate(reversed(self.result_data)):
            if index % 2 == 0 and index != 0:
                xuhao += 1
            dd = '顶' if tmp == 1 else '底'
            tmp *= -1

            spread = 0
            if index + 1 < len(self.result_data):
                spread = value.get('price') - self.result_data[len(self.result_data) - index - 2].get('price')
                spread = "{:.{digits}f}".format(spread, digits=digits)

            if index + 1 < len(self.result_data):
                kidff = (
                    self.notnallpoint[len(self.result_data) - index - 1][0]
                    - self.notnallpoint[len(self.result_data) - index - 2][0]
                )
            else:
                kidff = 0

            timestamp = value.get("timestamp")

            title_str = ""
            if self.ShowTitlenumber:
                title_str += dd + str(xuhao)
            if self.ShowTitlespread:
                title_str += " " + str(spread)
            if self.ShowKlinediff:
                title_str += " K" + str(kidff)
            if self.ShowTitletime:
                title_str += "\n" + str(timestamp)

            self.title.append(
                {
                    "kLineId": value.get("kLineId"),
                    "timestamp": timestamp,
                    "price": value.get("price"),
                    "value": title_str,
                }
            )

        # 分割顶/底
        for i in self.title:
            if "顶" in i["value"]:
                self.titlepeak.append(i)
            elif "底" in i["value"]:
                self.titlebottol.append(i)

    def get_result(self):
        lines = [
            {
                "type": "brokenline",
                "color": self.indicator_params.get("TrendPackconnectionColor", "#00FF00"),
                "data": self.result_data
            },
            {
                "type": "bmp",
                "arrow": self.peakBmp,
                "data": self.po_high
            },
            {
                "type": "bmp",
                "arrow": self.bottolBmp,
                "data": self.po_low
            },
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": "top",
                "data": self.titlepeak[::-1]
            },
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": "bottom",
                "data": self.titlebottol[::-1]
            },
        ]

        if len(self.notnallpoint) > 2:
            startime = self.data.datetime.datetime(self.notnallpoint[1][0] - self.data.buflen()).strftime('%Y-%m-%d %H:%M:%S')
            endtime = self.data.datetime.datetime(self.notnallpoint[-2][0] - self.data.buflen()).strftime('%Y-%m-%d %H:%M:%S')
        else:
            startime = None
            endtime = None

        return [lines, startime, endtime]

        # return {
        #     "lines": lines,
        #     "start_time": startime,
        #     "end_time": endtime,
        # }
