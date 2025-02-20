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


class DeepATRStrategy(CommonStrategy):
    # 使用长连接的接口时候，不会传begin_time
    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        # 接收参数变量
        self.indicator_params = indicator_params
        print(self.indicator_params)

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

        self.model = train_model(self, self.distribution, old_model_path, new_model_path, from_strategy=True)  # 数据  y的分布  模型路径和名称
        # 编译模型
        self.scaler = joblib.load('scalar02')


        self.dir = 0
        self.offset = 0
        self.indicator_params = indicator_params
        # 初始化指标
        self.atr_stoploss = ATRStopLoss(self.data,
                                        atr_len=self.indicator_params.get("period", 10),
                                        multiplier=self.indicator_params.get("Multiplier", 3.0))
        self.atr_len = self.atr_stoploss.params.atr_len
        self.data_line_count = 0
        self.er_data_line_count = 0
        self.new_trend_change = 0
        self.trend_change = self.atr_stoploss.lines.trend_change
        self.prev_trend = 0
        print("line的总长度：", self.data0.buflen())
        self.start_date = datetime.datetime.strptime('2024-01-01', '%Y-%m-%d')  # 设置开始日期

        self.dataclose = self.datas[0].close
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.dataopen = self.datas[0].open

        self.baseLots = baseLots

        print(goodsId, begin_time)


    def next(self):
        # 调用父类方法 （固定写法）
        super().calculate_values()
        if len(self) < 100:
            return
        X_test = []
        for i in range(-100, 0):
            X_test.append(self.data.close[i])
        X_test = np.array(X_test).reshape(-1, 1)
        ss = joblib.load('scalar02')
        X_test = ss.fit_transform(X_test)
        # 调整输入数据的维度
        X_test = np.reshape(X_test, (X_test.shape[1], X_test.shape[0], 1))


        # ======================   =================#
        self.data_line_count += 1

        # 获取当前数据点的时间
        current_date = self.datas[0].datetime.datetime(0)

        # 只在 current_date 大于等于 start_date 时执行策略逻辑
        if current_date <= self.start_date:
            self.er_data_line_count += 1
            return

        trend = self.atr_stoploss.lines.trend_change[0]

        if trend == 1 or trend == -1:
            if self.prev_trend == 0:
                self.prev_trend = trend
            else:
                if self.prev_trend != trend:
                    # 使用模型进行预测
                    predicted_prices = self.model.predict(X_test)
                    # predicted_prices = self.scaler.inverse_transform(predicted_prices)
                    # [-30, -20, -10, -5, -3][30, 20, 10, 5, 3]
                    predicted_prices = np.round(predicted_prices[0], 2)
                    print(predicted_prices)
                    tmp1, tmp2 = split_and_sort_probability(self.distribution)
                    # tmp1 = [-30, -20, -10, -5, -3]
                    # tmp2 = [30, 20, 10, 5, 3]
                    print(tmp1, tmp2)
                    pre_sell = predicted_prices[:5]
                    pre_buy = predicted_prices[5:]
                    # 通过概率计算期望
                    PositiveExpectations = sum(pre_buy * tmp2)  # 正期望
                    NegativeExpectations = sum(pre_sell * tmp1)  # 负期望
                    print(PositiveExpectations, NegativeExpectations)
                    Expectations = 1 if PositiveExpectations - abs(NegativeExpectations) > 0 else -1

                    # 检查是否有持仓
                    if not self.position:
                        if trend == 1 and Expectations == 1:

                            self.order = self.buy(size=self.baseLots)
                        elif trend == -1 and Expectations == -1:
                            self.order = self.sell(size=self.baseLots)
                    else:
                        if self.atr_stoploss.lines.trend_change[0] != self.atr_stoploss.lines.trend_change[-1]:
                            if trend == -1 and self.position.size > 0:
                                self.order = self.close(size=self.baseLots)  # 平仓，以下一日开盘价卖出

                                # 平仓后立即卖出
                                if Expectations == -1:
                                    self.order = self.sell(size=self.baseLots)

                            elif trend == 1 and self.position.size < 0:
                                self.order = self.close(size=self.baseLots)  # 平仓，以下一日开盘价卖出
                                if Expectations == 1:
                                    # 平仓后立即买入
                                    self.order = self.buy(size=self.baseLots)

                    self.prev_trend = trend

            # 检查是否到达数据末尾且仍持有仓位
            if self.data_line_count == (self.data.buflen() - (self.atr_len + 1)) and self.position:
                self.order = self.close()  # 平仓，以下一日开盘价卖出

        else:
            print("Invalid trend value")

    def stop(self):
        super().stop()

