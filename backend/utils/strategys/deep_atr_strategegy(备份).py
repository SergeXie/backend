import backtrader as bt
import datetime
import pandas as pd
import time
import pandas as pd
import numpy as np
from tensorflow.keras import backend as K
import tensorflow.keras as keras
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import LSTM, Conv1D, MaxPooling1D, Dense, Flatten, Reshape, Add, Input, ConvLSTM1D, LeakyReLU, Dropout, InputLayer
from tensorflow.keras.optimizers import Adam, SGD
from tensorflow.keras.regularizers import l2  # 使用TensorFlow.keras自己的l2 regularizer
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from tensorflow.keras.metrics import AUC  # 使用TensorFlow.keras自己的AUC metric
from sklearn.utils.class_weight import compute_class_weight
from tensorflow.keras.layers import Input, AveragePooling1D, concatenate
from tensorflow.keras.models import load_model
import tensorflow as tf
from utils.indicators import ATRStopLoss
from utils.public_strategy import CommonStrategy
import joblib

# 构建的google模型
def inception_module_1d(x, filters):
    # 1x1 conv
    conv1 = Conv1D(filters=filters[0], kernel_size=1, padding='same', activation='relu')(x)

    # 1x1 conv followed by 3x3 conv
    conv3 = Conv1D(filters=filters[1], kernel_size=1, padding='same', activation='relu')(x)
    conv3 = Conv1D(filters=filters[2], kernel_size=3, padding='same', activation='relu')(conv3)

    # 1x1 conv followed by 5x5 conv
    conv5 = Conv1D(filters=filters[3], kernel_size=1, padding='same', activation='relu')(x)
    conv5 = Conv1D(filters=filters[4], kernel_size=5, padding='same', activation='relu')(conv5)

    # 3x3 max pooling followed by 1x1 conv
    pool = MaxPooling1D(pool_size=3, strides=1, padding='same')(x)
    pool = Conv1D(filters=filters[4], kernel_size=1, padding='same', activation='relu')(pool)

    # concatenate filters
    out = concatenate([conv1, conv3, conv5, pool], axis=-1)

    return out

def create_googlenet_1d(input_shape, num_classes):
    inputs = Input(shape=input_shape)

    # Initial convolution and pooling layers
    x = Conv1D(64, 7, strides=2, padding='same', activation='relu')(inputs)
    x = MaxPooling1D(3, strides=2, padding='same')(x)

    # Inception modules
    x = inception_module_1d(x, [64, 96, 128, 16, 32])
    x = inception_module_1d(x, [128, 128, 192, 32, 96])
    x = MaxPooling1D(3, strides=2, padding='same')(x)

    x = inception_module_1d(x, [192, 96, 208, 16, 48])
    x = inception_module_1d(x, [160, 112, 224, 24, 64])
    x = inception_module_1d(x, [128, 128, 256, 24, 64])
    x = inception_module_1d(x, [112, 144, 288, 32, 64])
    x = inception_module_1d(x, [256, 160, 320, 32, 128])
    x = MaxPooling1D(3, strides=2, padding='same')(x)

    x = inception_module_1d(x, [256, 160, 320, 32, 128])
    x = inception_module_1d(x, [384, 192, 384, 48, 128])

    # Final pooling and dense layers
    x = AveragePooling1D(7, strides=1)(x)
    x = Flatten()(x)
    x = Dropout(0.4)(x)
    x = Dense(num_classes, activation='sigmoid')(x)

    model = Model(inputs, x, name='googlenet_1d')
    return model

class DeepATRStrategy(CommonStrategy):
    # 使用长连接的接口时候，不会传begin_time
    def __init__(self, indicator_params, goodsId=None, begin_time=None):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)

        self.high_data = np.array(self.data.high)
        self.close_data = np.array(self.data.close)
        model_path_dict = {
            0: "deeplearn_model/goole_model_M5.h5",
            1: "deeplearn_model/goole_model_M15.h5",
            2: "deeplearn_model/goole_model_M30.h5",
            3: "deeplearn_model/goole_model_H1.h5",
        }
        model_path = model_path_dict.get(indicator_params.get('TimePeriods', "deeplearn_model/goole_model_M15.h5"))
        # 导入模型
        self.model = tf.keras.models.load_model(model_path)
        # 编译模型
        # self.model.compile(loss='mean_squared_error', optimizer='adam')
        train_prices = self.close_data.reshape(-1, 1)
        # 数据归一化
        # self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.scaler = joblib.load('scalar01')
        # self.scaler = StandardScaler()
        # self.scaler.fit_transform(train_prices)

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
        # X_test = np.array(X_test)
        X_test = self.scaler.transform(X_test)
        # 调整输入数据的维度
        X_test = np.reshape(X_test, (X_test.shape[1], X_test.shape[0], 1))
        # print('shape',X_test.shape)

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
                    tmp1 = [-30, -20, -10, -5, -3]
                    tmp2 = [30, 20, 10, 5, 3]
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
                            self.order = self.buy(size=0.1)
                        elif trend == -1 and Expectations == -1:
                            self.order = self.sell(size=0.1)
                    else:
                        if self.atr_stoploss.lines.trend_change[0] != self.atr_stoploss.lines.trend_change[-1]:
                            if trend == -1 and self.position.size > 0:
                                self.order = self.close(size=0.1)  # 平仓，以下一日开盘价卖出

                                # 平仓后立即卖出
                                if Expectations == -1:
                                    self.order = self.sell(size=0.1)

                            elif trend == 1 and self.position.size < 0:
                                self.order = self.close(size=0.1)  # 平仓，以下一日开盘价卖出
                                if Expectations == 1:
                                    # 平仓后立即买入
                                    self.order = self.buy(size=0.1)

                    self.prev_trend = trend

            # 检查是否到达数据末尾且仍持有仓位
            if self.data_line_count == (self.data.buflen() - (self.atr_len + 1)) and self.position:
                self.order = self.close()  # 平仓，以下一日开盘价卖出

        else:
            print("Invalid trend value")

    def stop(self):
        super().stop()

