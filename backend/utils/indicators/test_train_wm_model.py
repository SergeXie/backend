import pickle
import backtrader as bt
import numpy as np
import tensorflow as tf
from utils.module.zigzag_calculator import ZigZagCalculator
from utils.module.wm_pattern_recognizer import WMPatternRecognizer
from utils.indicators.wm_predict_bymath import get_klines_in_range
from utils.module.dtw import calc_dtw_distance
from utils.indicators.wm_predict_bymath import klines_to_dataframe, merge_klines
from utils.indicators.wm_predict_bymath import convert_to_weight, probability
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
        self.Ts_to_hloc = {}

        # ----------
        # 参数 # 0为指标,1为模型
        self.wm_from = self.indicator_params.get('WMfrom', 0)
        self.pre_from = self.indicator_params.get('Prefrom', 0)
        # ---------

        self

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
        self.Ts_to_hloc[self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')] = [self.data.high[0],
                                                                                         self.data.low[0],
                                                                                         self.data.open[0],
                                                                                         self.data.close[0]]

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
        for i in all_wm_pattern:
            if "W" in i['pattern_type']:
                self.W_sum += 1
            if "M" in i['pattern_type']:
                self.M_sum += 1

        all_save_pattern = all_wm_pattern + all_none_pattern[:len(all_wm_pattern)]  # 保存的全部形态数据
        # 指标时间段内的全部形态
        all_5point = self.pattern_recognizer.get_all_5point_list()
        for pattern in all_5point:
            # 获取该模式时间范围内的所有K线
            target_klines = get_klines_in_range(
                all_klines=self.all_kline_data,  # 替换为实际的全量K线数据
                start_timestamp=pattern['start_timestamp'],
                end_timestamp=pattern['end_timestamp']
            )
            pattern['target_klines'] = target_klines
            pattern['period'] = "none"

        print('加载保存的数据')
        print(len(all_wm_pattern))
        print(len(all_none_pattern))
        print(all_wm_pattern[0])
        print(all_none_pattern[0])

        from utils.module.t2 import extract_data_to_diffclass, build_lstm_model_status, build_lstm_model_class, \
            extract_xdata, extract_data_to_statusclass
        #  ----------------------------------------这里先预测是否是形态--------------------------------
        X, y = extract_data_to_statusclass(all_save_pattern)
        print(X.shape, y.shape)
        # 划分训练集和测试集（8:2）
        split_idx = int(0.8 * len(X))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        # --------------------------
        # 步骤2：构建并训练模型
        # --------------------------
        max_seq_len = 200
        model = build_lstm_model_status(max_seq_len=max_seq_len, feat_dim=7)
        # 训练模型
        # print("\n开始训练模型...")
        # history = model.fit(
        # X_train, y_train,
        # batch_size=64,
        # epochs=50,
        # validation_data=(X_test, y_test),
        # shuffle=True
        # )

        # model.save('./dataset/pre_status.h5')  # 会创建一个包含模型信息的文件夹
        # 加载模型
        model = tf.keras.models.load_model('./dataset/pre_status.h5')

        # 评估模型
        test_loss, test_acc = model.evaluate(X_test, y_test)
        print(f"\n测试集性能：损失={test_loss:.4f}, 准确率={test_acc:.4f}")
        # --------------------------
        # 步骤3：模型预测
        # --------------------------
        test_x = extract_xdata(all_5point)
        y_pred_prob = model.predict(test_x, verbose=2)  # (3,)
        # print(len(y_pred_prob))
        # print(y_pred_prob)
        predict_wm_pattern = []

        maybe_w = None
        maybe_m = None
        for index, p_list in enumerate(y_pred_prob):
            max_value = np.max(p_list)  # 获取最大值
            max_index = np.argmax(p_list)
            if max_index != 0:
                predict_wm_pattern.append(all_5point[index])
                # print(max_index)
                if max_index == 1:
                    maybe_m = all_5point[index]
                elif max_index == 2:
                    maybe_w = all_5point[index]

        # --------------------------------------------------------------------------------------------
        if self.wm_from == 0:  # 0:math
            print('指标计算形态')
            maybe_m = self.pattern_recognizer.get_maybe_m_patterns()[-1]
            maybe_w = self.pattern_recognizer.get_maybe_w_patterns()[-1]
            for pattern in [maybe_m, maybe_w]:
                # 获取该模式时间范围内的所有K线
                target_klines = get_klines_in_range(
                    all_klines=self.all_kline_data,  # 替换为实际的全量K线数据
                    start_timestamp=pattern['start_timestamp'],
                    end_timestamp=pattern['end_timestamp']
                )
                pattern['target_klines'] = target_klines
                pattern['period'] = "none"
            predict_wm_pattern = [maybe_m, maybe_w]
        elif self.wm_from == 1:
            print('模型计算形态')

        all_wm_pattern_kline = [klines_to_dataframe(merge_klines(i['target_klines'])) for i in all_wm_pattern]
        # ----------------------------------w计算概率-----------------------------------------
        if self.pre_from == 0:
            print('指标计算概率')
            try:
                last_m_start = maybe_m['start']
                last_m_end = maybe_m['end']
                last_m_kline = get_klines_in_range(self.all_kline_data, last_m_start, last_m_end)
                last_m_kline_df = klines_to_dataframe(merge_klines(last_m_kline))
                distance = [calc_dtw_distance(last_m_kline_df, i) for i in all_wm_pattern_kline]
                weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
                m_zigzag_points = [i['points'] for i in all_wm_pattern if "M" in i['pattern_type']]
                weight = [weight[index] for index, i in enumerate(all_wm_pattern) if "M" in i['pattern_type']]
                p = probability(m_zigzag_points, datafrom='m', weight=weight)
                print("m概率:", p)
                price_diff = self.Ts_to_hloc.get(maybe_m['start_third'])[1] - \
                             self.Ts_to_hloc.get(maybe_m['start_four'])[0]  # 高点到低点的价差
                klineId = maybe_m['kLineId_3']
                for index, i in enumerate(p['probabilities']):
                    base_price = self.Ts_to_hloc.get(maybe_m['start_third'])[1]
                    price = base_price + price_diff * index
                    price = np.round(price, digit)
                    # print(i)
                    i = np.round(i * 100, 2)
                    # print('来了', price,self.Id_TS_dict.get(klineId))
                    # print(index)
                    self.BarStateText.append({
                        "kLineId": klineId,
                        "price": price,
                        "timestamp": self.Id_TS_dict.get(klineId),
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
                # -----------------------w计算概率-----------------------------------------
                last_w_start = maybe_w['start']
                last_w_end = maybe_w['end']
                last_w_kline = get_klines_in_range(self.all_kline_data, last_w_start, last_w_end)
                last_w_kline_df = klines_to_dataframe(merge_klines(last_w_kline))
                distance = [calc_dtw_distance(last_w_kline_df, i) for i in all_wm_pattern_kline]
                weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
                w_zigzag_points = [i['points'] for i in all_wm_pattern if "W" in i['pattern_type']]
                weight = [weight[index] for index, i in enumerate(all_wm_pattern) if "W" in i['pattern_type']]
                p = probability(w_zigzag_points, datafrom='w', weight=weight)
                print("w概率:", p)
                price_diff = self.Ts_to_hloc.get(maybe_w['start_third'])[0] - \
                             self.Ts_to_hloc.get(maybe_w['start_four'])[1]  # 高点到低点的价差
                klineId = maybe_w['kLineId_3']
                for index, i in enumerate(p['probabilities']):
                    base_price = self.Ts_to_hloc.get(maybe_w['start_third'])[0]
                    price = base_price + price_diff * index
                    price = np.round(price, digit)
                    # print(i)
                    i = np.round(i * 100, 2)
                    # print('来了', price,self.Id_TS_dict.get(klineId))
                    # print(index)
                    self.BarStateText.append({
                        "kLineId": klineId,
                        "price": price,
                        "timestamp": self.Id_TS_dict.get(klineId),
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
            except Exception as e:
                print(e)

        #  ----------------------------------------预测价差--------------------------------
        if self.pre_from == 1:
            print('模型计算概率')
            X, y = extract_data_to_diffclass(all_save_pattern)  # 用全部数据训练
            # print(X.shape, y.shape)
            # 划分训练集和测试集（8:2）
            split_idx = int(0.8 * len(X))
            X_train, X_test = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]
            # --------------------------
            # 步骤2：构建并训练模型
            # --------------------------
            max_seq_len = 200
            model = build_lstm_model_class(max_seq_len=max_seq_len, feat_dim=7)
            # 训练模型
            print("\n开始训练模型...")
            # history = model.fit(
            # X_train, y_train,
            # batch_size=64,
            # epochs=20,
            # validation_data=(X_test, y_test),
            # shuffle=True
            # )
            # model.save('./dataset/pre_diff.h5')  # 会创建一个包含模型信息的文件夹
            # 加载模型
            model = tf.keras.models.load_model('./dataset/pre_diff.h5')

            # 评估模型
            test_loss, test_acc = model.evaluate(X_test, y_test)
            print(f"\n测试集性能：损失={test_loss:.4f}, 准确率={test_acc:.4f}")
            # --------------------------
            # 步骤3：模型预测
            # --------------------------
            test_x = extract_xdata(predict_wm_pattern)
            y_pred_prob = model.predict(test_x, verbose=2)  # (3,)
            print('预测价差')
            print(y_pred_prob)

            for index, p_list in enumerate(y_pred_prob):
                self.probabilities_result_add(predict_wm_pattern[index], p_list)

            # self.probabilities_result_add(may_m, y_pred_prob[0])
            # self.probabilities_result_add(may_w, y_pred_prob[1])

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

    def probabilities_result_add(self, status, probabilities):
        '绘制概率的结果'
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
                "value": f"{np.round(price, 2)}: " + str(np.round(i * 100, 2)) + '%'
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






