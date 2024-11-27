import backtrader as bt
import numpy as np
import tensorflow as tf
import backtrader as bt
import joblib


class ResponseDLData(bt.Strategy):

    def __init__(self, indicator_params, indicator_name, comments):

        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data = []
        self.result_data_dict = dict()
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
        train_prices = self.close_data.reshape(-1, 1)
        # 数据归一化
        # self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.scaler = joblib.load('scalar01')

        self.Id_TS_dict = {}
        self.BarState = []



    def next(self):
        self.Id_TS_dict[int(self.data.klineId[0])] = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')

        pass


    def stop(self):
        X_test = []
        for i in range(-100, 0):
            X_test.append(self.data.close[i])

        X_test = np.array(X_test).reshape(-1, 1)
        # X_test = np.array(X_test)
        X_test = self.scaler.transform(X_test)
        # 调整输入数据的维度
        X_test = np.reshape(X_test, (X_test.shape[1], X_test.shape[0], 1))
        predicted_prices = self.model.predict(X_test)
        predicted_prices = predicted_prices*100
        # predicted_prices = self.scaler.inverse_transform(predicted_prices)
        # [-30, -20, -10, -5, -3][30, 20, 10, 5, 3]
        predicted_prices = np.round(predicted_prices[0], 2)
        predicted_prices = [str(i) for i in predicted_prices]
        print(predicted_prices)

        for i in [-30, -20, -10, -5, -3, 30, 20, 10, 5, 3]:
            # self.BarState.append([
            #     {
            #         "kLineId": self.data.klineId[0],
            #         "price": self.data.close[0] + i,
            #     },
            #     {
            #         "kLineId": self.data.klineId[-10],
            #         "price": self.data.close[0] + i,
            #     }
            # ])
            self.BarState.append([
                {
                    "kLineId": self.data.klineId[0],
                    "price": self.data.close[0] + i,
                    "timestamp": self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
                }
            ])

        for index, i in enumerate([-30, -20, -10, -5, -3, 30, 20, 10, 5, 3]):
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

        return [self.result_data_dict["lines"],
                None,
                None
                ]  # 结束时间


