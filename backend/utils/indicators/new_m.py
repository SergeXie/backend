import pickle

import backtrader as bt
import numpy as np
import math
import random
import pandas as pd
import tensorflow as tf
from backtrader.feeds import PandasData
from utils.module.zigzag_calculator import ZigZagCalculator
from utils.module.dll import train_two_classifiers, predict_binary

import warnings
from sklearn.exceptions import UndefinedMetricWarning

# 过滤特定警告
warnings.filterwarnings('ignore', category=UndefinedMetricWarning)


class ResponseWMpredictData(bt.Strategy):
    # 定义参数
    params = (
        ('inp_depth', 12),
    )

    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data_dict = dict()
        self.Id_TS_dict = {}

        self.BarState = []
        self.BarStateText = []
        self.W_sum = 0
        self.M_sum = 0


        # 实例化独立的算法类
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.p.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer()

        # 确保数据长度足够时再开始计算
        self.addminperiod(self.p.inp_depth)

    def next(self):
        self.Id_TS_dict[int(self.data.klineId[0])] = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')

        # 确保数据长度足够
        if len(self) < self.p.inp_depth:
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

        # 调用ZigZag算法类的处理方法
        # process_kline会返回是否产生了新的zigzag点，如果产生，就通知形态识别器
        new_zigzag_point_or_updated = self.zigzag_calculator.process_kline(current_kline_data)


    def stop(self):
        digit = int(self.datas[0].digits[0])
        zigzag_points = self.zigzag_calculator.get_zigzag_points()
        print('这里')
        # print(zigzag_points)

        dataset = []
        for i in range(len(zigzag_points) - 3):
            # 从索引i开始取4个元素组成子列表
            dataset = add_dataset(dataset, zigzag_points[i:i + 4])

        zigzag_list = []
        for zig in zigzag_points:
            zigzag_list.append(zig)
            self.pattern_recognizer.analyze_zigzag_points(zigzag_list)

        m_zigzag_points = self.pattern_recognizer.get_m_zigzag_points()
        # print(m_zigzag_points)

        df = pd.DataFrame(dataset, columns=['col1', 'col2', 'col3', 'col4', 'col5', 'col6',
                                            'col7', 'col8', 'col9', 'col10', 'col11', 'col12',
                                            'wmclass'])
        # print(df)
        with open('./dataset/wm_predict_classifiers.pkl', 'rb') as f:
            classifiers = pickle.load(f)

        model_neg = tf.keras.models.load_model('./dataset/model_neg.h5')
        model_pos = tf.keras.models.load_model('./dataset/model_pos.h5')
        predictions_neg, probs_neg = predict_binary(
            model_neg,
            classifiers['scaler_neg'],
            df,
            -1
        )

        # 使用第二个模型预测(1 vs 0)
        predictions_pos, probs_pos = predict_binary(
            model_pos,
            classifiers['scaler_pos'],
            df,
            1
        )
        # print("预测结果:", list(predictions))
        # print("真正结果:", list(df['wmclass']))
        # print(len(zigzag_list))
        # print(len(predictions))
        # print('@@@@@@@@@@@@@@@@')
        # print(dataset)
        # print(zigzag_list)
        # print('@@@@@@@@@@@@@@@@')
        a = [0,0,0,0,0,1,0,-1]
        # print("\n预测结果(-1 vs 0):", predictions_neg)
        # print("预测概率(-1的概率):", [f"{p:.4f}" for p in probs_neg])
        #
        # print("\n预测结果(1 vs 0):", predictions_pos)
        # print("预测概率(1的概率):", [f"{p:.4f}" for p in probs_pos])


        _, neg_one_idx = find_last_negative_indices(predictions_neg)
        one_idx, _ = find_last_negative_indices(predictions_pos)
        print(one_idx, neg_one_idx)  # 获取 预测队列中1和-1的位置

        m_point = [zigzag_list[one_idx-4], zigzag_list[one_idx-2], zigzag_list[one_idx-1], zigzag_list[one_idx]]
        w_point = [zigzag_list[neg_one_idx-4], zigzag_list[neg_one_idx-2], zigzag_list[neg_one_idx-1], zigzag_list[neg_one_idx]]

        #------------------计算概率-----------------------#

        # 计算价差 M顶
        # m_point = m_zigzag_points[-1]
        price_diff = m_point[2]['hloc'][1] - m_point[3]['hloc'][0]  # 高点到低点的价差
        p = probability(m_zigzag_points, datafrom='m')
        # print("m概率:", p)
        if p is None:
            return
        klineId = int(m_point[3]['kLineId'])
        for index, i in enumerate(p['probabilities']):
            base_price = m_point[2]['hloc'][1]
            price = base_price + price_diff * index
            price = np.round(price, digit)
            # print(i)
            i = np.round(i*100, 2)
            # print('来了', price)
            # print(index)
            self.BarStateText.append({
                "kLineId": klineId,
                "price": price,
                "timestamp": self.Id_TS_dict.get(klineId, ),
                "value": f"{np.round(price, 2)}: " + str(i) + '%'
            })
            self.BarState.append([
                {
                    "kLineId": int(klineId),
                    "price": price,
                },
                {
                    "kLineId": int(klineId),
                    "price": price,
                }
            ])

        # 计算价差 W底
        w_zigzag_points = self.pattern_recognizer.get_w_zigzag_points()

        p = probability(w_zigzag_points, datafrom='w')
        # print("w概率:", p)
        # w_point = w_zigzag_points[-1]
        price_diff = w_point[2]['hloc'][0] - w_point[3]['hloc'][1]  # 高点到低点的价差
        klineId = int(w_point[3]['kLineId'])
        for index, i in enumerate(p['probabilities']):
            base_price = w_point[2]['hloc'][0]
            price = base_price + price_diff * index
            price = np.round(price, digit)
            # print(i)
            i = np.round(i*100, 2)
            # print('来了', price)
            # print(index)
            self.BarStateText.append({
                "kLineId": klineId,
                "price": price,
                "timestamp": self.Id_TS_dict.get(klineId, ),
                "value": f"{np.round(price, 2)}: " + str(i) + '%'
            })
            self.BarState.append([
                {
                    "kLineId": int(klineId),
                    "price": price,
                },
                {
                    "kLineId": int(klineId),
                    "price": price,
                }
            ])

        self.M_sum = len(m_zigzag_points)
        self.W_sum = len(w_zigzag_points)
        return super().stop()

    def get_analysis(self):

        # 组织数据结构，从独立的算法类获取数据
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
        return [self.result_data_dict["lines"], None, None]


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

def probability(zigzag_points, datafrom='m'):
    '''
    datafrom表示要计算概率的轴枢点，为m或为w
    '''
    math_diff_list = []

    for i in zigzag_points:
        fir = i[0]
        sec = i[1]
        thi = i[2]
        fou = i[3]
        fif = i[4]
        if datafrom == 'm':
            p = (fif['hloc'][1] - thi['hloc'][1]) / (thi['hloc'][1] - fou['hloc'][0])
        elif datafrom == 'w':
            p = (fif['hloc'][0] - thi['hloc'][0]) / (thi['hloc'][0] - fou['hloc'][1])
        math_diff_list.append(p)
    # print('math_diff_list', datafrom, math_diff_list)
    try:
        com = calculate_probability_distribution(math_diff_list, bins=[0, 1.0, 2.0, 3.0])
        return com
    except:
        print('error')
        return None


def calculate_probability_distribution(data, bins=None, num_bins=6):
    """
    计算连续型数据的概率分布（按区间划分）

    参数:
        data: 输入的数据集（列表或数组）
        bins: 自定义区间边界（如[0, 0.5, 1.0]），默认None则自动生成
        num_bins: 自动生成区间时的区间数量，默认6个

    返回:
        dict: 包含两个键的字典
            - 'intervals': 区间列表（如["[0.0, 0.6)", ...]）
            - 'probabilities': 对应区间的概率列表

    """
    # 数据验证
    if not data:
        raise ValueError("输入数据不能为空")
    data = np.asarray(data)
    if len(data) < 2:
        raise ValueError("数据量太少，无法计算分布")

    # 处理区间边界
    if bins is None:
        # 自动生成区间（基于数据最小值和最大值）
        min_val = np.min(data)
        max_val = np.max(data)
        bins = np.linspace(min_val, max_val, num_bins + 1)  # 生成num_bins个区间

    # 计算频数和概率
    freq, edges = np.histogram(data, bins=bins)
    total = len(data)
    probabilities = freq / total  # 频率即概率估计

    # 格式化区间为字符串（如"[0.0, 0.6)"）
    intervals = []
    for i in range(len(edges) - 1):
        interval_str = f"[{edges[i]:.4f}, {edges[i + 1]:.4f})"
        intervals.append(interval_str)

    return {
        "intervals": intervals,
        "probabilities": probabilities.round(4).tolist()  # 保留4位小数
    }


class WMPatternRecognizer:
    """
    负责识别M和W形态的独立算法类。
    """

    def __init__(self):
        self.detected_patterns = []  # 存储M/W形态结果
        self.zigzag_points = []
        self.dataset = []
        self.m_zigzag_points = []
        self.w_zigzag_points = []

    def analyze_zigzag_points(self, zigzag_points):
        """
        分析ZigZag点列表，识别M和W形态。
        Args:
            zigzag_points (list): 从ZigZagCalculator获取的ZigZag转折点列表。
            dict_index2ts (dict): 内部K线索引到时间戳的映射。
            dict_ts2index (dict): 时间戳到内部K线索引的映射。
        """
        # 只有当zigzag点数量增加且至少有5个点时才进行判断
        if len(zigzag_points) >= 5:
            con1 = self._judgment_m_pattern(zigzag_points)
            con2 = self._judgment_w_pattern(zigzag_points)
            self.zigzag_points = zigzag_points
            if con1:
                self.m_zigzag_points.append(self.zigzag_points[-5:])
            if con2:
                self.w_zigzag_points.append(self.zigzag_points[-5:])
            if not con1 and not con2:
                self._add_dataset(self.dataset, zigzag_points[-5:], stutas=0)

    def _judgment_m_pattern(self, zigzag_points):
        """判断M形态 (双顶)"""
        # M形态需要至少5个点: L-D-H-D-L (或 H-D-H-D-H)
        # 这里的zigzag_points[-5:]是最近的5个点
        # 原始代码的M形态定义：l_d_val -> l_val -> head_val -> r_val -> r_d_val
        # 对应zigzag_points: [-5] -> [-4] -> [-3] -> [-2] -> [-1]

        if len(zigzag_points) < 5:
            return

        l_val = zigzag_points[-4]['price']  # 左肩高点
        r_val = zigzag_points[-2]['price']  # 右肩高点
        l_d_val = zigzag_points[-5]['price']  # 左脚（形态起始低点）
        r_d_val = zigzag_points[-1]['price']  # 右脚（形态结束低点）
        head_val = zigzag_points[-3]['price']  # 颈线（谷底）

        # 距离20根 K 线
        con1 = (zigzag_points[-3]['index'] - zigzag_points[-5]['index']) > 20
        # 左肩高点高于右肩高点
        con3 = l_val > r_val
        # 颈线（谷底）高于双脚最低点，且低于双肩最高点
        con4 = head_val > max(l_d_val, r_d_val) and head_val < min(l_val, r_val)

        # 不重复判断，避免连续识别相同的形态
        con5 = True
        if self.detected_patterns and zigzag_points[-3]['timestamp'] == self.detected_patterns[-1]['timestamp']:
            con5 = False

        if con1 and con3 and con4 and con5:
            self._add_dataset(self.dataset, zigzag_points[-5:], stutas=1)
            self.detected_patterns.append({
                "kLineId": zigzag_points[-3]['kLineId'],
                "timestamp": zigzag_points[-3]['timestamp'],
                "price": zigzag_points[-3]['price'],
                "value": "M形态",
                "start": zigzag_points[-5]['timestamp'],
                "end": zigzag_points[-1]['timestamp'],
                "high": max(l_val, r_val),  # 形态的最高点是左右肩中较高的那个
                "low": head_val,  # 形态的最低点是颈线
            })
            return True
        return False

    def _judgment_w_pattern(self, zigzag_points):
        """判断W形态 (双底)"""
        # W形态需要至少5个点: H-D-L-D-H (或 L-D-L-D-L)
        # 原始代码的W形态定义：l_d_val -> l_val -> head_val -> r_val -> r_d_val
        # 对应zigzag_points: [-5] -> [-4] -> [-3] -> [-2] -> [-1]

        if len(zigzag_points) < 5:
            return

        l_val = zigzag_points[-4]['price']  # 左肩低点
        r_val = zigzag_points[-2]['price']  # 右肩低点
        l_d_val = zigzag_points[-5]['price']  # 左高（形态起始高点）
        r_d_val = zigzag_points[-1]['price']  # 右高（形态结束高点）
        head_val = zigzag_points[-3]['price']  # 颈线（山顶）

        # 距离20根 K 线
        con1 = (zigzag_points[-3]['index'] - zigzag_points[-5]['index']) > 20
        # 左肩低点低于右肩低点
        con3 = l_val < r_val
        # 颈线（山顶）低于双高点，且高于双低点
        con4 = head_val < min(l_d_val, r_d_val) and head_val > max(l_val, r_val)

        # 不重复判断
        con5 = True
        if self.detected_patterns and zigzag_points[-3]['timestamp'] == self.detected_patterns[-1]['timestamp']:
            con5 = False

        if con1 and con3 and con4 and con5:
            self._add_dataset(self.dataset, zigzag_points[-5:], stutas=-1)
            self.detected_patterns.append({
                "kLineId": zigzag_points[-3]['kLineId'],
                "timestamp": zigzag_points[-3]['timestamp'],
                "price": zigzag_points[-3]['price'],
                "value": "W形态",
                "start": zigzag_points[-5]['timestamp'],
                "end": zigzag_points[-1]['timestamp'],
                "high": head_val,  # 形态的最高点是颈线
                "low": min(l_val, r_val),  # 形态的最低点是左右肩中较低的那个
            })
            return True
        return False

    def get_pattern_titles(self):
        """返回检测到的M/W形态标题的原始列表。"""
        return self.detected_patterns

    def get_zigzag_points(self):
        return self.zigzag_points

    def _add_dataset(self, dataset, zigzag_points_1for5, stutas=0):
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
             fou['index'] - thi['index'],
             fou['index'] - sec['index'],
             # fif['index'] - fou['index'],
             round(sec['price'] - fri['price'], 3),
             round(thi['price'] - sec['price'], 3),
             round(fou['price'] - thi['price'], 3),
             round(fou['price'] - sec['price'], 3),
             # round(fif['price'] - fou['price'], 3),
             stutas,
             ]
        )

    def get_dataset(self):
        return self.dataset

    def get_m_zigzag_points(self):
        return self.m_zigzag_points

    def get_w_zigzag_points(self):
        return self.w_zigzag_points




