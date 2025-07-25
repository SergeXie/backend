import backtrader as bt
import numpy as np
import math
import random
import pandas as pd
from backtrader.feeds import PandasData
from utils.module.zigzag_calculator import ZigZagCalculator
from utils.module.dll import train_wmclass_predictor, predict_wmclass


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

        # 实例化独立的算法类
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.p.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer()

        # 确保数据长度足够时再开始计算
        self.addminperiod(self.p.inp_depth)

    def next(self):
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

        # # 如果ZigZag有更新，就通知形态识别器进行分析
        # if new_zigzag_point_or_updated:
        #     zigzag_points = self.zigzag_calculator.get_zigzag_points()
        #     print("zigzag_points:", len(zigzag_points))
        #     dict_index2ts, dict_ts2index = self.zigzag_calculator.get_index_timestamp_maps()
        #     self.pattern_recognizer.analyze_zigzag_points(zigzag_points, dict_index2ts, dict_ts2index)
    def stop(self):
        zigzag_points = self.zigzag_calculator.get_zigzag_points()
        zigzag_list = []
        for zig in zigzag_points:
            zigzag_list.append(zig)
            self.pattern_recognizer.analyze_zigzag_points(zigzag_list)
        dataset = self.pattern_recognizer.get_dataset()
        df = pd.DataFrame(dataset, columns=['col1', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7', 'col8', 'wmclass'])
        
        
        # 训练模型
        model, scaler, metrics, class_map = train_wmclass_predictor(df)
        
        # # 使用模型进行预测
        # # 假设new_samples是包含新样本的DataFrame或numpy数组
        # predictions = predict_wmclass(model, scaler, new_samples, class_map)
        # print("预测结果:", predictions)
        
        print(df)

        return super().stop()


    def get_analysis(self):
        # 组织数据结构，从独立的算法类获取数据
        zigzag_points = self.zigzag_calculator.get_zigzag_points()

        self.result_data_dict["lines"] = [
            # {
            #     "type": "text",
            #     "TextColor": self.indicator_params.get("TextColor", "#000000"),
            #     "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
            #     "position": 'top',
            #     "data": pattern_titles
            # },
            # {
            #     "type": "picture",  # 假设'picture'是您自定义的一种绘图类型，用于M/W形态
            #     "data": formatted_m_w_patterns
            # },
            {
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FFFF"),
                "data": zigzag_points
            },
        ]
        
        return [self.result_data_dict["lines"], None , None]



import random

class WMPatternRecognizer:
    """
    负责识别M和W形态的独立算法类。
    """

    def __init__(self):
        self.detected_patterns = []  # 存储M/W形态结果
        self.zigzag_points = []
        self.dataset = []

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
            self._add_dataset(self.dataset, zigzag_points[-5:],stutas=1)
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
            self._add_dataset(self.dataset, zigzag_points[-5:],stutas=-1)
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
        fif = zigzag_points_1for5[4]
        
        dataset.append(
            [sec['index'] - fri['index'],
             thi['index'] - sec['index'],
             fou['index'] - thi['index'],
             fif['index'] - fou['index'],
             round(sec['price'] - fri['price'], 3),
             round(thi['price'] - sec['price'], 3),
             round(fou['price'] - thi['price'], 3),
             round(fif['price'] - fou['price'], 3),
             stutas,
             ]
        )
        
    def get_dataset(self):
        return self.dataset



        
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

def decision_tree_predict(data):
    """
    使用决策树模型预测wmclass
    
    参数:
    data: DataFrame，包含特征列(col1-col8)和目标列(wmclass)
    
    返回:
    tuple: 包含训练好的模型、预测结果和评估指标
    """
    # 分割特征和目标变量
    X = data[['col1', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7', 'col8']]
    y = data['wmclass']
    
    # 分割训练集和测试集（70%训练，30%测试）
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    # 创建并训练决策树模型
    clf = DecisionTreeClassifier(random_state=42)
    clf.fit(X_train, y_train)
    
    # 在测试集上进行预测
    y_pred = clf.predict(X_test)
    
    # 计算评估指标
    accuracy = accuracy_score(y_test, y_pred)
    conf_matrix = confusion_matrix(y_test, y_pred)
    class_report = classification_report(y_test, y_pred)
    
    # 输出评估结果
    print(f"模型准确率: {accuracy:.4f}")
    print("\n混淆矩阵:")
    print(conf_matrix)
    print("\n分类报告:")
    print(class_report)
    
    return clf, y_pred, {
        'accuracy': accuracy,
        'confusion_matrix': conf_matrix,
        'classification_report': class_report
    }

# 使用示例：
# 假设你的数据已经是一个pandas DataFrame，名为df
# model, predictions, metrics = decision_tree_predict(df)
