import os
import asyncio
import gc
import numpy as np
import tensorflow as tf
from utils.public_strategy import CommonStrategy
import joblib
from utils.indicators.deeplearn_v2 import train_model, split_and_sort_probability, change_y
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.metrics import AUC
from tensorflow.keras import backend as K
from multiprocessing import Process, Queue
import objgraph

# 设置 TensorFlow 内存增长
gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
    except RuntimeError as e:
        print(e)

class DeepRealtimeStrategy(CommonStrategy):
    # 使用长连接的接口时候，不会传begin_time
    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        # 接收参数变量
        self.indicator_params = indicator_params
        self.baseLots = baseLots

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
        # self.model.compile(loss='mean_squared_error', optimizer='adam')
        train_prices = self.close_data.reshape(-1, 1)

        self.X_test = []

        print("参数",self.indicator_params)
        self.amplitude = self.indicator_params.get("amplitude", '')  # 振幅：可操作的空间
        self.diff = self.indicator_params.get("diff", '')  # 偏差：确定止盈止损
        self.p_diff = self.indicator_params.get("p_diff", '')  # 概率差
        # self.distribution  [-30.0, -20.0, -10.0, -5.0, -3.0, 30.0, 20.0, 10.0, 5.0, 3.0]
        greater_elements = None
        self.greater_elements = [(item, idx) for idx, item in enumerate(tmp2) if item > self.amplitude]
        print(self.greater_elements[-1][0],"是我")  # [(30.0, 0), (20.0, 1)]
        # 表示是第一个符合振幅的索引
        # self.amplitude_tmp = [False, True, False, False, False, False, True, False, False, False]
        self.amplitude_tmp = [True if abs(i) == self.greater_elements[-1][0] else False for i in self.distribution]

        self.sl = 0  # 止损
        self.tp = 0  # 止盈

        self.closedata_to_lastest_close = []


    def next(self):

        # 调用父类方法 （固定写法）
        super().calculate_values()
        ss = joblib.load('./dataset/scalar02')
        self.closedata_to_lastest_close.append(self.data.close[0])
        # 整理出测试数据的格式，保证长度为100
        self.X_test.append(self.data.close[0])
        if len(self.X_test) < 100:
            return
        elif len(self.X_test) > 100:
            self.X_test.pop(0)
        X_test = self.X_test.copy()
        # print(X_test[-1])

        if len(self) < 150:
            return

        model = Local_train_model(model=self.model,
                                            data=np.array(self.closedata_to_lastest_close),
                                            ss=ss, distribution=self.distribution)

        # 进行归一化
        X_test = np.array(X_test).reshape(-1, 1)

        X_test = ss.fit_transform(X_test)
        # 调整输入数据的维度
        X_test = np.reshape(X_test, (X_test.shape[1], X_test.shape[0], 1))



        diff = 0
        # 只有在不持单的时候才进行预测
        if not self.position:
            predicted_prices = model.predict(X_test)

            # del X_test, self.model
            tf.keras.backend.clear_session()

            predicted_prices = predicted_prices * 100
            # predicted_prices = self.scaler.inverse_transform(predicted_prices)
            # [-30, -20, -10, -5, -3][30, 20, 10, 5, 3]
            predicted_prices = np.round(predicted_prices[0], 2)
            predicted_prices_str = [str(i) for i in predicted_prices]
            print(predicted_prices_str)
            # print(self.amplitude_tmp)
            print(predicted_prices[self.amplitude_tmp])
            predicted_diff = predicted_prices[self.amplitude_tmp][0] - predicted_prices[self.amplitude_tmp][1]  # 负概率 - 正概率
            diff = abs(predicted_diff)

        # 看概率进行下单
        if diff > self.p_diff*100 and not self.position:
            if predicted_diff > 0:  # 负的概率更大
                print('负的概率更大')
                self.order = self.sell(size=self.baseLots)
                self.sl = self.data.close[0] + self.greater_elements[-1][0] + self.diff  # 止损
                self.tp = self.data.close[0] - self.greater_elements[-1][0] - self.diff  # 止盈
            elif predicted_diff < 0:
                print('正的概率更大')
                self.order = self.buy(size=self.baseLots)
                self.sl = self.data.close[0] - self.greater_elements[-1][0] - self.diff  # 止损
                self.tp = self.data.close[0] + self.greater_elements[-1][0] + self.diff  # 止盈

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
        gc.collect()
        # objgraph.show_most_common_types(limit=50)

    def stop(self):
        super().stop()



def Local_train_model(model, data, ss, distribution):
    print('data',len(data))

    train_prices = data.reshape(-1, 1)
    # 数据归一化
    train_scaled = ss.fit_transform(train_prices)

    # 创建训练数据集
    X_train = []
    y_train = []
    timesteps = 100  # 时间步长，可根据需求进行调整
    timesteps2 = 10

    for i in range(timesteps + timesteps2 + 1, len(train_scaled)):
        X_train.append(train_scaled[i - timesteps - timesteps2 - 1: i - timesteps2 - 1, 0])  # 归一化
        y = change_y(train_prices[i - timesteps2 - 1], train_prices[i - timesteps2: i, 0], Probability=distribution)
        # print(y)
        y_train.append(y)

    X_train, y_train = np.array(X_train), np.array(y_train)
    # print(X_train[-1])
    # print(y_train[-1])

    # 调整输入数据的维度
    X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], 1))
    print(X_train.shape, y_train.shape)
    epochs = 100
    model.compile(loss='binary_crossentropy', optimizer=Adam(learning_rate=0.001),
                  metrics=['accuracy', AUC(multi_label=True)])


    # 创建队列用于传递训练后的模型
    queue = Queue()
    # 创建子进程
    p = Process(target=train_model_in_process, args=(model, X_train, y_train, queue))
    p.start()
    p.join()  # 等待子进程结束

    # 从队列中获取训练后的模型
    trained_model = queue.get()

    # 拟合模型
    # model.fit(X_train, y_train, epochs=1, batch_size=64)
    # 释放内存
    del X_train, y, data
    del y_train
    del train_prices
    del train_scaled
    tf.keras.backend.clear_session()
    gc.collect(2)
    gc.set_debug(gc.DEBUG_LEAK)

    return trained_model

def train_model_in_process(model, X_train, y_train, queue):
    """
    在子进程中训练模型
    """
    # 编译模型
    model.compile(loss='binary_crossentropy', optimizer=Adam(learning_rate=0.001),
                  metrics=['accuracy', AUC(multi_label=True)])
    # 拟合模型
    history = model.fit(X_train, y_train, epochs=1, batch_size=64)
    # 将训练后的模型放入队列返回
    queue.put(model)