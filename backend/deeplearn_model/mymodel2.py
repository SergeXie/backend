import tensorflow as tf
import numpy as np
import pandas as pd
import pymysql
from tensorflow.keras.layers import Input, Conv1D, SeparableConv1D, Activation, BatchNormalization, MaxPooling1D, \
    GlobalAveragePooling1D, Dense, Add, Dropout, AveragePooling1D, Flatten, concatenate
# from tensorflow.keras.layers import Input, AveragePooling1D, concatenate
from tensorflow.keras.models import Sequential, Model

def get_data(period=""):
    # 周期
    # period = "M5"
    # 交易品种
    tradingGoods = "XAUUSD"
    limit = 500
    # 连接到数据库
    conn = pymysql.connect(
        host='192.168.0.126',
        user='cmdb',
        password='cmdb123456',
        database='dql'
    )

    # 创建游标对象
    cursor = conn.cursor()
    # query = (f"SELECT * FROM dql_trading_fpg WHERE type='{period}' AND tradingGoods='{tradingGoods}' ORDER BY tradeDateTime desc LIMIT {limit}")
    query = (f"SELECT * FROM dql_trading_fpg WHERE type LIKE '%{period}%' AND tradingGoods='XAUUSD' AND tradeDateTime < '2024-10-1' ORDER BY tradeDateTime desc")
    cursor.execute(query)
    # 获取查询结果
    results = cursor.fetchall()
    results = reversed(results)

    # 关闭游标和连接
    cursor.close()
    conn.close()

    # class PandasData(bt.feeds.PandasData):
    #     lines = ('pkId', 'open', 'high', 'low', 'close', 'volume', 'openinterest', 'klineId')
    #     params = (
    #         ('pkId', -1),
    #         ('open', -1),
    #         ('high', -1),
    #         ('low', -1),
    #         ('close', -1),
    #         ('volume', -1),
    #         ('openinterest', None),
    #         ('klineId', -1),
    #     )

    # results = get_results()
    # 从数据库加载数据源
    results_data_list = [{"pkId": x[0], "datetime": x[4].strftime("%Y-%m-%d %H:%M:%S"), "open": float(x[9]),
                          "high": float(x[11]), "low": float(x[12]), "close": float(x[10]),
                          "volume": x[13], "openinterest": 0, "klineId": x[0]} for x in results]
    # 添加 backtrader 大脑
    # 添加数据源
    df = pd.DataFrame(results_data_list)
    # df = df.iloc[:200,:]
    # print(df)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    # df.columns

    X_data = []
    close = list(df['close'].values)
    for i in range(len(close)):
        # print(close[i])
        if i < 100:
            continue
        X_data.append(close[i-100: i])

    # return X_data
    return df

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
    # x = Dropout(0.4)(x)
    x = Dense(num_classes, activation='sigmoid')(x)

    model = Model(inputs, x, name='googlenet_1d')
    return model


if __name__ == '__main__':
    # # # 建立模型
    model = create_googlenet_1d(input_shape=(100, 4), num_classes=10)
    model.summary()

