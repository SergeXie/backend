import backtrader as bt
import datetime
import pandas as pd
import time
import pandas as pd
import numpy as np
from tensorflow.keras.models import load_model
import tensorflow as tf
from utils.indicators import ATRStopLoss
from utils.public_strategy import CommonStrategy
import joblib
from utils.indicators.deeplearn_v2 import train_model, split_and_sort_probability



class deeptmp(bt.Indicator):
    lines = ("trend_change", "predicted_diff",)

    # params = (
    #     ('TimePeriodssf', []),
    #     ('amplitude', 0),
    #     ('diff', 0),
    #     ('p_diff', 0)
    # )
    params = (
        ('indicator_params', []),
    )

    def __init__(self):
        print("有没有参数传递",self.params.indicator_params)
        self.indicator_params = self.params.indicator_params

        self.high_data = np.array(self.data.high)
        self.close_data = np.array(self.data.close)
        self.distribution = self.indicator_params.get("TimePeriodssf")
        self.distribution = str(self.distribution).replace("[", "").replace("]", "")
        self.distribution = self.distribution.split(',')
        self.distribution = list(map(float, self.distribution))
        tmp1, tmp2 = split_and_sort_probability(self.distribution)
        self.distribution = tmp1 + tmp2
        # print(type(self.distribution),self.distribution)
        # 后期替换为可输入的参数
        # self.distribution = [-3, -2, -1.5, -1, -0.5, 3, 2, 1.5, 1, 0.5]
        kline_goods = self.indicator_params.get("Kline_goods", '')
        kline_period = self.indicator_params.get("Kline_period", '')
        model_index = [kline_goods] + [kline_period]

        old_model_path = '_'.join(str(i) for i in model_index)
        new_model_path = '_'.join(str(i) for i in self.distribution + [kline_goods] + [kline_period])
        print(old_model_path, new_model_path)

        self.model = train_model(self, self.distribution, old_model_path, new_model_path,
                                 from_strategy=True)  # 数据  y的分布  模型路径和名称
        # 编译模型
        # self.model.compile(loss='mean_squared_error', optimizer='adam')
        train_prices = self.close_data.reshape(-1, 1)

        self.X_test = []

        print("参数", self.indicator_params)
        self.amplitude = self.indicator_params.get("amplitude", '')  # 振幅：可操作的空间
        self.diff = self.indicator_params.get("diff", '')  # 偏差：确定止盈止损
        self.p_diff = self.indicator_params.get("p_diff", '')  # 概率差
        # self.distribution  [-30.0, -20.0, -10.0, -5.0, -3.0, 30.0, 20.0, 10.0, 5.0, 3.0]
        greater_elements = None
        self.greater_elements = [(item, idx) for idx, item in enumerate(tmp2) if item > self.amplitude]
        print(self.greater_elements[-1][0], "是我")  # [(30.0, 0), (20.0, 1)]
        # 表示是第一个符合振幅的索引
        # self.amplitude_tmp = [False, True, False, False, False, False, True, False, False, False]
        self.amplitude_tmp = [True if abs(i) == self.greater_elements[-1][0] else False for i in self.distribution]


        self.change = 0  # 初始化趋势 1 上趋势 -1 下趋势
        print('成功了')

        self.X_test_list = []

    def next(self):
        pass

        # 整理出测试数据的格式，保证长度为100
        self.X_test.append(self.data.close[0])
        if len(self.X_test) < 100:
            return
        elif len(self.X_test) > 100:
            self.X_test.pop(0)
        X_test = self.X_test.copy()
        # print(X_test[-1])

        if len(self) < 200:
            return

        # 进行归一化
        X_test = np.array(X_test).reshape(-1, 1)
        ss = joblib.load('scalar02')
        X_test = ss.fit_transform(X_test)
        # 调整输入数据的维度
        self.X_test_list.append(X_test)

        # print(len(self.X_test_list))

        if len(self) == self.data.buflen():
            self.X_test_list = np.array(self.X_test_list)

            print(self.X_test_list.shape)
            predicted_pricess = self.model.predict(self.X_test_list)
            # print(len(predicted_prices))
            for i in range(len(predicted_pricess)):
                # print(i-len(predicted_pricess)+1)
                predicted_prices = predicted_pricess[i]
                predicted_prices = predicted_prices * 100
                predicted_prices = np.round(predicted_prices, 2)
                predicted_prices_str = [str(i) for i in predicted_prices]
                print(predicted_prices_str)
                # print(self.amplitude_tmp)
                # print(predicted_prices[self.amplitude_tmp])
                predicted_diff = predicted_prices[self.amplitude_tmp][0] - predicted_prices[self.amplitude_tmp][1]  # 负概率 - 正概率
                # diff = abs(predicted_diff)

                # self.lines.trend_change[i-len(predicted_pricess)+1] = -1 if diff > 0 else 1
                self.lines.predicted_diff[i-len(predicted_pricess)+1] = predicted_diff




        # X_test = np.reshape(X_test, (X_test.shape[1], X_test.shape[0], 1))


class DeepStrategy(CommonStrategy):
    # 使用长连接的接口时候，不会传begin_time
    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        # 接收参数变量
        self.indicator_params = indicator_params
        self.baseLots=baseLots

        self.amplitude = self.indicator_params.get("amplitude", '')  # 振幅：可操作的空间
        self.diff = self.indicator_params.get("diff", '')  # 偏差：确定止盈止损
        self.p_diff = self.indicator_params.get("p_diff", '')  # 概率差

        # self.high_data = np.array(self.data.high)
        # self.close_data = np.array(self.data.close)
        # self.distribution = self.indicator_params.get("TimePeriodssf")
        # self.distribution = str(self.distribution).replace("[", "").replace("]", "")
        # self.distribution = self.distribution.split(',')
        # self.distribution = list(map(float, self.distribution))
        # tmp1, tmp2 = split_and_sort_probability(self.distribution)
        # self.distribution = tmp1 + tmp2
        # # print(type(self.distribution),self.distribution)
        # # 后期替换为可输入的参数
        # # self.distribution = [-3, -2, -1.5, -1, -0.5, 3, 2, 1.5, 1, 0.5]
        # kline_goods = self.indicator_params.get("Kline_goods", '')
        # kline_period = self.indicator_params.get("Kline_period", '')
        # model_index = [kline_goods] + [kline_period]
        #
        # old_model_path = '_'.join(str(i) for i in model_index)
        # new_model_path = '_'.join(str(i) for i in self.distribution + [kline_goods] + [kline_period])
        # print(old_model_path, new_model_path)
        #
        # self.model = train_model(self, self.distribution, old_model_path, new_model_path, from_strategy=True)  # 数据  y的分布  模型路径和名称
        # # 编译模型
        # # self.model.compile(loss='mean_squared_error', optimizer='adam')
        # train_prices = self.close_data.reshape(-1, 1)
        #
        # self.X_test = []
        #
        # print("参数",self.indicator_params)
        # self.amplitude = self.indicator_params.get("amplitude", '')  # 振幅：可操作的空间
        # self.diff = self.indicator_params.get("diff", '')  # 偏差：确定止盈止损
        # self.p_diff = self.indicator_params.get("p_diff", '')  # 概率差
        # # self.distribution  [-30.0, -20.0, -10.0, -5.0, -3.0, 30.0, 20.0, 10.0, 5.0, 3.0]
        # greater_elements = None
        # self.greater_elements = [(item, idx) for idx, item in enumerate(tmp2) if item > self.amplitude]
        # print(self.greater_elements[-1][0],"是我")  # [(30.0, 0), (20.0, 1)]
        # # 表示是第一个符合振幅的索引
        # # self.amplitude_tmp = [False, True, False, False, False, False, True, False, False, False]
        # self.amplitude_tmp = [True if abs(i) == self.greater_elements[-1][0] else False for i in self.distribution]
        #
        # self.sl = 0  # 止损
        # self.tp = 0  # 止盈

        self.Deeptmp = deeptmp(self.data,
                               indicator_params = self.indicator_params,
                               )



        self.sl = 0  # 止损
        self.tp = 0  # 止盈


    def next(self):
        # print(len(self), self.Deeptmp.lines.predicted_diff[0], self.Deeptmp.greater_elements[-1][0])

        # 调用父类方法 （固定写法）
        super().calculate_values()
        # # 整理出测试数据的格式，保证长度为100
        # self.X_test.append(self.data.close[0])
        # if len(self.X_test) < 100:
        #     return
        # elif len(self.X_test) > 100:
        #     self.X_test.pop(0)
        # X_test = self.X_test.copy()
        # # print(X_test[-1])
        #
        # if len(self) < 150:
        #     return
        #
        # # 进行归一化
        # X_test = np.array(X_test).reshape(-1, 1)
        # ss = joblib.load('scalar02')
        # X_test = ss.fit_transform(X_test)
        # # 调整输入数据的维度
        # X_test = np.reshape(X_test, (X_test.shape[1], X_test.shape[0], 1))
        # diff = 0
        # # 只有在不持单的时候才进行预测
        # if not self.position:
        #     predicted_prices = self.model.predict(X_test)
        #     predicted_prices = predicted_prices * 100
        #     # predicted_prices = self.scaler.inverse_transform(predicted_prices)
        #     # [-30, -20, -10, -5, -3][30, 20, 10, 5, 3]
        #     predicted_prices = np.round(predicted_prices[0], 2)
        #     predicted_prices_str = [str(i) for i in predicted_prices]
        #     print(predicted_prices_str)
        #     # print(self.amplitude_tmp)
        #     print(predicted_prices[self.amplitude_tmp])
        #     predicted_diff = predicted_prices[self.amplitude_tmp][0] - predicted_prices[self.amplitude_tmp][1]  # 负概率 - 正概率
        #     diff = abs(predicted_diff)
        #
        # 看概率进行下单
        predicted_diff = self.Deeptmp.lines.predicted_diff[0]
        diff = abs(predicted_diff)
        greater_elements = self.Deeptmp.greater_elements

        if diff > self.p_diff*100 and not self.position:
            if predicted_diff > 0:  # 负的概率更大
                print('负的概率更大')
                self.order = self.sell(size=self.baseLots)
                self.sl = self.data.close[0] + greater_elements[-1][0] + self.diff  # 止损
                self.tp = self.data.close[0] - greater_elements[-1][0] - self.diff  # 止盈
            elif predicted_diff < 0:
                print('正的概率更大')
                self.order = self.buy(size=self.baseLots)
                self.sl = self.data.close[0] - greater_elements[-1][0] - self.diff  # 止损
                self.tp = self.data.close[0] + greater_elements[-1][0] + self.diff  # 止盈

        # 根据止盈止损进行平仓
        if self.position and self.position.size > 0:  # 买多
            if self.data.high[0] > self.tp or self.data.low[0] < self.sl:
                print('买多',self.tp, self.sl, self.data.high[0] > self.tp, self.data.low[0] < self.sl)
                self.order = self.close(size=self.baseLots)
                self.sl = 0  # 止损
                self.tp = 0  # 止盈
        elif self.position and self.position.size < 0:  # 买空
            if self.data.high[0] > self.sl or self.data.low[0] < self.tp:
                print('买空', self.tp, self.sl, self.data.high[0] > self.tp, self.data.low[0] < self.sl)
                self.order = self.close(size=self.baseLots)
                self.sl = 0  # 止损
                self.tp = 0  # 止盈


    def stop(self):
        super().stop()

