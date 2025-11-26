import backtrader as bt
import os
import numpy as np
import requests
import tensorflow as tf
from tensorflow import keras
import backtrader as bt
import joblib

from clients.dl_api_client import call_dl_api
from common.log import log
from core.conf import settings
from models.deepmodel import create_googlenet_1d
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.metrics import AUC


class ResponseDL2Data(bt.Strategy):
    def __init__(self, indicator_params, indicator_name, comments):

        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data = []
        self.result_data_dict = dict()
        self.close_data = np.array(self.data.close)

        # 解析传递的参数
        self.distribution = self.indicator_params.get("TimePeriodssf")
        self.distribution = str(self.distribution).replace("[", "").replace("]", "")
        self.distribution = self.distribution.split(',')
        self.distribution = list(map(float, self.distribution))
        tmp1, tmp2 = split_and_sort_probability(self.distribution)
        self.distribution = tmp1 + tmp2

        # print(type(self.distribution),self.distribution)
        # 后期替换为可输入的参数
        # self.distribution = [-3, -2, -1.5, -1, -0.5, 3, 2, 1.5, 1, 0.5]
        self.kline_goods = self.indicator_params.get("Kline_goods",'')
        self.kline_period = self.indicator_params.get("Kline_period", '')
        self.end_time = self.indicator_params.get("end_time", '')
        self.begin_time = self.indicator_params.get("begin_time", '')

        self.Id_TS_dict = {}
        self.BarState = []

        self.X_test = []
        self.result_data_pre = []

    def next(self):
        pass

    def stop(self):
        """
           方法中调用 DL API
        """
        try:
            log.info(f"正在请求 DL API ... 参数：{self.indicator_params}")
            data = call_dl_api(
                # url=settings.AI_URL,
                url = 'http://192.168.1.182:8083/api/ai/myai',
                task='kline_predict_price',
                goods=self.kline_goods,
                period=self.kline_period,
                begin_time=self.begin_time,
                end_time=self.end_time,
                time_periodssf=self.distribution,
                timeout=120.0,
            )
            print('输出结果',data)
            prices, predicted_prices = data['prices'], data['probabilities']
            log.info(f"DL API 调用成功: prices={prices}, probabilities={predicted_prices}")
        except Exception as e:
            log.exception("调用 DL API 失败: %s", e)

        for i in self.distribution:
            self.BarState.append([
                {
                    "kLineId": self.data.klineId[0],
                    "price": self.data.close[0] + i,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                }
            ])

        for index, i in enumerate(self.distribution):
            self.result_data.append([
                {"kLineId": self.data.klineId[0],
                 "price": self.data.close[0] + i,
                 "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                 "value": str(predicted_prices[index])+'%  '+str(self.data.close[0] + i)}
            ])

        print(self.data.close[0])

    def get_analysis(self):
        self.result_data_dict["lines"] = []
        # 组织数据结构
        for i in self.BarState:
            self.result_data_dict["lines"].append({
                "type": "ray",
                "color": self.indicator_params.get("TrendDMAColor", "#00FFFF"),
                "distance": 10,
                "data": i
            })
        for i in self.result_data:
            self.result_data_dict["lines"].append({
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                "position": 'right',
                "distance": 10,
                "data": i
            })
        self.result_data_dict["lines"].append({
            "type": "line",
            "color": self.indicator_params.get("TrendmidColor", "#00FF00"),
            "data": self.result_data_pre
        })


        return [self.result_data_dict["lines"],
                None,
                None
                ]  # 结束时间

def train_model(self, distribution, old_model_path, new_model_path, from_strategy = False):
    train_prices = self.close_data.reshape(-1, 1)
    # 数据归一化
    train_scaled = train_prices
    ss = joblib.load('./dataset/scalar02')
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
    X_test = X_train[-1]
    # print(X_train[-1])
    # print(y_train[-1])

    # 调整输入数据的维度
    X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], 1))
    print(X_train.shape, y_train.shape)
    epochs = 100
    if from_strategy:
        X_train = X_train[:200,:]
        y_train = y_train[:200,:]
        epochs = 30

    # 查看是否有模型了
    if os.path.exists(f'deeplearn_model/FineTuningModel/{new_model_path}.h5') and not from_strategy:
        model = tf.keras.models.load_model(f'deeplearn_model/FineTuningModel/{new_model_path}.h5')
        print('存在微调模型')
    else:
        # 加载预训练模型
        basemodel = tf.keras.models.load_model(f"deeplearn_model/BaseModel/{old_model_path}.h5")
        # 编译新模型
        input_shape = (100, 1)  # 100 time steps, 1 channel
        num_classes = len(distribution)
        model = create_googlenet_1d(input_shape, num_classes)
        for layer1, layer2 in zip(basemodel.layers[:-1], model.layers[:-1]):
            layer2.set_weights(layer1.get_weights())
            layer2.trainable = False

        model.compile(loss='binary_crossentropy', optimizer=Adam(learning_rate=0.001), metrics=['accuracy', AUC(multi_label=True)])

        # 拟合模型
        model.fit(X_train, y_train, epochs=epochs, batch_size=64)
        model.save(f'deeplearn_model/FineTuningModel/{new_model_path}.h5')

    return model

def split_and_sort_probability(Probability):
    tmp1 = sorted([p for p in Probability if p < 0])
    tmp2 = sorted([p for p in Probability if p > 0], reverse=True)
    return tmp1, tmp2

def change_y(basics, list1, Probability=[-30, -20, -10, -5, -3, 30, 20, 10, 5, 3]):
    # Probability = [-30, -20, -10, -5, -3, 30, 20, 10, 5, 3]
    diff = list1-basics
    # tmp1 = [-30, -20, -10, -5, -3]
    # tmp2 = [30, 20, 10, 5, 3]
    tmp1, tmp2 = split_and_sort_probability(Probability)
    # print(Probability)
    # tmp2 = [3, 5, 10, 20, 30]
    return_result1 = [0] * len(tmp1)
    return_result2 = [0] * len(tmp2)
    # list [ 2.27 -1.39 -3.85 -5.09 -2.86 -4.59 -6.12 -4.6  -3.36 -4.83]

    max_n = round(max(diff), 2)
    min_n = round(min(diff), 2)
    # print(max_n, min_n)

    boundaries1 = [-float('inf')] + tmp1 + [0]
    boundaries2 = [float('inf')] + tmp2 + [0]

    # 遍历边界以找到正确的范围
    for i in range(len(boundaries1) - 1):
        if boundaries1[i] < min_n <= boundaries1[i + 1]:
            # print(f"{boundaries1[i]} < value <= {boundaries1[i + 1]}, {i}")
            # print(min_n/boundaries1[i])
            num = 0
            for j in range(i-1, len(return_result1)):
                if num == 0:
                    # return_result1[j] = round(min_n/boundaries1[i], 2)
                    pass
                else:
                    pass
                    return_result1[j] = 1
                num += 1


    # 遍历边界以找到正确的范围
    for i in range(len(boundaries2) - 1):
        if boundaries2[i] > max_n >= boundaries2[i + 1]:
            # print(f"{boundaries2[i]} > max_n >= {boundaries2[i + 1]}, {i}")
            # print(max_n/boundaries2[i])
            num = 0
            for j in range(i-1, len(return_result2)):
                if num == 0:
                    pass
                    # return_result2[j] = round(max_n/boundaries2[i], 2)
                else:
                    pass
                    return_result2[j] = 1
                num += 1
    # return_result2.reverse()
    # print(return_result1 +return_result2)
    return return_result1 +return_result2
    # print(return_result2)
