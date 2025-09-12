import pickle
import backtrader as bt
import numpy as np
import math
import random
import pandas as pd
import tensorflow as tf
from backtrader.feeds import PandasData
from utils.module.zigzag_calculator import ZigZagCalculator
from utils.module.wm_pattern_recognizer import WMPatternRecognizer

import warnings
from sklearn.exceptions import UndefinedMetricWarning

# 过滤特定警告
warnings.filterwarnings('ignore', category=UndefinedMetricWarning)


class ResWMpredictByModelData(bt.Strategy):
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
        # print(zigzag_points)

        # dataset = []
        # for i in range(len(zigzag_points) - 3):
        #     # 从索引i开始取4个元素组成子列表
        #     dataset = add_dataset(dataset, zigzag_points[i:i + 4])

        zigzag_list = []
        for zig in zigzag_points:
            zigzag_list.append(zig)
            self.pattern_recognizer.analyze_zigzag_points(zigzag_list)


        with open('./dataset/all_wm_pattern_kline.pkl', 'rb') as file:
            all_wm_pattern = pickle.load(file)

        print('这里')
        print(len(all_wm_pattern))
        print(all_wm_pattern[0])

        from utils.module.test import preprocess_wm_data

        from t2 import extract_data_from_all_wm_pattern, build_lstm_model
        X, y = extract_data_from_all_wm_pattern(all_wm_pattern)
        print(X.shape, y.shape)

        # 划分训练集和测试集（8:2）
        split_idx = int(0.8 * len(X))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # --------------------------
        # 步骤2：构建并训练模型
        # --------------------------
        max_seq_len = X.shape[1]  # 所有样本的最大K线长度
        model = build_lstm_model(max_seq_len=max_seq_len, feat_dim=9)
        print("\n模型结构：")
        model.summary()

        # 训练模型
        print("\n开始训练模型...")
        history = model.fit(
            X_train, y_train,
            batch_size=16,
            epochs=30,
            validation_data=(X_test, y_test),
            shuffle=True
        )

        # 评估模型
        test_loss, test_acc = model.evaluate(X_test, y_test)
        print(f"\n测试集性能：损失={test_loss:.4f}, 准确率={test_acc:.4f}")

        # --------------------------
        # 步骤3：推理预测（以测试集第一个样本为例）
        # --------------------------
        print("\n推理示例：")
        # 取测试集第一个样本
        sample_idx = 50
        X_sample = X_test[sample_idx:sample_idx + 1]  # (1, max_seq_len, 9)
        y_true = y_test[sample_idx]  # 真实标签

        # 预测概率
        y_pred_prob = model.predict(X_sample, verbose=0)[0]  # (3,)

        # 打印结果
        print(f"样本{sample_idx} - 真实标签：1倍价差={y_true[0]}, 2倍价差={y_true[1]}, 3倍价差={y_true[2]}")
        print(
            f"样本{sample_idx} - 预测概率：1倍价差={y_pred_prob[0]:.4f}, 2倍价差={y_pred_prob[1]:.4f}, 3倍价差={y_pred_prob[2]:.4f}")


        # # 2. 调用预处理函数
        # X_train_scaled, X_val_scaled, X_test_scaled, y_train, y_val, y_test, scaler = preprocess_wm_data(
        #     all_wm_pattern=all_wm_pattern,
        #     test_size=0.1,
        #     val_size=0.2,
        #     random_state=42,
        #     use_kline_context=False  # 若有完整target_klines可设为True
        # )
        #
        # # 3. 查看输出结果
        # print("\n预处理后数据形状：")
        # print(f"X_train_scaled: {X_train_scaled.shape} (样本数, 特征数)")
        # print(f"y_train: {y_train.shape} (样本数,)")
        # print(f"特征数：{X_train_scaled.shape[1]}")
        # # print(y_train)




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



