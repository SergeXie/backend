import backtrader as bt
import numpy as np

import backtrader as bt


def Current(pos, vals):
    c_str = ''
    val1 = np.nan
    val2 = np.nan
    if pos >= 0:
        if pos == 1:
            c_str = "SMS: "
            val1 = vals[0, 1]
            val2 = vals[0, 3]
        elif pos == 2:
            c_str = "BMS: "
            val1 = vals[1, 1]
            val2 = vals[1, 3]
        elif pos > 2:
            c_str = "BMS: "
            val1 = vals[2, 1]
            val2 = vals[2, 3]
    elif pos <= 0:
        if pos == -1:
            c_str = "SMS: "
            val1 = vals[3, 1]
            val2 = vals[3, 3]
        elif pos == -2:
            c_str = "BMS: "
            val1 = vals[4, 1]
            val2 = vals[4, 3]
        elif pos < -2:
            c_str = "BMS: "
            val1 = vals[5, 1]
            val2 = vals[5, 3]

    return [c_str, val1, val2]


class ResponseSMCPData(bt.Strategy):
    params = (
        ('prd', 20),
        ('resp', 7),
        ('bull', True),
        ('bear', True),
        ('showPD', True),

    )

    def __init__(self, indicator_params, indicator_name, comments):

        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.prd = self.indicator_params.get("Periods", 20)
        self.showPrice = self.indicator_params.get("ShowPrice", 1)
        self.showProbability = self.indicator_params.get("ShoeProbability", 1)

        self.result_data = []
        self.result_data_dict = dict()
        self.pvtHi = []
        self.pvtLo = []
        self.close_data = np.array(self.data.close)
        self.high_data = np.array(self.data.high)
        self.low_data = np.array(self.data.low)
        self.Up = self.data.high
        self.Dn = self.data.low
        self.pos = 0
        self.last_pos = [0]
        self.CreateLine = []
        self.CreateLine2 = []
        self.CreateLabel = []
        self.CreateLabel2 = []
        self.BarState = []
        self.BarStateText1 = {}
        self.BarStateText2 = {}
        self.iUp = np.nan
        self.iDn = np.nan
        self.ts = ''
        self.Id_TS_dict = {}
        self.vals = np.zeros((9, 4))
        self.txt_array = []
        self.last_price = []

        self.resp = 7

    def next(self):
        if len(self)<20:
            self.iUp = int(self.data.klineId[0])
            self.iDn = int(self.data.klineId[0])
            return
        self.Id_TS_dict[int(self.data.klineId[0])] = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')

        current_kline_id = int(self.data.klineId[0])
        # print(self.lines.Up[0], self.lines.Dn[0], self.data.high[0])
        # 更新up和dn
        self.Up[0] = self.Up[-1] if self.Up[-1] > self.Up[0] else self.Up[0]
        self.Dn[0] = self.Dn[-1] if self.Dn[-1] < self.Dn[0] else self.Dn[0]

        # 计算轴枢点
        current_kline = len(self)-self.prd  # current_kline是当前k线
        max_val = None
        min_val = None
        start = current_kline - self.prd
        end = current_kline + self.prd+1
        if end > self.data.buflen() or start < 0:
            pass
        else:
            max_val = max(self.high_data[start:end])
            min_val = min(self.low_data[start:end])
        # print(max_val, min_val)
        if max_val == self.high_data[current_kline] and max_val:
            self.Up[0] = max_val
        if min_val == self.low_data[current_kline] and min_val:
            self.Dn[0] = min_val
        # 画轴点连线
        # print(self.Up[0], self.Dn[0])
        drawFlag1 = False
        if self.Up[0] > self.Up[-1]:
            if self.pos <= 0:
                drawFlag1 = True
                self.CreateLine.append([
                    {
                        "kLineId": self.iUp,
                        "price": self.Up[-1],
                    },
                    {
                        "kLineId": current_kline_id,
                        "price": self.Up[-1],
                    }
                ])
                self.CreateLabel.append([
                    {
                        "kLineId": self.iUp,
                        "price": self.Up[-1],
                        "timestamp": self.Id_TS_dict.get(self.iUp),
                        "value": str(self.Up[-1]) + "[CHoCH]",
                    }
                ])
                self.pos = 1
                self.vals[6, 0] = self.vals[6, 0] +1
            elif self.pos == 1 and self.Up[0] > self.Up[-1] and self.Up[-1]==self.Up[-self.resp]:
                drawFlag1 = True
                self.CreateLine.append([
                    {
                        "kLineId": self.iUp,
                        "price": self.Up[-1],
                    },
                    {
                        "kLineId": current_kline_id,
                        "price": self.Up[-1],
                    }
                ])
                self.CreateLabel.append([
                    {
                        "kLineId": self.iUp,
                        "price": self.Up[-1],
                        "timestamp": self.Id_TS_dict.get(self.iUp),
                        "value": str(self.Up[-1]) + "[SMS]",
                    }
                ])
                self.pos = 2
                self.vals[6, 1] = self.vals[6, 1] + 1
            elif self.pos > 1 and self.Up[0] > self.Up[-1] and self.Up[-1] == self.Up[-self.resp]:
                drawFlag1 = True
                self.CreateLine.append([
                    {
                        "kLineId": self.iUp,
                        "price": self.Up[-1],
                    },
                    {
                        "kLineId": current_kline_id,
                        "price": self.Up[-1],
                    }
                ])
                self.CreateLabel.append([
                    {
                        "kLineId": self.iUp,
                        "price": self.Up[-1],
                        "timestamp": self.Id_TS_dict.get(self.iUp),
                        "value": str(self.Up[-1]) + "[BMS]",
                    }
                ])
                self.pos += 1
                self.vals[6, 2] = self.vals[6, 2] + 1
            self.iUp = int(self.data.klineId[0])
            self.ts = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
        elif self.Up[0] < self.Up[-1]:
            self.iUp = int(self.data.klineId[-20])
            self.ts = self.datas[0].datetime.datetime(-20).strftime('%Y-%m-%d %H:%M:%S'),

        drawFlag2 = False
        if self.Dn[0] < self.Dn[-1]:
            if self.pos >= 0:
                drawFlag2 = True
                self.CreateLine2.append([
                    {
                        "kLineId": self.iDn,
                        "price": self.Dn[-1],
                    },
                    {
                        "kLineId": current_kline_id,
                        "price": self.Dn[-1],
                    }
                ])
                self.CreateLabel2.append([
                    {
                        "kLineId": self.iDn,
                        "price": self.Dn[-1],
                        "timestamp": self.Id_TS_dict.get(self.iDn),
                        "value": str(self.Dn[-1]) + "[CHoCH]",
                    }
                ])
                self.pos = -1
                self.vals[7, 0] = self.vals[7, 0] + 1
            elif self.pos == -1 and self.Dn[0] < self.Dn[-1] and self.Dn[-1] == self.Dn[-self.resp]:
                drawFlag2 = True
                self.CreateLine2.append([
                    {
                        "kLineId": self.iDn,
                        "price": self.Dn[-1],
                    },
                    {
                        "kLineId": current_kline_id,
                        "price": self.Dn[-1],
                    }
                ])
                self.CreateLabel2.append([
                    {
                        "kLineId": self.iDn,
                        "price": self.Dn[-1],
                        "timestamp": self.Id_TS_dict.get(self.iDn),
                        "value": str(self.Dn[-1])+"[SMS]",
                    }
                ])
                self.pos = -2
                self.vals[7, 1] = self.vals[7, 1] + 1
            elif self.pos < -1 and self.Dn[0] < self.Dn[-1] and self.Dn[-1] == self.Dn[-self.resp]:
                drawFlag2 = True
                self.CreateLine2.append([
                    {
                        "kLineId": self.iDn,
                        "price": self.Dn[-1],
                    },
                    {
                        "kLineId": current_kline_id,
                        "price": self.Dn[-1],
                    }
                ])
                self.CreateLabel2.append([
                    {
                        "kLineId": self.iDn,
                        "price": self.Dn[-1],
                        "timestamp": self.Id_TS_dict.get(self.iDn),
                        "value": str(self.Dn[-1])+"[BMS]",
                    }
                ])
                self.pos -= 1
                self.vals[7, 2] = self.vals[7, 2] + 1
            self.iDn = int(self.data.klineId[0])
        elif self.Dn[0] > self.Dn[-1]:
            self.iDn = int(self.data.klineId[-20])

        self.pvtHi.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": self.Up[0],
        })
        self.pvtLo.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": self.Dn[0],
        })

        # 画概率
        self.last_pos.append(self.pos)
        if self.last_pos[-2] != self.last_pos[-1]:
            if ((self.last_pos[-1] > 0 and self.last_pos[-2] > 0) or (self.last_pos[-1] < 0 and self.last_pos[-2] < 0)):
                if self.vals[8, 0] < self.vals[8, 1]:
                    self.vals[8, 2] = self.vals[8, 2] + 1
                else:
                    self.vals[8, 3] = self.vals[8, 3] + 1
            else:
                if self.vals[8, 0] > self.vals[8, 1]:
                    self.vals[8, 2] = self.vals[8, 2] + 1
                else:
                    self.vals[8, 3] = self.vals[8, 3] + 1

            buC0 = self.vals[0, 0]
            buC1 = self.vals[0, 2]
            buS0 = self.vals[1, 0]
            buS1 = self.vals[1, 2]
            buB0 = self.vals[2, 0]
            buB1 = self.vals[2, 2]
            beC0 = self.vals[3, 0]
            beC1 = self.vals[3, 2]
            beS0 = self.vals[4, 0]
            beS1 = self.vals[4, 2]
            beB0 = self.vals[5, 0]
            beB1 = self.vals[5, 2]
            tbuC = self.vals[6, 0]
            tbuS = self.vals[6, 1]
            tbuB = self.vals[6, 2]
            tbeC = self.vals[7, 0]
            tbeS = self.vals[7, 1]
            tbeB = self.vals[7, 2]

            if (self.last_pos[-2] == 1 or self.last_pos[-2] == 0) and self.last_pos[-1] < 0:
                self.vals[0, 0] = buC0 + 1
                if tbuC != 0:
                    self.vals[0, 1] = round(((buC0 + 1) / tbuC) * 100, 2)

            if (self.last_pos[-2] == 1 or self.last_pos[-2] == 0) and self.last_pos[-1] == 2:
                self.vals[0, 2] = buC1 + 1
                if tbuC != 0:
                    self.vals[0, 3] = round(((buC1 + 1) / tbuC) * 100, 2)

            if self.last_pos[-2] == 2 and self.last_pos[-1] < 0:
                self.vals[1, 0] = buS0 + 1
                if tbuS != 0:
                    self.vals[1, 1] = round(((buS0 + 1) / tbuS) * 100, 2)

            if self.last_pos[-2] == 2 and self.last_pos[-1] > 2:
                self.vals[1, 2] = buS1 + 1
                if tbuS != 0:
                    self.vals[1, 3] = round(((buS1 + 1) / tbuS) * 100, 2)

            if self.last_pos[-2] > 2 and self.last_pos[-1] < 0:
                self.vals[2, 0] = buB0 + 1
                if tbuB != 0:
                    self.vals[2, 1] = round(((buB0 + 1) / tbuB) * 100, 2)

            if self.last_pos[-2] > 2 and self.last_pos[-1] > self.last_pos[-2]:
                self.vals[2, 2] = buB1 + 1
                if tbuB != 0:
                    self.vals[2, 3] = round(((buB1 + 1) / tbuB) * 100, 2)

            # Bear
            if (self.last_pos[-2] == -1 or self.last_pos[-2] == 0) and self.last_pos[-1] > 0:
                self.vals[3, 0] = beC0 + 1
                if tbeC != 0:
                    self.vals[3, 1] = round(((beC0 + 1) / tbeC) * 100, 2)

            if (self.last_pos[-2] == -1 or self.last_pos[-2] == 0) and self.last_pos[-1] == -2:
                self.vals[3, 2] = beC1 + 1
                if tbeC != 0:
                    self.vals[3, 3] = round(((beC1 + 1) / tbeC) * 100, 2)

            if self.last_pos[-2] == -2 and self.last_pos[-1] > 0:
                self.vals[4, 0] = beS0 + 1
                if tbeS != 0:
                    self.vals[4, 1] = round(((beS0 + 1) / tbeS) * 100, 2)

            if self.last_pos[-2] == -2 and self.last_pos[-1] < -2:
                self.vals[4, 2] = beS1 + 1
                if tbeS != 0:
                    self.vals[4, 3] = round(((beS1 + 1) / tbeS) * 100, 2)

            if self.last_pos[-2] < -2 and self.last_pos[-1] > 0:
                self.vals[5, 0] = beB0 + 1
                if tbeB != 0:
                    self.vals[5, 1] = round(((beB0 + 1) / tbeB) * 100, 2)

            if self.last_pos[-2] < -2 and self.last_pos[-1] < self.last_pos[-2]:
                self.vals[5, 2] = beB1 + 1
                if tbeB != 0:
                    self.vals[5, 3] = round(((beB1 + 1) / tbeB) * 100, 2)

            [c_str, val1, val2] = Current(self.last_pos[-1], self.vals)

            txt1 = "CHoCH: " + str(val1)
            txt2 = c_str + str(val2)
            self.txt_array = [txt1, txt2]
            self.vals[8, 0] = val1
            self.vals[8, 1] = val2

            if drawFlag1:
                self.CreateLabel[-1][0]['value'] = self.CreateLabel[-1][0]['value'] + txt1 + txt2
                # print(self.CreateLabel[-1][0])
                pass

            if drawFlag2:
                self.CreateLabel2[-1][0]['value'] = self.CreateLabel2[-1][0]['value'] + txt1 + txt2
                # print(self.CreateLabel2[-1][0])
                pass


    def stop(self):
        print(self.Id_TS_dict)
        current_kline_id = int(self.data.klineId[0])
        # print(self.Id_TS_dict)
        #---------------- 画线旁边的概率 ----------------#
        str1 = self.txt_array[0] if self.pos < 0 else self.txt_array[1]
        str2 = self.txt_array[0] if self.pos > 0 else self.txt_array[1]
        print(str1, str2)


        #---------------- 画线旁边的框 -----------------#
        PremiumTop = self.Up[0] - (self.Up[0] - self.Dn[0]) * .1
        PremiumBot = self.Up[0] - (self.Up[0] - self.Dn[0]) * .25
        DiscountTop = self.Dn[0] + (self.Up[0] - self.Dn[0]) * .25
        DiscountBot = self.Dn[0] + (self.Up[0] - self.Dn[0]) * .1
        MidTop = self.Up[0] - (self.Up[0] - self.Dn[0]) * .45
        MidBot = self.Dn[0] + (self.Up[0] - self.Dn[0]) * .45
        loc = max(self.iUp, self.iDn)

        self.BarState.append([
            {
                "kLineId": loc,
                "price": self.Up[0],
            },
            {
                "kLineId": current_kline_id,
                "price": self.Up[0],
            }
        ])
        self.BarStateText1 = {
            "kLineId": current_kline_id,
            "price": self.Up[0],
            "timestamp": self.Id_TS_dict.get(current_kline_id),
            "value": str(self.Up[0]) + str1
        }
        self.BarState.append([
            {
                "kLineId": loc,
                "price": self.Dn[0],
            },
            {
                "kLineId": current_kline_id,
                "price": self.Dn[0],
            }
        ])
        self.BarStateText2 = {
            "kLineId": current_kline_id,
            "price": self.Dn[0],
            "timestamp": self.Id_TS_dict.get(current_kline_id),
            "value": str(self.Dn[0]) + str2
        }
        self.BarState.append([
            {
                "kLineId": loc,
                "price": PremiumTop,
            },
            {
                "kLineId": current_kline_id,
                "price": PremiumBot,
            }
        ])
        self.BarState.append([
            {
                "kLineId": loc,
                "price": DiscountTop,
            },
            {
                "kLineId": current_kline_id,
                "price": DiscountBot,
            }
        ])
        self.BarState.append([
            {
                "kLineId": loc,
                "price": MidTop,
            },
            {
                "kLineId": current_kline_id,
                "price": MidBot,
            }
        ])
        # 最后的概率框旁边的概率
        self.last_price.append([
            {
                "kLineId": current_kline_id,
                "price": PremiumTop,
                "timestamp": self.Id_TS_dict.get(current_kline_id),
                "value": str(round(PremiumTop, 2))
            }
        ])
        self.last_price.append([
            {
                "kLineId": current_kline_id,
                "price": PremiumBot,
                "timestamp": self.Id_TS_dict.get(current_kline_id),
                "value": str(round(PremiumBot, 2))
            }
        ])
        self.last_price.append([
            {
                "kLineId": current_kline_id,
                "price": DiscountTop,
                "timestamp": self.Id_TS_dict.get(current_kline_id),
                "value": str(round(DiscountTop, 2))
            }
        ])
        self.last_price.append([
            {
                "kLineId": current_kline_id,
                "price": DiscountBot,
                "timestamp": self.Id_TS_dict.get(current_kline_id),
                "value": str(round(DiscountBot, 2))
            }
        ])
        self.last_price.append([
            {
                "kLineId": current_kline_id,
                "price": MidTop,
                "timestamp": self.Id_TS_dict.get(current_kline_id),
                "value": str(round(MidTop, 2))
            }
        ])
        self.last_price.append([
            {
                "kLineId": current_kline_id,
                "price": MidBot,
                "timestamp": self.Id_TS_dict.get(current_kline_id),
                "value": str(round(MidBot, 2))
            }
        ])


        # ---------------- 画胜率 -----------------#

        W = self.vals[8, 2]
        L = self.vals[8, 3]
        WR = round((W / (W + L)) * 100, 2)
        print(f"WIN: {W}, LOSS: {L}, Profitability: {WR}")

    def get_analysis(self):
        W = self.vals[8, 2]
        L = self.vals[8, 3]
        WR = round((W / (W + L)) * 100, 2)
        # 组织数据结构
        self.result_data_dict["lines"] = [
            # {
            #     "type": "line",
            #     "color": self.indicator_params.get("TrendDMAColor", "#FF0000"),
            #     "data": self.result_data
            # },
            # {
            #     "type": "brokenline",
            #     "color": self.indicator_params.get("TrendDMAColor", "#FF0000"),
            #     "data": self.pvtHi
            # },
            # {
            #     "type": "brokenline",
            #     "color": self.indicator_params.get("TrendDMAColor", "#FFFF00"),
            #     "data": self.pvtLo
            # },
        ]
        if self.params.bull:
            for i in self.CreateLine:
                # print(i)
                self.result_data_dict["lines"].append({
                    "type": "brokenline",
                    "color": self.indicator_params.get("UpColor", "#00FF00"),
                    "data": i
                })
            for i in self.CreateLabel:
                # print(i)
                self.result_data_dict["lines"].append({
                    "type": "text",
                    "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                    "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                    "position": 'top',
                    "data": i
                })
        if self.params.bear:
            for i in self.CreateLine2:
                self.result_data_dict["lines"].append({
                    "type": "brokenline",
                    "color": self.indicator_params.get("DnColor", "#FF0000"),
                    "data": i
                })
            for i in self.CreateLabel2:
                # print(i)
                self.result_data_dict["lines"].append({
                    "type": "text",
                    "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                    "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                    "position": 'bottom',
                    "data": i
                })
        if self.params.showPD:
            # print(self.BarState)
            for i in self.BarState:
                self.result_data_dict["lines"].append({
                    "type": "graphical",
                    "BackgroundColor": self.indicator_params.get("TrendDMAColor", "#0000FF"),
                    "lineWidth": 1,
                    "lineStyle": 1,
                    "color": "#FFFFFF",
                    "globalAlpha": 0.1,
                    "data": i
                })
            for i in self.BarState[:2]:
                self.result_data_dict["lines"].append({
                    "type": "brokenline",
                    "color": self.indicator_params.get("TrendDMAColor", "#0000FF"),
                    "data": i
                })

        if self.showProbability == 1:
            self.result_data_dict["lines"].append({
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                "position": 'top',
                "data": [self.BarStateText1]
            })
            self.result_data_dict["lines"].append({
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                "position": 'bottom',
                "data": [self.BarStateText2]
            })
        if self.showPrice == 1:
            for i in self.last_price:
                print(i)
                self.result_data_dict["lines"].append({
                    "type": "text",
                    "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                    "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                    "position": 'right',
                    "data": i
                })




        self.result_data_dict["lines"].append({
            "type": "bottomText",
            "color": self.indicator_params.get("DnColor", "#FF0000"),
            "data": f"WIN: {W}, LOSS: {L}, Profitability: {WR}"
        })





        return [self.result_data_dict["lines"],
                # self.result_data[0].get('timestamp'),  # 开始时间
                # self.result_data[-1].get('timestamp')
                None,
                None
                ]  # 结束时间


