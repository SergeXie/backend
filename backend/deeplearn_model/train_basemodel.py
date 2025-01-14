from mymodel2 import create_googlenet_1d
from mymodel2 import get_data
from tensorflow.keras.metrics import AUC
from tensorflow.keras.optimizers import Adam
import numpy as np

import joblib
import tensorflow as tf
from sklearn.preprocessing import StandardScaler

def train_model(self, distribution, model_path):
    # print(self.high_data.reshape(-1,1))
    train_prices = np.array(df['close'].values)
    train_prices = train_prices.reshape(-1, 1)
    # 数据归一化
    ss = joblib.load('scalar02')
    train_scaled = ss.fit_transform(train_prices)

    # train_scaled1 = self.scaler.transform(train_prices)
    # train_scaled = train_prices
    print(len(train_scaled))

    # 创建训练数据集
    X_train = []
    y_train = []
    timesteps = 100  # 时间步长，可根据需求进行调整
    timesteps2 = 10

    for i in range(timesteps + timesteps2 + 1, len(train_scaled)):
        X_train.append(train_scaled[i - timesteps - timesteps2 - 1: i - timesteps2 - 1, 0])  # 归一化
        y = change_y(train_prices[i - timesteps2 - 1], train_prices[i - timesteps2: i, 0], Probability=distribution)
        y_train.append(y)

    X_train, y_train = np.array(X_train), np.array(y_train)
    X_test = X_train[-1]

    print(X_train[-1])
    print(y_train[-1])
    # print(sum(y_train))
    # print(sum(sum(y_train)))


    # 调整输入数据的维度
    X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], 1))
    print(X_train.shape, y_train.shape)

    input_shape = (100, 1)  # 100 time steps, 1 channel
    num_classes = 10
    num_classes = len(distribution)

    # Create and compile the model
    model = create_googlenet_1d(input_shape, num_classes)

    # 编译模型，使用较小的学习率
    model.compile(loss='binary_crossentropy', optimizer=Adam(learning_rate=0.001), metrics=['accuracy', AUC(multi_label=True)])

    # 拟合模型
    model.fit(X_train, y_train, epochs=50, batch_size=64)
    model.save(f'./BaseModel/{model_path}.h5')

    X_test = np.reshape(X_test, (1,100,1))
    print(X_test.shape)
    predicted_prices = model.predict(X_test)
    print(np.round(predicted_prices,2))

    return model

def split_and_sort_probability(Probability):
    tmp1 = sorted([p for p in Probability if p < 0])
    tmp2 = sorted([p for p in Probability if p > 0], reverse=True)
    return tmp1, tmp2

def change_y(basics, list1, Probability=[-30, -20, -10, -5, -3, 30, 20, 10, 5, 3]):
    # Probability = [-30, -20, -10, -5, -3, 30, 20, 10, 5, 3]
    diff = list1-basics
    tmp1 = [-30, -20, -10, -5, -3]
    tmp2 = [30, 20, 10, 5, 3]
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
            num = 0
            for j in range(i-1, len(return_result1)):
                if num == 0:
                    pass
                else:
                    pass
                    return_result1[j] = 1
                num += 1

    # 遍历边界以找到正确的范围
    for i in range(len(boundaries2) - 1):
        if boundaries2[i] > max_n >= boundaries2[i + 1]:
            num = 0
            for j in range(i-1, len(return_result2)):
                if num == 0:
                    pass
                    # return_result2[j] = round(max_n/boundaries2[i], 2)
                else:
                    pass
                    return_result2[j] = 1
                num += 1

    return return_result1 + return_result2


if __name__ == '__main__':
# 假设get_data()返回一个包含'close'列的数据框
#     df = get_data(period='M1')
#     train_model(df, distribution=[-3, -2, -1.5, -1, -0.5, 3, 2, 1.5, 1, 0.5], model_path='FPG-XAUUSD_M1')
    df = get_data(period='M5')
    train_model(df, distribution=[-5, -4, -3, -2, -1, 5, 4, 3, 2, 1], model_path='FPG-XAUUSD_M5')
#     df = get_data(period='M15')
    # train_model(df, distribution=[-30, -20, -10, -5, -3, 30, 20, 10, 5, 3], model_path='FPG-XAUUSD_M15')
#     df = get_data(period='M30')
    # train_model(df, distribution=[-30, -20, -10, -5, -3, 30, 20, 10, 5, 3], model_path='FPG-XAUUSD_M30')
    # df = get_data(period='H1')
    # train_model(df, distribution=[-30, -20, -10, -5, -3, 30, 20, 10, 5, 3], model_path='FPG-XAUUSD_H1')
    # df = get_data(period='H4')
    # train_model(df, distribution=[-100, -80, -60, -40, -20, 100, 80, 60, 40, 20], model_path='FPG-XAUUSD_H4')

