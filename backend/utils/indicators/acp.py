import numpy as np
import backtrader as bt
import time
from backtrader import indicator

class ResponseACPData(bt.Strategy):


    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data = []
        self.result_data_dict = dict()

        self.high_data = np.array(self.data.high)
        self.low_data = np.array(self.data.low)
        self.pHigh = []
        self.pLow = []
        self.Id_TS_dict = {}
        self.index_kid_dict = {}

        self.candel_length = 8

        self.pDir = 1
        self.zigzagPivots = []
        self.pattern = []

        self.distanceFromLastPivot = 0

        self.test = []

        self.pDir = 1

        self.newPiovt = False
        self.forceDoublePivot = False

        self.ohlc = {}

        self.lastZigzagPivots = []
        self.lastZigzagPivots_next = []
        self.Pattern_list = []  # 绘制的模式
        self.Pattern_class = []
        self.nextPiovt = []

        self.is_add = [[0,0,0]]

    def next(self):
        current_kline_id = int(self.data.klineId[0])
        self.Id_TS_dict[int(self.data.klineId[0])] = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')
        self.index_kid_dict[len(self)] = current_kline_id

        # print(len(self), current_kline_id, self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'))
        self.ohlc[len(self.data)] = {'open':self.data.open[0], 'high':self.data.high[0],
                                     'low':self.data.low[0], 'close':self.data.close[0],
                                     'time':self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                                     'index':len(self.data)}
        #------------------- 计算高点和低点 ----------------------------#
        candel_kline = len(self)+1  # current_kline是当前k线
        max_val = None
        min_val = None
        start = candel_kline - self.candel_length
        end = candel_kline
        # print(len(self), start, end)
        if start < 0:
            pass
        else:
            max_val = max(self.high_data[start:end])
            min_val = min(self.low_data[start:end])

        self.pHigh.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": max_val,
        })
        self.pLow.append({
            "kLineId": current_kline_id,
            "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "price": min_val,
        })

        #------------------- 计算轴枢点 ----------------------------#
        self.forceDoublePivot = False

        if len(self.zigzagPivots) > 0:
            lastPivot = self.zigzagPivots[-1]
            self.pDir = int(np.sign(lastPivot.get('dir')))
            self.distanceFromLastPivot += 1

        if len(self.zigzagPivots) > 1:
            llastPivot = self.zigzagPivots[-2]
            llastDir = int(np.sign(lastPivot.get('dir')))

            if self.pDir == 1 and min_val == self.data.low[0]:
                if min_val < llastPivot.get('price'):
                    self.forceDoublePivot = True
            elif self.pDir == -1 and max_val == self.data.high[0]:
                if max_val > llastPivot.get('price'):
                    self.forceDoublePivot = True

        overflow = self.distanceFromLastPivot >= self.candel_length
        self.newPiovt = False

        # 更大的
        if ((self.pDir == 1 and max_val == self.data.high[0]) or (self.pDir == -1 and min_val == self.data.low[0])) and len(self.zigzagPivots) >= 1:
            if self.pDir == 1:
                value = max_val
                ipivot = min_val
            else:
                value = min_val
                ipivot = max_val

            if value * self.pDir >= lastPivot.get('price') * self.pDir:
                self.zigzagPivots.pop(-1)  # 清除上一个
                self.newPiovt = True

                self.zigzagPivots.append({
                    "kLineId": current_kline_id,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                    "price": value,
                    "dir": self.pDir,
                    "form": 1,
                    "index": len(self),
                    "level": 1,
                })
                # print(self.zigzagPivots[-1])

                self.distanceFromLastPivot = 0
        # 反方向
        if ((self.pDir == 1 and min_val == self.data.low[0]) or (self.pDir == -1 and max_val == self.data.high[0])) and (not self.newPiovt or self.forceDoublePivot):

            if self.pDir == 1:
                value = min_val
            else:
                value = max_val

            self.newPiovt = True

            self.zigzagPivots.append({
                "kLineId": current_kline_id,
                "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                "price": value,
                "dir": -self.pDir,
                "form": 2,
                "index": len(self),
                "level": 1,
            })
            # print(self.zigzagPivots[-1])
            self.distanceFromLastPivot = 0
        # 超8进行更新
        if (overflow and not self.newPiovt):
            if self.pDir == 1:
                ipivot = min_val
                idata = self.data.low
            else:
                ipivot = max_val
                idata = self.data.high

            offset = 0
            for i in range(-7,0):
                if ipivot == idata[i]:
                    offset = i
                    break

            self.zigzagPivots.append({
                "kLineId": int(self.data.klineId[offset]),
                "timestamp": self.datas[0].datetime.datetime(offset).strftime('%Y-%m-%d %H:%M:%S'),
                "price": ipivot,
                "dir": -self.pDir,
                "form": 3,
                "index": len(self)+offset,
                "level": 1,
            })
            # print('offset', offset)
            # print(self.zigzagPivots[-1])
            self.newPiovt = True
            self.distanceFromLastPivot = abs(offset)

        if self.newPiovt and len(self.zigzagPivots) > 3:
            dir = np.sign(self.zigzagPivots[-1]['dir'])
            value = self.zigzagPivots[-1]['price']
            llastValue = self.zigzagPivots[-3]['price']
            newDir = dir * 2 if dir * value > dir * llastValue else dir
            self.zigzagPivots[-1]['dir'] = int(newDir)

        # ------------------- 根据轴枢点匹配模式 ----------------------------#
        if self.newPiovt and len(self.zigzagPivots) > 6:
            if self.zigzagPivots[-5] not in self.lastZigzagPivots:
                [valid, currentPattern] = find(self.zigzagPivots, self.ohlc)
                if valid:
                    # print(currentPattern['patternname'])

                    l1 = list(currentPattern['trendLine1'].keys())
                    self.Pattern_list.append([
                        {
                            "kLineId": self.index_kid_dict[l1[0]],
                            "price": currentPattern['trendLine1'][l1[0]],
                        },
                        {
                            "kLineId": self.index_kid_dict[l1[-1]],
                            "price": currentPattern['trendLine1'][l1[-1]],
                        }
                    ])
                    l2 = list(currentPattern['trendLine2'].keys())
                    self.Pattern_list.append([
                        {
                            "kLineId": self.index_kid_dict[l2[0]],
                            "price": currentPattern['trendLine2'][l2[0]],
                        },
                        {
                            "kLineId": self.index_kid_dict[l2[-1]],
                            "price": currentPattern['trendLine2'][l2[-1]],
                        }
                    ])
                    self.Pattern_class.append([
                        {
                            "kLineId":  self.index_kid_dict[l2[0]],
                            "price": max(currentPattern['trendLine1'][l1[0]],currentPattern['trendLine2'][l2[0]]),
                            "timestamp": self.Id_TS_dict.get(self.index_kid_dict[l2[0]]),
                            "value": currentPattern['patternname'],
                        }
                    ])
                    self.lastZigzagPivots = currentPattern['zigzagPivots'].copy()

        self.nextPiovt = nextlevel(self.zigzagPivots)
        while len(self.nextPiovt) > 6:
            [valid, currentPattern] = find(self.nextPiovt, self.ohlc)
            if valid and self.nextPiovt[-5]['index']!=self.zigzagPivots[-5]['index']:
                reciprocal_5_level = currentPattern['zigzagPivots'][-5]['level']
                reciprocal_5_index = currentPattern['zigzagPivots'][-5]['index']
                reciprocal_1_index = currentPattern['zigzagPivots'][-1]['index']
                tmp_con = [reciprocal_5_level, reciprocal_5_index, reciprocal_1_index]
                con = True
                for i in self.is_add:
                    if reciprocal_5_level == i[0] and reciprocal_5_index == i[1]:
                        con = False
                        break
                    if reciprocal_5_level == i[0] and reciprocal_5_index <= i[2]:
                        con = False
                        break

                if con:
                    self.is_add.append(tmp_con)
                    l1 = list(currentPattern['trendLine1'].keys())
                    self.Pattern_list.append([
                        {
                            "kLineId": self.index_kid_dict[l1[0]],
                            "price": currentPattern['trendLine1'][l1[0]],
                        },
                        {
                            "kLineId": self.index_kid_dict[l1[-1]],
                            "price": currentPattern['trendLine1'][l1[-1]],
                        }
                    ])
                    l2 = list(currentPattern['trendLine2'].keys())
                    self.Pattern_list.append([
                        {
                            "kLineId": self.index_kid_dict[l2[0]],
                            "price": currentPattern['trendLine2'][l2[0]],
                        },
                        {
                            "kLineId": self.index_kid_dict[l2[-1]],
                            "price": currentPattern['trendLine2'][l2[-1]],
                        }
                    ])
                    self.Pattern_class.append([
                        {
                            "kLineId":  self.index_kid_dict[l2[0]],
                            "price": min(currentPattern['trendLine1'][l1[0]],currentPattern['trendLine2'][l2[0]]),
                            "timestamp": self.Id_TS_dict.get(self.index_kid_dict[l2[0]]),
                            "value": currentPattern['patternname'],
                        }
                    ])
                else:
                    pass

            self.nextPiovt = nextlevel(self.nextPiovt)


    def stop(self):
        # print('self.Pattern_list', self.Pattern_list)
        # print(self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'))
        # print(len(self.zigzagPivots), len(self))

        # print('self.zigzagPivots', self.zigzagPivots)
        # for i in self.zigzagPivots:
        #     print(i)
        print(self.Pattern_class)
        pass

    def get_analysis(self):
        # 组织数据结构
        self.result_data_dict["lines"] = [
            # {
            #     "type": "line",
            #     "color": self.indicator_params.get("UpColor", "#FF0000"),
            #     "data": self.pHigh
            # },
            # {
            #     "type": "line",
            #     "color": self.indicator_params.get("UpColor", "#FF0000"),
            #     "data": self.pLow
            # },
            # {
            #     "type": "brokenline",
            #     "color": self.indicator_params.get("UpColor", "#00FFFF"),
            #     "data": self.nextPiovt
            # },
            {
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FFFF"),
                "data": self.zigzagPivots
            },
        ]

        for i in self.Pattern_list:
            self.result_data_dict["lines"].append({
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FF00"),
                "data": i
            })
        for i in self.Pattern_class:
            self.result_data_dict["lines"].append({
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                "position": 'bottom',
                "data": i
            })


        return [self.result_data_dict["lines"],
                None,
                None
                ]  # 结束时间

def nextlevel(zigzagPivots):
    # nextLevel = zigzagPivots.copy()
    nextLevel = []
    tempBullishPivot = {}
    tempBearishPivot = {}
    for i in zigzagPivots:
        lPivot = i.copy()
        lPivot['level'] = int(lPivot['level']) + 1
        dir = lPivot['dir']
        newDir = np.sign(dir)
        value = lPivot['price']
        if (len(nextLevel) > 3):
            lastPivot = nextLevel[-1]
            lastDir = np.sign(lastPivot['dir'])
            lastValue = lastPivot['price']
            if abs(dir) == 2:
                if lastDir == newDir:
                    if dir * lastDir < newDir * dir:
                        del nextLevel[0]
                    else:
                        tempPivot = tempBearishPivot if newDir > 0 else tempBullishPivot
                        if len(tempPivot) != 0:
                            nextLevel.append(tempPivot)
                            nextLevel = resdir(nextLevel)
                        else:
                            continue
                else:
                    tempFirstPivot = tempBullishPivot if newDir > 0 else tempBearishPivot
                    tempSecondPivot = tempBearishPivot if newDir > 0 else tempBullishPivot
                    if len(tempFirstPivot) != 0 and len(tempSecondPivot) != 0:
                        tempVal  = tempFirstPivot['price']
                        val = lPivot['price']
                        if (newDir*tempVal) > (newDir*val):
                            nextLevel.append(tempFirstPivot)
                            nextLevel = resdir(nextLevel)
                            nextLevel.append(tempSecondPivot)
                            nextLevel = resdir(nextLevel)
                nextLevel.append(lPivot)
                nextLevel = resdir(nextLevel)
                tempBullishPivot = {}
                tempBearishPivot = {}
                continue
            else:
                tempPivot = tempBullishPivot if newDir > 0 else tempBearishPivot
                if len(tempPivot) != 0:
                    tempDir = tempPivot['dir']
                    tempVal = tempPivot['price']
                    val = lPivot['price']
                    if val*dir > tempVal*dir:
                        if newDir > 0:
                            tempBullishPivot = lPivot
                        else:
                            tempBearishPivot = lPivot
                        continue
                else:
                    if newDir > 0:
                        tempBullishPivot = lPivot
                    else:
                        tempBearishPivot = lPivot
                    continue
        elif abs(dir) == 2:
            nextLevel.append(lPivot)
            # nextLevel = resdir(nextLevel)
    if (len(nextLevel) == len(zigzagPivots)):
        nextLevel = []
    return nextLevel

# 条形长度比例
def checkBarRatio(p1, p2, p3, barRatioLimit):
    p1_index = int(p1.get('index'))
    p2_index = int(p2.get('index'))
    p3_index = int(p3.get('index'))
    p1_price = p1.get('price')
    p2_price = p2.get('price')
    p3_price = p3.get('price')
    ratio = abs(((p3_price-p2_price)/(p3_index-p2_index)) - ((p3_price-p1_price)/(p3_index-p1_index)))
    r = abs(p3_index - p2_index) / abs(p2_index - p1_index)
    if 1/barRatioLimit >= r >= barRatioLimit:
        ratio = 0.1
        if ratio < 0.5:
            return True
        else:
            return False
    else:
        return False

# 计算斜率差
def getRatioDiff(p1, p2, p3):
    firstRatio = (p2.get('price') - p1.get('price')) / (p2.get('index') - p1.get('index'))
    secondRatio = (p3.get('price') - p2.get('price')) / (p3.get('index') - p2.get('index'))
    return abs(firstRatio-secondRatio)

def find(zigzagPivots, data):
    barRatioLimit = 0.0382
    currentPattern = []
    validPattern = checkBarRatio(zigzagPivots[-1], zigzagPivots[-3], zigzagPivots[-5], barRatioLimit)
    currentPattern = None
    if validPattern:
        trendPointArray1 = [zigzagPivots[-1], zigzagPivots[-3], zigzagPivots[-5]]
        trendPointArray2 = [zigzagPivots[-2], zigzagPivots[-4]]

        firstIndex = zigzagPivots[0]['index']
        lastIndex = zigzagPivots[-1]['index']
        firstDirection = 1 if zigzagPivots[-1]['price'] > zigzagPivots[-2]['price'] else -1
        # firstDirection = zigzagPivots[-1]['dir']
        # inpect 发送  第一个拐点的index， 最后一个拐点的index 方向
        startIndex = zigzagPivots[-5]['index']
        [valid1, trendLine1] = inspect(firstIndex, lastIndex, firstDirection, trendPointArray1, data, startIndex)
        [valid2, trendLine2] = inspect(firstIndex, lastIndex, -firstDirection, trendPointArray2, data, startIndex)
        if valid1 and valid2:
            # print(zigzagPivots[-5])
            ratioDiff = getRatioDiff(zigzagPivots[-5], zigzagPivots[-3], zigzagPivots[-1])
            if ratioDiff < 1:
                # print(ratioDiff,zigzagPivots[-5]['timestamp'],zigzagPivots[-1]['timestamp'])
                lastDir = int(np.sign(zigzagPivots[-1].get('price') - zigzagPivots[-3].get('price')))
                middle_pattern = {
                    'ratioDiff': ratioDiff,
                    'lastDir': lastDir,
                    'trendLine1': trendLine1,
                    'trendLine2': trendLine2,
                    'zigzagPivots': zigzagPivots,
                    'data': data,
                }
                # print(trendPointArray1)
                # print(trendPointArray2)
                # print('ok',middle_pattern['zigzagPivots'][-1])
                currentPattern = resolve(middle_pattern)
                # print('ok2',currentPattern['zigzagPivots'][-1])

            else:
                validPattern = False
        else:
            validPattern = False
    else:
        validPattern = False
    return [validPattern, currentPattern]

def inspect(firstindex, lastindex, firstDirection, PointArray, data, startIndex):

    if len(PointArray) == 3:
        l1 = new_line(PointArray[-3], PointArray[-1])
        [valid1, score1] = inspect_new(firstindex, lastindex, PointArray[-2], firstDirection, l1, data, startIndex)
        l2 = new_line(PointArray[-3], PointArray[-2])
        [valid2, score2] = inspect_new(firstindex, lastindex, PointArray[-1], firstDirection, l2, data, startIndex)
        l3 = new_line(PointArray[-2], PointArray[-1])
        [valid3, score3] = inspect_new(firstindex, lastindex, PointArray[-3], firstDirection, l3, data, startIndex)


        # print([valid1, score1], [valid2, score2], [valid3, score3])

        returnItem = 0
        if valid1 and score1 > max(score2, score3):
            returnItem = 1
        else:
            if valid2 and score2 > max(score1, score3):
                returnItem = 2
            else:
                returnItem = 3

        if returnItem == 1:
            return [valid1, l1]
        else:
            if returnItem == 2:
                return [valid2, l2]
            else:
                return [valid3, l3]

    elif len(PointArray) == 2:
        # print('####调用####', PointArray[-1]['timestamp'], PointArray[-2]['timestamp'], firstDirection)
        li = new_line(PointArray[0], PointArray[-1])
        [valid, score] = inspect_new(firstindex, lastindex, PointArray[0], firstDirection, li, data, startIndex)
        # print([valid, score])
        return [valid, li]

# 计算连接线的得分
def inspect_new(stratingBar, endingBar, otherBar, direction, line, data, lineStartIndex):
    valid = True
    score = 0
    total = 0
    # print(data) #
    # data[barIndex]
    # {'open': 2513.85, 'high': 2514.01, 'low': 2512.91, 'close': 2513.45, 'index': 987}
    # line是一个字典{950: 2517.18, 951: 2517.18, 952: 2517.18, 953: 2517.18}
    # print(f'方向{direction},实际连线{line}')
    # print(f'开始{stratingBar},结束{endingBar},其他{otherBar['index']}')
    # print(data[endingBar]['time'],direction)
    key_list = list(line.keys())
    line_start = key_list[0]
    line_end = key_list[-1]
    pivots_start = lineStartIndex
    pivots_end = endingBar
    o = otherBar['index']
    if pivots_start < line_start or pivots_end > line_end:
        line = reline(line, pivots_start, pivots_end)

    for barIndex in range(stratingBar, endingBar):

        total += 1
        if barIndex not in line.keys():
            continue
            # print(barIndex, data[barIndex])

        barPrice = data[barIndex]['high'] if direction > 0 else data[barIndex]['low']
        barOutPrice = data[barIndex]['low'] if direction > 0 else data[barIndex]['high']
        linePrice = line[barIndex]
        # print(
        #     f'linePrice: {barIndex, linePrice, data[barIndex]['time']},  '
        #     f'open: {data[barIndex]['open']},  '
        #     f'close: {data[barIndex]['close']}  ,'
        #     f'barOutPrice: {barOutPrice},  '
        #     f'barPrice: {barPrice}'
        # )

        if (linePrice*direction) < min(data[barIndex]['open']*direction, data[barIndex]['close']*direction):
            valid = False
            # print('false')
            break

        if linePrice*direction >= barOutPrice*direction and linePrice*direction <= barPrice*direction:
            score += 1
            # print('ture')
        elif otherBar['index'] == barIndex:
            valid = False
            # print('false')
            break
        if len(line) > 100:
            valid = False
            break
    # print(valid, score, total, direction)
    return [valid and (score / total) < 0.2, score]

def new_line(p1, p2):
    start = 0
    end = 0
    num = 0
    price_diff = 0
    s_price = 0
    end_price = 0
    if p1.get('index') < p2.get('index'):
        start = p1['index']
        end = p2['index']
        num = end - start
        s_price = p1['price']
        end_price = p2['price']
        price_diff = (p2['price'] - p1['price'])/num

    else:
        start = p2['index']
        end = p1['index']
        num = end - start
        s_price = p2['price']
        end_price = p1['price']
        price_diff = (p1['price'] - p2['price'])/num
        # print(f'是我,开始{start},结束{end},多少个{num},开始价格{s_price},价差{price_diff}')
    line = {}
    for i in range(num):
        line[start+i] = s_price + i * price_diff

    line[end] = end_price
    return line

# 根据轴枢点更新上下线的开始点和结束点
def reline(line, start, end):
    # start 和 end 是新线的边界
    # print(start, end)
    # print(line)
    line_new = line.copy()
    line_value = list(line.values())
    lins_index = list(line.keys())
    price_diff = (line_value[-1] - line_value[0])/(lins_index[-1]-lins_index[0])

    if start != lins_index[0]:
        num = lins_index[0] - start
        tmp_line =  {}
        for i in list(range(num+1))[::-1]:
            tmp_line[lins_index[0] - i] = line_value[0] - i * price_diff
        line_new = {**tmp_line, **line_new}

    if end != lins_index[-1]:
        num = end - lins_index[-1]
        tmp_line = {}
        for i in range(num+1):
            tmp_line[lins_index[-1] + i] = line_value[-1] + i * price_diff
        line_new = {**line_new, **tmp_line}

    return line_new

# 进行模式识别
def resolve(pattern):
    '''
    接收
    middle_pattern = {
    'ratioDiff': ratioDiff,
    'lastDir': lastDir,
    'trendLine1': trendLine1,
    'trendLine2': trendLine2,
    'zigzagPivots': zigzagPivots,
    'data': data,
}
    :param pattern:
    :return:
    '''
    # print('#--------------------------------')
    flatRatio = 0.2

    firstIndex = pattern['zigzagPivots'][-5]['index']  # 起点索引
    lastIndex = pattern['zigzagPivots'][-1]['index']  # 结束索引
    # print(lastIndex)
    # 根据枢轴点进行填充
    filling_l1 = reline(pattern['trendLine1'], firstIndex, lastIndex)
    filling_l2 = reline(pattern['trendLine2'], firstIndex, lastIndex)
    # print(filling_l1)
    # print(filling_l2)

    # print(firstIndex, lastIndex)
    t1p1 = filling_l1[firstIndex]
    t1p2 = filling_l1[lastIndex]
    t2p1 = filling_l2[firstIndex]
    t2p2 = filling_l2[lastIndex]
    # print(t1p1, t2p1, t1p2, t2p2)

    upperAngle = (t1p2 - min(t2p1, t2p2))/(t1p1 - min(t2p1, t2p2)) if t1p1 > t2p1 else\
                 (t2p2 - min(t1p1, t1p2))/(t2p1 - min(t1p1, t1p2))

    lowerAngle = (t2p2 - max(t1p1, t1p2))/(t2p1 - max(t1p1, t1p2)) if t1p1 > t2p1 else\
                 (t1p2 - max(t2p1, t2p2))/(t1p1 - max(t2p1, t2p2))

    upperLineDir = 0
    if upperAngle > 1 + flatRatio:
        upperLineDir = 1
    else:
        if upperAngle < 1 - flatRatio:
            upperLineDir = -1

    lowerLineDir = 0
    if lowerAngle > 1 + flatRatio:
        lowerLineDir = -1
    else:
        if lowerAngle < 1 - flatRatio:
            lowerLineDir = 1

    startDiff = abs(t1p1 - t2p1)
    endDiff = abs(t1p2 - t2p2)

    minDiff = min(startDiff, endDiff)
    barDiff = lastIndex - firstIndex
    priceDiff = abs(startDiff - endDiff)/barDiff

    probableConvergingBars = minDiff / priceDiff

    isExpanding = abs(t1p2 - t2p2) > abs(t1p1 - t2p1)
    isContracting = abs(t1p2 - t2p2) < abs(t1p1 - t2p1)

    isChannel = probableConvergingBars > 2 * barDiff or (not isExpanding and not isContracting) or (
                upperLineDir == 0 and lowerLineDir == 0)
    invalid = np.sign(t1p1 - t2p1) != np.sign(t1p2 - t2p2)

    patternType  = 0
    if invalid:
        pattern_type = 0
    elif isChannel:
        if upperLineDir > 0 and lowerLineDir > 0:
            pattern_type = 1
        elif upperLineDir < 0 and lowerLineDir < 0:
            pattern_type = 2
        elif upperLineDir == 0 and lowerLineDir == 0:
            pattern_type = 3
        else:
            pattern_type = 3
    elif isExpanding:
        if upperLineDir > 0 and lowerLineDir > 0:
            pattern_type = 4
        elif upperLineDir < 0 and lowerLineDir < 0:
            pattern_type = 5
        elif upperLineDir > 0 and lowerLineDir < 0:
            pattern_type = 6
        elif upperLineDir > 0 and lowerLineDir == 0:
            pattern_type = 7
        elif upperLineDir == 0 and lowerLineDir < 0:
            pattern_type = 8
        else:
            pattern_type = -2
    elif isContracting:
        if upperLineDir > 0 and lowerLineDir > 0:
            pattern_type = 9
        elif upperLineDir < 0 and lowerLineDir < 0:
            pattern_type = 10
        elif upperLineDir < 0 and lowerLineDir > 0:
            pattern_type = 11
        elif lowerLineDir == 0:
            if upperLineDir < 0:
                pattern_type = 12
            else:
                pattern_type = 1
        elif upperLineDir == 0:
            if lowerLineDir > 0:
                pattern_type = 13
            else:
                pattern_type = 2
        else:
            pattern_type = -3
    else:
        pattern_type = -4

    pattern['pattern_type'] = pattern_type
    pattern['patternname'] = pattern_dict_cn[pattern_type]
    pattern['trendLine1'] = filling_l1
    pattern['trendLine2'] = filling_l2
    return pattern

def resdir(zigzagPivots):
    dir = np.sign(zigzagPivots[-1]['dir'])
    value = zigzagPivots[-1]['price']
    llastValue = zigzagPivots[-3]['price']
    newDir = dir * 2 if dir * value > dir * llastValue else dir
    zigzagPivots[-1]['dir'] = int(newDir)
    return zigzagPivots


pattern_dict = {
    1: "Ascending Channel",
    2: "Descending Channel",
    3: "Ranging Channel",
    4: "Rising Wedge (Expanding)",
    5: "Falling Wedge (Expanding)",
    6: "Diverging Triangle",
    7: "Ascending Triangle (Expanding)",
    8: "Descending Triangle (Expanding)",
    9: "Rising Wedge (Contracting)",
    10: "Falling Wedge (Contracting)",
    11: "Converging Triangle",
    12: "Descending Triangle (Contracting)",
    13: "Ascending Triangle (Contracting)",
    0: "0",
    "default": "Error"
}
pattern_dict_cn = {
    1: "上升通道",
    2: "下降通道",
    3: "区间通道",
    4: "上升楔形（扩张）",
    5: "下降楔形（扩张）",
    6: "发散三角形",
    7: "上升三角形（扩张）",
    8: "下降三角形（扩张）",
    9: "上升楔形（收缩）",
    10: "下降楔形（收缩）",
    11: "收敛三角形",
    12: "下降三角形（收缩）",
    13: "上升三角形（收缩）",
    0: "0",
    "default": "Error"
}
