import pickle
import backtrader as bt
import numpy as np
from utils.module.zigzag_calculator import ZigZagCalculator
from utils.module.wm_pattern_recognizer import WMPatternRecognizer
from utils.indicators.wm_predict_bymath import get_klines_in_range

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
        self.all_kline_data = []


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
        self.all_kline_data.append(current_kline_data)

        # 调用ZigZag算法类的处理方法
        # process_kline会返回是否产生了新的zigzag点，如果产生，就通知形态识别器
        new_zigzag_point_or_updated = self.zigzag_calculator.process_kline(current_kline_data)


    def stop(self):
        digit = int(self.datas[0].digits[0])
        zigzag_points = self.zigzag_calculator.get_zigzag_points()

        zigzag_list = []
        for zig in zigzag_points:
            zigzag_list.append(zig)
            self.pattern_recognizer.analyze_zigzag_points(zigzag_list)
        # 获取非形态数据
        # wm_pattern = self.pattern_recognizer.get_all_none_patterns()
        # for pattern in wm_pattern:
        #     # 获取该模式时间范围内的所有K线
        #     target_klines = get_klines_in_range(
        #         all_klines=self.all_kline_data,  # 替换为实际的全量K线数据
        #         start_timestamp=pattern['start_timestamp'],
        #         end_timestamp=pattern['end_timestamp']
        #     )
        #     pattern['target_klines'] = target_klines
        #     pattern['period'] = "None"
        #
        # print('空的',len(wm_pattern))
        #
        # with open('./dataset/all_no_pattern_kline_M30.pkl', 'wb') as file:
        #     pickle.dump(wm_pattern, file)
        # pass
        # # 加载数据
        # with open('./dataset/all_no_pattern_kline_H4.pkl', 'rb') as file:
        #     h4 = pickle.load(file)
        # with open('./dataset/all_no_pattern_kline_H1.pkl', 'rb') as file:
        #     h1 = pickle.load(file)
        # with open('./dataset/all_no_pattern_kline_M5.pkl', 'rb') as file:
        #     m5 = pickle.load(file)
        # with open('./dataset/all_no_pattern_kline_M15.pkl', 'rb') as file:
        #     m15 = pickle.load(file)
        # with open('./dataset/all_no_pattern_kline_M30.pkl', 'rb') as file:
        #     m30 = pickle.load(file)
        # print(type(h4), len(h1), len(m5), len(m15), len(m30))
        #
        # all = m5+m15+m30+h1+h4
        # with open('./dataset/all_no_pattern_kline.pkl', 'wb') as file:
        #     pickle.dump(all, file)
        #
        # pass

        with open('./dataset/all_wm_pattern_kline.pkl', 'rb') as file:
            all_wm_pattern = pickle.load(file)
        with open('./dataset/all_no_pattern_kline.pkl', 'rb') as file:
            all_none_pattern = pickle.load(file)

        print('这里')
        print(len(all_wm_pattern))
        print(len(all_none_pattern))
        print(all_wm_pattern[0])
        print(all_none_pattern[0])

        #  这里先预测是否是形态
        from utils.module.t2 import extract_data_to_diffclass, build_lstm_model,extract_xdata
        X, y = extract_data_to_diffclass(all_wm_pattern+all_none_pattern)
        print(X.shape, y.shape)

        # 划分训练集和测试集（8:2）
        split_idx = int(0.8 * len(X))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # --------------------------
        # 步骤2：构建并训练模型
        # --------------------------
        max_seq_len = X.shape[1]  # 所有样本的最大K线长度
        max_seq_len = 200
        model = build_lstm_model(max_seq_len=max_seq_len, feat_dim=7)
        print("\n模型结构：")
        model.summary()

        # 训练模型
        print("\n开始训练模型...")
        history = model.fit(
            X_train, y_train,
            batch_size=16,
            epochs=1,
            validation_data=(X_test, y_test),
            shuffle=True
        )

        # 评估模型
        test_loss, test_acc = model.evaluate(X_test, y_test)
        print(f"\n测试集性能：损失={test_loss:.4f}, 准确率={test_acc:.4f}")

        # # --------------------------
        # # 步骤3：推理预测（以测试集第一个样本为例）
        # # --------------------------
        # print("\n推理示例：")
        # # 取测试集第一个样本
        # sample_idx = 52
        # X_sample = X_test[sample_idx:sample_idx + 1]  # (1, max_seq_len, 9)
        # print(X_sample.shape)
        # y_true = y_test[sample_idx]  # 真实标签
        #
        # # 预测概率
        # y_pred_prob = model.predict(X_sample, verbose=0)[0]  # (3,)
        #
        # # 打印结果
        # print(f"样本{sample_idx} - 真实标签：1倍价差={y_true[0]}, 2倍价差={y_true[1]}, 3倍价差={y_true[2]}")
        # print(
        #     f"样本{sample_idx} - 预测概率：1倍价差={y_pred_prob[0]:.4f}, 2倍价差={y_pred_prob[1]:.4f}, 3倍价差={y_pred_prob[2]:.4f}")

        may_m = self.pattern_recognizer.get_maybe_m_patterns()[-1]
        may_w = self.pattern_recognizer.get_maybe_w_patterns()[-1]
        # print(may_m)
        # print(may_w)

        for pattern in [may_m,may_w]:
            # 获取该模式时间范围内的所有K线
            target_klines = get_klines_in_range(
                all_klines=self.all_kline_data,  # 替换为实际的全量K线数据
                start_timestamp=pattern['start_timestamp'],
                end_timestamp=pattern['end_timestamp']
            )
            pattern['target_klines'] = target_klines
            pattern['period'] = "none"


        test_x = extract_xdata([may_m, may_w])
        print('测试数据维度',test_x.shape)
        y_pred_prob = model.predict(test_x, verbose=2)  # (3,)
        print(y_pred_prob)

        self.result_add(may_m, y_pred_prob[0])
        self.result_add(may_w, y_pred_prob[1])



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


    def result_add(self, status, probabilities):
        points_list = status['points']
        points_4 = points_list[3]
        points_3 = points_list[2]
        base_price = points_3['kline_data']['price']
        price_diff = points_4['kline_data']['price'] - base_price

        klineId = points_4['kline_data']['kLineId']

        for index, i in enumerate(probabilities):
            price = base_price - price_diff * index

            self.BarStateText.append({
                "kLineId": klineId,
                "price": price,
                "timestamp": self.Id_TS_dict.get(klineId),
                "value": f"{np.round(price, 2)}: " + str(np.round(i*100, 2)) + '%'
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






