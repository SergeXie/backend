import pickle
import backtrader as bt
import numpy as np
import pandas as pd
from utils.module.zigzag_calculator_byclass import ZigZagCalculator
from utils.module.dll import train_two_classifiers, predict_binary
from utils.module.dtw import calc_dtw_distance
from utils.module.wm_pattern_recognizer import WMPatternRecognizer2
import warnings
from datetime import datetime
from sklearn.exceptions import UndefinedMetricWarning
from utils.module.wm_pattern import run_strategy

# 过滤特定警告
warnings.filterwarnings('ignore', category=UndefinedMetricWarning)


class ResWMpredictByMathData(bt.Strategy):

    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data_dict = dict()
        self.Id_TS_dict = {}
        self.Ts_to_hloc = {}
        self.inp_depth = 12

        self.BarState = []
        self.BarStateText = []
        self.verticalBrokenline = []
        self.W_sum = 0
        self.M_sum = 0
        self.all_kline_data = []

        # 实例化独立的算法类
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer2()

        goods = self.indicator_params.get('Kline_goods')
        periods = self.indicator_params.get('Kline_period')
        endTime = self.indicator_params.get('end_time')
        beginTime = '2020-01-01 00:00:00'
        self.all_wm_pattern = run_strategy(goods, periods, endTime, beginTime)
        from apis.v1.platform import select_multiple_goods_k_lines
        # res = await select_multiple_goods_k_lines(goods, periods, beginTime, endTime)
        # print('全部参数', self.all_wm_pattern[-1])
        # print(res.data)


        # 确保数据长度足够时再开始计算
        self.addminperiod(self.inp_depth)

    def next(self):
        self.Id_TS_dict[int(self.data.klineId[0])] = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')

        # 确保数据长度足够
        if len(self) < self.inp_depth:
            return

        # 准备当前K线数据，传递给ZigZagCalculator
        current_kline_data = {
            "kLineId": self.data.klineId[0],  # 假设datafeed提供了klineId
            "timestamp": self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "open": self.data.open[0],
            "high": self.data.high[0],
            "low": self.data.low[0],
            "close": self.data.close[0],
            "volume": self.data.volume[0],
        }
        self.all_kline_data.append(current_kline_data)
        self.Ts_to_hloc[self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')] = [self.data.high[0],
                                                 self.data.low[0],
                                                 self.data.open[0],
                                                 self.data.close[0]]

        # 调用ZigZag算法类的处理方法
        # process_kline会返回是否产生了新的zigzag点，如果产生，就通知形态识别器
        new_zigzag_point_or_updated = self.zigzag_calculator.process_kline(current_kline_data)



    def stop(self):
        digit = int(self.datas[0].digits[0])
        zigzag_points = self.zigzag_calculator.get_zigzag_points(as_dict=False)
        print('看中了',zigzag_points)

        zigzag_list = []
        for zig in zigzag_points:
            zigzag_list.append(zig)
            self.pattern_recognizer.analyze_zigzag_points(zigzag_list)


        #________________保存全部的wm形态_____________________________#

        # wm_pattern = self.pattern_recognizer.get_all_wm_patterns()
        # for pattern in wm_pattern:
        #     # 获取该模式时间范围内的所有K线
        #     target_klines = get_klines_in_range(
        #         all_klines=self.all_kline_data,  # 替换为实际的全量K线数据
        #         start_timestamp=pattern['start_timestamp'],
        #         end_timestamp=pattern['end_timestamp']
        #     )
        #     pattern['target_klines'] = target_klines
        #     pattern['period'] = "H4"
        #
        # print(len(wm_pattern))
        #
        # with open('./dataset/all_wm_pattern_kline_h4.pkl', 'wb') as file:
        #     pickle.dump(wm_pattern, file)

        # # 加载数据
        # with open('./dataset/all_wm_pattern_kline_h4.pkl', 'rb') as file:
        #     h4 = pickle.load(file)
        # with open('./dataset/all_wm_pattern_kline_h1.pkl', 'rb') as file:
        #     h1 = pickle.load(file)
        # with open('./dataset/all_wm_pattern_kline_m5.pkl', 'rb') as file:
        #     m5 = pickle.load(file)
        # with open('./dataset/all_wm_pattern_kline_m15.pkl', 'rb') as file:
        #     m15 = pickle.load(file)
        # with open('./dataset/all_wm_pattern_kline_m30.pkl', 'rb') as file:
        #     m30 = pickle.load(file)
        # print(type(h4), len(h1), len(m5), len(m15), len(m30))
        #
        # all = m5+m15+m30+h1+h4
        # with open('./dataset/all_wm_pattern_kline.pkl', 'wb') as file:
        #     pickle.dump(all, file)
        # ________________保存全部的wm形态_____________________________#
        # with open('./dataset/all_wm_pattern_kline.pkl', 'rb') as file:
        #     all_wm_pattern = pickle.load(file)
        # for i in all_wm_pattern:
        #     if "W" in i['pattern_type']:
        #         self.W_sum += 1
        #     if "M" in i['pattern_type']:
        #         self.M_sum += 1


        # print(len(all_wm_pattern))
        # print(all_wm_pattern[-5:])


        #_______________计算相似度____________________
        time_format = "%Y-%m-%d %H:%M:%S"  # 定义时间类型


        all_wm_pattern_kline = []
        time_list = []
        for i in self.all_wm_pattern:
            all_wm_pattern_kline.append(klines_to_dataframe(merge_klines(i.target_klines)))
            datetime_list = datetime.strptime(i.start_timestamp, time_format)
            time_list.append(datetime_list)

        show_pattern = self.indicator_params.get("show_mabye_pattern")

        if show_pattern == 1:  # 可能形态
            # -----------获取最后一个可能的m，用于计算概率----------------
            for maybe_m in self.pattern_recognizer.get_maybe_m_patterns():
                # maybe_m = self.pattern_recognizer.get_maybe_m_patterns()[1]
                last_m_start = maybe_m.start
                base_time = datetime.strptime(last_m_start, time_format)
                early_indices = [idx for idx, t in enumerate(time_list) if t < base_time]
                # print(early_indices)
                early_times = self.all_wm_pattern[:early_indices[-1]]
                # print("对应早于基准时间的元素：", early_times)

                last_m_end = maybe_m.end
                last_m_kline = get_klines_in_range(self.all_kline_data, last_m_start, last_m_end)
                last_m_kline_df = klines_to_dataframe(merge_klines(last_m_kline))
                # print(last_m_kline_df)
                # print(all_wm_pattern_kline[-1])
                # print(calc_dtw_distance(last_m_kline_df, last_m_kline_df))
                distance = [calc_dtw_distance(last_m_kline_df, i) for i in all_wm_pattern_kline]
                weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
                m_zigzag_points = [i.points for i in early_times if "M" in i.value]
                weight = [weight[index] for index, i in enumerate(early_times) if "M" in i.value]

                p = probability(m_zigzag_points, datafrom='m',weight=weight)
                print("m概率:", p)

                price_diff = self.Ts_to_hloc.get(maybe_m.start_third)[1] - self.Ts_to_hloc.get(maybe_m.start_four)[0]  # 高点到低点的价差
                klineId = maybe_m.four_kLineId
                for index, i in enumerate(p['probabilities']):
                    base_price = self.Ts_to_hloc.get(maybe_m.start_third)[1]
                    price = base_price + price_diff * index
                    price = np.round(price, digit)
                    # print(i)
                    i = np.round(i*100, 2)
                    # print('来了', price,self.Id_TS_dict.get(klineId))
                    # print(index)
                    self.BarStateText.append({
                        "kLineId": klineId,
                        "price": price,
                        "timestamp": self.Id_TS_dict.get(klineId),
                        "value": f"{np.round(price, 2)}: " + str(i) + '%'
                    })
                self.verticalBrokenline.append(
                    {
                        "kLineId": klineId,
                        "price": price,
                        "price2": [base_price-price_diff, base_price + price_diff * 2],
                        "timestamp": self.Id_TS_dict.get(klineId),
                    })


            # -----------获取最后一个可能的w，用于计算概率----------------
            for maybe_w in self.pattern_recognizer.get_maybe_w_patterns():
                # maybe_w = self.pattern_recognizer.get_maybe_w_patterns()[-1]
                last_w_start = maybe_w.start
                base_time = datetime.strptime(last_w_start, time_format)
                early_indices = [idx for idx, t in enumerate(time_list) if t < base_time]
                early_times = self.all_wm_pattern[:early_indices[-1]]

                last_w_end = maybe_w.end
                last_w_kline = get_klines_in_range(self.all_kline_data, last_w_start, last_w_end)
                last_w_kline_df = klines_to_dataframe(merge_klines(last_w_kline))

                distance = [calc_dtw_distance(last_w_kline_df, i) for i in all_wm_pattern_kline]
                weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
                w_zigzag_points = [i.points for i in early_times if "W" in i.value]
                weight = [weight[index] for index, i in enumerate(early_times) if "W" in i.value]

                p = probability(w_zigzag_points, datafrom='w',weight=weight)
                print("w概率:", p)

                price_diff = self.Ts_to_hloc.get(maybe_w.start_third)[0] - self.Ts_to_hloc.get(maybe_w.start_four)[1]  # 高点到低点的价差
                klineId = maybe_w.four_kLineId
                for index, i in enumerate(p['probabilities']):
                    base_price = self.Ts_to_hloc.get(maybe_w.start_third)[0]
                    price = base_price + price_diff * index
                    price = np.round(price, digit)
                    # print(i)
                    i = np.round(i*100, 2)
                    # print('来了', price,self.Id_TS_dict.get(klineId))
                    # print(index)
                    self.BarStateText.append({
                        "kLineId": klineId,
                        "price": price,
                        "timestamp": self.Id_TS_dict.get(klineId),
                        "value": f"{np.round(price, 2)}: " + str(i) + '%'
                    })
                self.verticalBrokenline.append(
                    {
                        "kLineId": klineId,
                        "price": price,
                        "price2": [base_price-price_diff, base_price + price_diff * 2],
                        "timestamp": self.Id_TS_dict.get(klineId),
                    })


        elif show_pattern == 0:  # 确认形态
            for standard_m in self.pattern_recognizer.get_standard_m_patterns():
                last_m_start = standard_m.start
                base_time = datetime.strptime(last_m_start, time_format)
                early_indices = [idx for idx, t in enumerate(time_list) if t < base_time]
                early_times = self.all_wm_pattern[:early_indices[-1]]
                last_m_end = standard_m.end
                last_m_kline = get_klines_in_range(self.all_kline_data, last_m_start, last_m_end)
                last_m_kline_df = klines_to_dataframe(merge_klines(last_m_kline))
                distance = [calc_dtw_distance(last_m_kline_df, i) for i in all_wm_pattern_kline]
                weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
                m_zigzag_points = [i.points for i in early_times if "M" in i.value]
                weight = [weight[index] for index, i in enumerate(early_times) if "M" in i.value]
                p = probability(m_zigzag_points, datafrom='m',weight=weight)
                print("m概率:", p)
                price_diff = self.Ts_to_hloc.get(standard_m.start_third)[1] - self.Ts_to_hloc.get(standard_m.start_four)[0]  # 高点到低点的价差
                klineId = standard_m.end_kLineId
                for index, i in enumerate(p['probabilities'][-2:]):
                    base_price = standard_m.end_price + price_diff
                    price = base_price + price_diff * index
                    price = np.round(price, digit)
                    # print(i)
                    i = np.round(i*100, 2)
                    # print('来了', price,self.Id_TS_dict.get(klineId))
                    # print(index)
                    self.BarStateText.append({
                        "kLineId": klineId,
                        "price": price,
                        "timestamp": self.Id_TS_dict.get(klineId),
                        "value": f"{np.round(price, 2)}: " + str(i) + '%'
                    })
                self.verticalBrokenline.append(
                    {
                        "kLineId": klineId,
                        "price": price,
                        "price2": [standard_m.end_price, standard_m.end_price + price_diff * 2],
                        "timestamp": self.Id_TS_dict.get(klineId),
                    })

            for standard_w in self.pattern_recognizer.get_standard_w_patterns():
                last_w_start = standard_w.start
                base_time = datetime.strptime(last_w_start, time_format)
                early_indices = [idx for idx, t in enumerate(time_list) if t < base_time]
                early_times = self.all_wm_pattern[:early_indices[-1]]
                last_w_end = standard_w.end
                last_w_kline = get_klines_in_range(self.all_kline_data, last_w_start, last_w_end)
                last_w_kline_df = klines_to_dataframe(merge_klines(last_w_kline))
                distance = [calc_dtw_distance(last_w_kline_df, i) for i in all_wm_pattern_kline]
                weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
                w_zigzag_points = [i.points for i in early_times if "W" in i.value]
                weight = [weight[index] for index, i in enumerate(early_times) if "W" in i.value]
                p = probability(w_zigzag_points, datafrom='w',weight=weight)
                print("w概率:", p)
                price_diff = self.Ts_to_hloc.get(standard_w.start_third)[0] - self.Ts_to_hloc.get(standard_w.start_four)[1]  # 高点到低点的价差
                klineId = standard_w.end_kLineId
                for index, i in enumerate(p['probabilities'][-2:]):
                    base_price = standard_w.end_price + price_diff
                    price = base_price + price_diff * index
                    price = np.round(price, digit)
                    i = np.round(i*100, 2)
                    self.BarStateText.append({
                        "kLineId": klineId,
                        "price": price,
                        "timestamp": self.Id_TS_dict.get(klineId),
                        "value": f"{np.round(price, 2)}: " + str(i) + '%'
                    })
                self.verticalBrokenline.append(
                {
                    "kLineId": klineId,
                    "price": price,
                    "price2": [standard_w.end_price, standard_w.end_price + price_diff * 2],
                    "timestamp": self.Id_TS_dict.get(klineId),
                })





    def get_analysis(self):
        zigzag_points = self.zigzag_calculator.get_zigzag_points()
        self.result_data_dict["lines"] = [
            {
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FFFF"),
                "data": zigzag_points
            },
        ]
        # 画横线
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
        # 写概率
        for i in self.BarStateText:
            # print(i)
            self.result_data_dict["lines"].append({
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                "position": 'right',
                "data": [i],
            })
        self.result_data_dict["lines"].append({
            "type": "bottomText",
            "color": self.indicator_params.get("DnColor", "#FF0000"),
            "data": f"W形态个数: {self.W_sum}, M形态个数: {self.M_sum},"
        })
        for i in self.verticalBrokenline:
            self.result_data_dict["lines"].append({
                "type": "verticalBrokenline",
                "color": self.indicator_params.get("DnColor", "#FF0000"),
                "data": [i]
            })
        return [self.result_data_dict["lines"], None, None]

# 权重映射到1~10
def convert_to_weight(values):
    # 找到最大值和最小值
    max_val = max(values)
    min_val = min(values)

    # 计算值的范围
    range_val = max_val - min_val

    weights = []
    for val in values:
        # 反转值（原值越大，反转后的值越小）
        reversed_val = max_val - val

        # 归一化到0-9范围，然后加1得到1-10的权重
        if range_val == 0:  # 处理所有值都相同的情况
            weight = 1
        else:
            weight = 1 + 999 * (reversed_val / range_val)

        # 四舍五入到整数
        weights.append(round(weight))

    return weights

def calculate_dtw_distance_matrix(all_series, dtw_func):
    """
    计算时间序列列表的DTW距离矩阵

    参数:
        all_series: 时间序列列表，每个元素是一个时间序列
        dtw_func: 计算两个时间序列DTW距离的函数

    返回:
        distance_matrix: 对称的距离矩阵，其中distance_matrix[i][j]是第i个和第j个序列的DTW距离
    """
    # 获取序列数量
    n = len(all_series)

    # 初始化距离矩阵
    distance_matrix = np.zeros((n, n))

    # 计算所有成对序列的DTW距离
    for i in range(n):
        # 对角线元素为0（自己与自己的距离）
        distance_matrix[i][i] = 0

        # 计算上三角部分并对称到下三角
        for j in range(i + 1, n):
            # 计算第i个和第j个序列的DTW距离
            distance = dtw_func(all_series[i], all_series[j])

            # 距离矩阵是对称的
            distance_matrix[i][j] = distance
            distance_matrix[j][i] = distance

            # 可选择性地打印进度
            # if j % 10 == 0:
            #     print(f"计算完成 {i}-{j} 对序列的距离")
    distance_df = pd.DataFrame(distance_matrix,
                               index=range(n),
                               columns=range(n))

    return distance_df

def klines_to_dataframe(merged_klines):
    """
    从合并后的K线数据中提取open, high, low, close并转换为DataFrame

    参数:
        merged_klines: 经merge_klines函数处理后的合并字典

    返回:
        包含open, high, low, close列的DataFrame
    """
    # 提取需要的列
    data = {
        'open': merged_klines.get('open', []),
        'high': merged_klines.get('high', []),
        'low': merged_klines.get('low', []),
        'close': merged_klines.get('close', [])
    }

    # 转换为DataFrame
    return pd.DataFrame(data)

def merge_klines(raw_target_klines):
    """
    将多个K线数据字典合并为一个字典，其中每个键对应的值是所有K线中该键值组成的列表

    参数:
        raw_target_klines: 包含多个K线字典的列表

    返回:
        合并后的字典，每个键对应的值是列表
    """
    # 如果输入列表为空，返回空字典
    if not raw_target_klines:
        return {}

    # 初始化结果字典，使用第一个K线的键创建空列表
    merged = {key: [] for key in raw_target_klines[0].keys()}

    # 遍历每个K线，将对应的值添加到结果字典的列表中
    for kline in raw_target_klines:
        for key, value in kline.items():
            merged[key].append(value)

    return merged

def get_klines_in_range(all_klines, start_timestamp, end_timestamp):
    """
    获取指定时间范围内的所有K线

    参数:
        all_klines: 所有K线数据列表，每个元素为包含'timestamp'键的字典
        start_timestamp: 起始时间字符串（如'2025-08-11 01:00:00'）
        end_timestamp: 结束时间字符串（如'2025-08-12 10:30:00'）

    返回:
        时间范围内的K线列表
    """
    # 筛选出时间在[start, end]范围内的K线
    return [
        kline for kline in all_klines
        if start_timestamp <= kline['timestamp'] <= end_timestamp
    ]

def find_last_negative_indices(lst):
    last_one_pos = -1  # 初始值表示未找到1
    last_neg_one_pos = -1  # 初始值表示未找到-1

    # 遍历列表，记录最后出现的1和-1的正索引
    for index, value in enumerate(lst):
        if value == 1:
            last_one_pos = index
        elif value == -1:
            last_neg_one_pos = index

    # 计算负索引（从末尾开始计数，最后一个元素为-1）
    list_length = len(lst)
    # 若未找到1，则返回None，否则计算负索引
    last_one_neg = -(list_length - last_one_pos) if last_one_pos != -1 else None
    # 若未找到-1，则返回None，否则计算负索引
    last_neg_one_neg = -(list_length - last_neg_one_pos) if last_neg_one_pos != -1 else None

    return last_one_neg, last_neg_one_neg

def add_dataset(dataset, zigzag_points_1for5, stutas=0):
    """
    用于测试的函数，将zigzag_points_1for5添加到dataset中。
    zigzag_points_1for5表示5个轴点
    stutas表示是否是M形态，-1表示W形态，1表示M形态， 0表示其他形态
    """
    fri = zigzag_points_1for5[0]
    sec = zigzag_points_1for5[1]
    thi = zigzag_points_1for5[2]
    fou = zigzag_points_1for5[3]
    # fif = zigzag_points_1for5[4]

    dataset.append(
        [sec['index'] - fri['index'],
         thi['index'] - sec['index'],
         thi['index'] - fri['index'],
         fou['index'] - thi['index'],
         fou['index'] - sec['index'],
         fou['index'] - fri['index'],
         # fif['index'] - fou['index'],
         round(sec['price'] - fri['price'], 3),
         round(thi['price'] - sec['price'], 3),
         round(thi['price'] - fri['price'], 3),
         round(fou['price'] - thi['price'], 3),
         round(fou['price'] - sec['price'], 3),
         round(fou['price'] - fri['price'], 3),
         # round(fif['price'] - fou['price'], 3),
         stutas,
         ]
    )
    return dataset

def probability(zigzag_points, datafrom='m', weight=None):
    '''
    datafrom表示要计算概率的轴枢点，为m或为w
    '''
    math_diff_list = []

    for i in zigzag_points:
        fir = i[0]
        sec = i[1]
        thi = i[2]['kline_data']
        fou = i[3]['kline_data']
        fif = i[4]['kline_data']
        if datafrom == 'm':
            p = (fif.hloc[1] - thi.hloc[1]) / (thi.hloc[1] - fou.hloc[0])
        elif datafrom == 'w':
            p = (fif.hloc[0] - thi.hloc[0]) / (thi.hloc[0] - fou.hloc[1])
        math_diff_list.append(p)
    # print('math_diff_list', datafrom, math_diff_list)
    try:
        com = calculate_probability_distribution(math_diff_list, bins=[0, 1.0, 2.0, 3.0], weights=weight)
        return com
    except:
        print('error')
        return None

def calculate_probability_distribution(data, bins=None, num_bins=6, weights=None):
    """
    计算连续型数据的概率分布（按区间划分），支持加权计算

    参数:
        data: 输入的数据集（列表或数组）
        bins: 自定义区间边界（如[0, 0.5, 1.0]），默认None则自动生成
        num_bins: 自动生成区间时的区间数量，默认6个
        weights: 每个数据点对应的权重（列表或数组），长度需与data一致
                 若为None，默认所有数据点权重为1（等权重）

    返回:
        dict: 包含两个键的字典
            - 'intervals': 区间列表（如["[0.0, 0.6)", ...]）
            - 'probabilities': 对应区间的概率列表（加权后）

    """
    # 数据验证
    if not data:
        raise ValueError("输入数据不能为空")
    data = np.asarray(data)
    if len(data) < 2:
        raise ValueError("数据量太少，无法计算分布")

    # 权重处理与验证
    if weights is None:
        # 默认为等权重（每个数据点权重为1）
        weights = np.ones_like(data, dtype=np.float64)
    else:
        weights = np.asarray(weights, dtype=np.float64)
        # 验证权重长度与数据一致
        if len(weights) != len(data):
            raise ValueError("权重长度必须与数据长度一致")
        # 验证权重非负性（权重不能为负数）
        if np.any(weights < 0):
            raise ValueError("权重不能为负数")
        # 验证权重总和不为0（避免除零错误）
        if np.sum(weights) == 0:
            raise ValueError("权重总和不能为0")

    # 处理区间边界
    if bins is None:
        # 自动生成区间（基于数据最小值和最大值）
        min_val = np.min(data)
        max_val = np.max(data)
        bins = np.linspace(min_val, max_val, num_bins + 1)  # 生成num_bins个区间

    # 计算每个数据点所在的区间索引
    bin_indices = np.digitize(data, bins, right=False) - 1  # 转为0-based索引
    # 确保索引在有效范围内（处理等于最大值的数据点）
    bin_indices = np.clip(bin_indices, 0, len(bins) - 2)

    # 计算每个区间的权重之和（替代原有的频数）
    weighted_freq = np.zeros(len(bins) - 1, dtype=np.float64)
    for i in range(len(bins) - 1):
        weighted_freq[i] = np.sum(weights[bin_indices == i])

    # 计算加权概率（区间权重和 / 总权重）
    total_weight = np.sum(weights)
    probabilities = weighted_freq / total_weight

    # 格式化区间为字符串（如"[0.0, 0.6)"）
    intervals = []
    for i in range(len(bins) - 1):
        interval_str = f"[{bins[i]:.4f}, {bins[i + 1]:.4f})"
        intervals.append(interval_str)

    return {
        "intervals": intervals,
        "probabilities": probabilities.round(4).tolist()  # 保留4位小数
    }
