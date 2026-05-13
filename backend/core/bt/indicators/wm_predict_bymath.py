import math
from bisect import bisect_left
import backtrader as bt
import numpy as np
import pandas as pd
from core.bt.tools.zigzag_calculator_byclass import ZigZagCalculator
from core.bt.indicators.peak_trough import PeakTroughIndicator, PeakTroughType
from core.bt.entity.wm_peak_trough import PeakTroughPointCalculator
from core.ai.dtw import df_to_sequence, fast_dtw
from core.bt.tools.wm_pattern_recognizer import WMPatternRecognizer2
from core.bt.tools.wm_extractor import load_patterns_sync
import warnings
from datetime import datetime
from collections import Counter
# 过滤特定警告
warnings.filterwarnings('ignore')


class ResWMpredictByMathData(bt.Strategy):

    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data_dict = dict()
        self.Id_TS_dict = {}
        self.Ts_to_hloc = {}
        self.kLineId_to_all = dict()
        self.inp_depth = 12

        self.BarState = []
        self.BarStateText = []
        self.verticalBrokenline = []
        self.W_sum = 0
        self.M_sum = 0
        self.all_kline_data = []
        self.BarStateText1 = []
        Z_from = indicator_params.get("Zfrom", 1)
        self.Z_from = 'pc' if Z_from == 0 else 'zig'

        # 实例化独立的算法类
        self.peak_trough = PeakTroughIndicator(self.data)
        self.pk_point_calculator = PeakTroughPointCalculator()
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer2()
        self.history_patterns_by_type = {'M': [], 'W': []}
        self.history_start_times_by_type = {'M': [], 'W': []}
        self.history_feature_matrix_by_type = {
            'M': np.empty((0, 5), dtype=np.float64),
            'W': np.empty((0, 5), dtype=np.float64),
        }
        self.history_top_k = int(self.indicator_params.get('history_top_k', 500))
        self.history_keep_ratio = float(self.indicator_params.get('history_keep_ratio', 0.2))

        goods = self.indicator_params.get('Kline_goods')
        periods = self.indicator_params.get('Kline_period')
        # 预测场景只读取数据库中已经落库的 WM 形态。
        # WM 的全量 / 增量计算由定时任务统一执行，避免预测请求阻塞在计算过程上。
        self.all_wm_pattern = load_patterns_sync(
            goods=goods,
            periods=periods,
        )
        tmp = [i.value for i in self.all_wm_pattern]
        self.counts = Counter(tmp)
        self._prepare_history_patterns()


        # 确保数据长度足够时再开始计算
        self.addminperiod(self.inp_depth)

    def next(self):
        self.Id_TS_dict[int(self.data.klineId[0])] = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')
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
        self.kLineId_to_all[int(self.data.klineId[0])] = current_kline_data
        self.all_kline_data.append(current_kline_data)
        self.Ts_to_hloc[self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')] = [self.data.high[0],
                                                 self.data.low[0],
                                                 self.data.open[0],
                                                 self.data.close[0]]

        # 确保数据长度足够
        if len(self) < self.inp_depth:
            return
        # 调用ZigZag算法类的处理方法
        if self.Z_from == 'zig':
            new_zigzag_point_or_updated = self.zigzag_calculator.process_kline(current_kline_data)
            if new_zigzag_point_or_updated:
                zigzag_points = self.zigzag_calculator.get_zigzag_points(as_dict=False)
                self.pattern_recognizer.analyze_zigzag_points(zigzag_points)
        elif self.Z_from == 'pc':  # 峰值连线

            val = self.peak_trough.lines.pt_r[0]
            if val > 0:
                pt_type = PeakTroughType.Peak
            elif val < 0:
                pt_type = PeakTroughType.Trough
            else:
                pt_type = PeakTroughType.Normal

            center_line_id = self.peak_trough.lines.pt_center[0]
            center_line_id = self.data.klineId[0] if pt_type == PeakTroughType.Normal else center_line_id
            self.pk_point_calculator.process_point(self.kLineId_to_all.get(int(center_line_id)), pt_type)
            # print('峰值连线',val)
            # 如果值不是 NaN，说明当前K线确认了一个顶或底
            if not math.isnan(val):
                PeakTrough_points = self.pk_point_calculator.get_PeakTrough_points(as_dict=False)
                self.pattern_recognizer.analyze_zigzag_points(PeakTrough_points)

    def stop(self):
        digit = int(self.datas[0].digits[0])
        if not self.all_wm_pattern:
            return

        show_pattern = self.indicator_params.get("show_mabye_pattern")

        if show_pattern == 1:  # 可能形态
            # -----------获取最后一个可能的m，用于计算概率----------------
            for maybe_m in self.pattern_recognizer.get_maybe_m_patterns():
                p = self._calculate_pattern_probability(maybe_m, pattern_type='M', datafrom='m')
                if not p:
                    continue

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
                self.BarStateText1.append({
                    "kLineId": maybe_m.kLineId,
                    "price": maybe_m.price,
                    "timestamp": self.Id_TS_dict.get(maybe_m.kLineId),
                    "value": maybe_m.value
                })

            # -----------获取最后一个可能的w，用于计算概率----------------
            for maybe_w in self.pattern_recognizer.get_maybe_w_patterns():
                p = self._calculate_pattern_probability(maybe_w, pattern_type='W', datafrom='w')
                if not p:
                    continue

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
                self.BarStateText1.append({
                    "kLineId": maybe_w.kLineId,
                    "price": maybe_w.price,
                    "timestamp": self.Id_TS_dict.get(maybe_w.kLineId),
                    "value": maybe_w.value
                })



        elif show_pattern == 0:  # 确认形态
            standard_m_list = self.pattern_recognizer.get_standard_m_patterns()
            for standard_m in standard_m_list:
                p = self._calculate_pattern_probability(standard_m, pattern_type='M', datafrom='m')
                if not p:
                    continue
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
                self.BarStateText1.append({
                    "kLineId": standard_m.kLineId,
                    "price": standard_m.price,
                    "timestamp": self.Id_TS_dict.get(standard_m.kLineId),
                    "value": standard_m.value
                })

            standard_w_list = self.pattern_recognizer.get_standard_w_patterns()
            for standard_w in standard_w_list:
                p = self._calculate_pattern_probability(standard_w, pattern_type='W', datafrom='w')
                if not p:
                    continue
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
                self.BarStateText1.append({
                    "kLineId": standard_w.kLineId,
                    "price": standard_w.price,
                    "timestamp": self.Id_TS_dict.get(standard_w.kLineId),
                    "value": standard_w.value
                })

    def _prepare_history_patterns(self):
        time_format = "%Y-%m-%d %H:%M:%S"
        for pattern in self.all_wm_pattern:
            target_klines = getattr(pattern, 'target_klines', None)
            start_timestamp = getattr(pattern, 'start_timestamp', None)
            value = getattr(pattern, 'value', '')
            if not target_klines or not start_timestamp:
                continue

            pattern_type = 'M' if 'M' in value else 'W' if 'W' in value else None
            if not pattern_type:
                continue

            history_df = klines_to_dataframe(merge_klines(target_klines))
            history_sequence = df_to_sequence(history_df)
            if not history_sequence:
                continue

            start_time = datetime.strptime(start_timestamp, time_format)

            self.history_patterns_by_type[pattern_type].append({
                'pattern': pattern,
                'start_time': start_time,
                'sequence': history_sequence,
                'feature_vector': build_feature_vector(history_sequence),
            })

        for pattern_type, pattern_items in self.history_patterns_by_type.items():
            pattern_items.sort(key=lambda item: item['start_time'])
            self.history_start_times_by_type[pattern_type] = [item['start_time'] for item in pattern_items]
            if pattern_items:
                self.history_feature_matrix_by_type[pattern_type] = np.vstack(
                    [item['feature_vector'] for item in pattern_items]
                )

    def _get_history_candidate_prefix(self, base_time, pattern_type):
        history_times = self.history_start_times_by_type.get(pattern_type, [])
        if not history_times:
            return 0
        return bisect_left(history_times, base_time)

    def _resolve_history_keep_count(self, candidate_count):
        ratio_count = int(candidate_count * self.history_keep_ratio)
        keep_count = max(2, self.history_top_k, ratio_count)
        return min(candidate_count, keep_count)

    def _select_top_history_candidates(self, candidate_items, candidate_feature_matrix, current_feature_vector):
        candidate_count = len(candidate_items)
        if candidate_count <= 2:
            return candidate_items

        keep_count = self._resolve_history_keep_count(candidate_count)
        if candidate_count <= keep_count:
            return candidate_items

        length_gap_limit = max(5.0, current_feature_vector[0] * 0.6)
        length_mask = np.abs(candidate_feature_matrix[:, 0] - current_feature_vector[0]) <= length_gap_limit

        if np.count_nonzero(length_mask) >= 2:
            filtered_indices = np.flatnonzero(length_mask)
            filtered_matrix = candidate_feature_matrix[length_mask]
        else:
            filtered_indices = np.arange(candidate_count)
            filtered_matrix = candidate_feature_matrix

        if len(filtered_indices) <= keep_count:
            return [candidate_items[index] for index in filtered_indices]

        base_vector = np.array([1.0, 1e-9, 1e-9, 1e-9, 1e-9], dtype=np.float64)
        denominator = np.maximum(
            np.maximum(np.abs(filtered_matrix), np.abs(current_feature_vector)),
            base_vector,
        )
        weight_vector = np.array([0.35, 0.25, 0.20, 0.10, 0.10], dtype=np.float64)
        score_matrix = np.abs(filtered_matrix - current_feature_vector) / denominator
        scores = score_matrix @ weight_vector

        top_local_indices = np.argpartition(scores, keep_count - 1)[:keep_count]
        top_local_indices = top_local_indices[np.argsort(scores[top_local_indices])]
        selected_indices = filtered_indices[top_local_indices]
        return [candidate_items[index] for index in selected_indices]

    def _calculate_pattern_probability(self, current_pattern, pattern_type, datafrom):
        base_time = datetime.strptime(current_pattern.start, "%Y-%m-%d %H:%M:%S")
        history_prefix = self._get_history_candidate_prefix(base_time, pattern_type)
        if history_prefix < 2:
            return None

        history_candidates = self.history_patterns_by_type.get(pattern_type, [])[:history_prefix]
        history_feature_matrix = self.history_feature_matrix_by_type.get(pattern_type)
        history_feature_matrix = history_feature_matrix[:history_prefix]

        current_klines = get_klines_in_range(self.all_kline_data, current_pattern.start, current_pattern.end)
        if len(current_klines) < 2:
            return None

        current_kline_df = klines_to_dataframe(merge_klines(current_klines))
        if current_kline_df.empty:
            return None

        current_sequence = df_to_sequence(current_kline_df)
        current_feature_vector = build_feature_vector(current_sequence)
        history_candidates = self._select_top_history_candidates(
            history_candidates,
            history_feature_matrix,
            current_feature_vector,
        )
        if len(history_candidates) < 2:
            return None

        distances = [int(fast_dtw(current_sequence, item['sequence'])) for item in history_candidates]
        weights = convert_to_weight(distances)
        zigzag_points = [item['pattern'].points for item in history_candidates]

        if len(zigzag_points) < 2:
            return None

        return probability(zigzag_points, datafrom=datafrom, weight=weights)


    def get_analysis(self):
        print(self.BarStateText1)
        zigzag_points = self.pattern_recognizer.get_zigzag_points()
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

        self.counts
        self.result_data_dict["lines"].append({
            "type": "bottomText",
            "color": self.indicator_params.get("DnColor", "#FF0000"),
            "data": f"W1形态个数: {self.counts['W1形态']}, M1形态个数: {self.counts['M1形态']},"
                    f"W2形态个数: {self.counts['W2形态']}, M2形态个数: {self.counts['M2形态']},"
                    f"W3形态个数: {self.counts['W3形态']}, M3形态个数: {self.counts['M3形态']},"
        })
        # 画竖线
        for i in self.verticalBrokenline:
            self.result_data_dict["lines"].append({
                "type": "verticalBrokenline",
                "color": self.indicator_params.get("FFFF00", "#FFFF00"),
                "data": [i]
            })
        # 写形态
        for i in self.BarStateText1:
            # print(i)
            self.result_data_dict["lines"].append({
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                "position": 'top',
                "data": [i],
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


def build_feature_vector(sequence):
    if not sequence:
        return np.zeros(5, dtype=np.float64)

    seq_array = np.asarray(sequence, dtype=np.float64)
    open_prices = seq_array[:, 0]
    high_prices = seq_array[:, 1]
    low_prices = seq_array[:, 2]
    close_prices = seq_array[:, 3]

    return np.array([
        float(len(sequence)),
        float(np.max(high_prices) - np.min(low_prices)),
        float(close_prices[-1] - open_prices[0]),
        float(np.mean(np.abs(close_prices - open_prices))),
        float(np.mean(high_prices - low_prices)),
    ], dtype=np.float64)

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
        # print('@@@', fif)

        hloc_fif = get_hloc(fif)
        hloc_thi = get_hloc(thi)
        hloc_fou = get_hloc(fou)

        if datafrom == 'm':
            # m: 使用 low（hloc[1]）和 high（hloc[0]）
            # 根据你原始注释：hloc = [high, low, open, close]
            p = (hloc_fif[1] - hloc_thi[1]) / (hloc_thi[1] - hloc_fou[0])
        elif datafrom == 'w':
            # w: 使用 high（hloc[0]）和 low（hloc[1]）
            p = (hloc_fif[0] - hloc_thi[0]) / (hloc_thi[0] - hloc_fou[1])
        else:
            raise ValueError("datafrom must be 'm' or 'w'")

        math_diff_list.append(p)

    try:
        com = calculate_probability_distribution(math_diff_list, bins=[0, 1.0, 2.0, 3.0], weights=weight)
        return com
    except Exception as e:
        print('error in probability:', e)
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


def get_hloc(obj):
    """通用方式获取 hloc，兼容 dict 和 对象"""
    if isinstance(obj, dict):
        return obj['hloc']
    else:
        return obj.hloc
