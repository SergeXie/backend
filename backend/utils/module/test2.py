import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import Dense, Dropout, LSTM, Input, concatenate
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import ReduceLROnPlateau
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score


class WMPricePredictor:
    """W形态价格预测模型类，支持FCNN、LSTM和混合模型"""

    def __init__(self, input_shape, learning_rate=0.001, random_state=42):
        """
        初始化预测器

        参数:
            input_shape: 输入特征的形状，对于FCNN是(特征数,), 对于LSTM是(时间步, 特征数)
            learning_rate: 学习率
            random_state: 随机种子，保证结果可复现
        """
        self.input_shape = input_shape
        self.learning_rate = learning_rate
        self.random_state = random_state
        self.models = {}  # 存储不同类型的模型
        self.scaler = None  # 用于后续预测的标准化器

        # 设置随机种子
        np.random.seed(random_state)

    def build_fcnn_model(self, layers=[64, 32], dropout_rate=0.2):
        """
        构建全连接神经网络模型

        参数:
            layers: 各隐藏层的神经元数量列表
            dropout_rate: Dropout层的丢弃率
        """
        model = Sequential(name="FCNN_Model")

        # 输入层
        model.add(Dense(layers[0], activation='relu', input_shape=(self.input_shape,)))
        model.add(Dropout(dropout_rate))

        # 隐藏层
        for units in layers[1:]:
            model.add(Dense(units, activation='relu'))
            model.add(Dropout(dropout_rate))

        # 输出层（预测第5个点的价格）
        model.add(Dense(1, activation='linear'))

        # 编译模型
        optimizer = Adam(learning_rate=self.learning_rate)
        model.compile(optimizer=optimizer,
                      loss='mse',
                      metrics=['mae'])

        self.models['fcnn'] = model
        return model

    def build_lstm_model(self, lstm_units=[32, 16], dense_units=8, dropout_rate=0.2):
        """
        构建LSTM模型

        参数:
            lstm_units: LSTM层的神经元数量列表
            dense_units: 全连接层的神经元数量
            dropout_rate: Dropout层的丢弃率
        """
        # 输入形状应为 (时间步, 特征数)
        model = Sequential(name="LSTM_Model")

        # 第一个LSTM层，需要指定input_shape
        model.add(LSTM(lstm_units[0], return_sequences=True,
                       input_shape=self.input_shape))
        model.add(Dropout(dropout_rate))

        # 后续LSTM层
        for units in lstm_units[1:]:
            # 最后一个LSTM层不需要返回序列
            return_seq = (units != lstm_units[-1])
            model.add(LSTM(units, return_sequences=return_seq))
            model.add(Dropout(dropout_rate))

        # 全连接层
        model.add(Dense(dense_units, activation='relu'))
        model.add(Dropout(dropout_rate))

        # 输出层
        model.add(Dense(1, activation='linear'))

        # 编译模型
        optimizer = Adam(learning_rate=self.learning_rate)
        model.compile(optimizer=optimizer,
                      loss='mse',
                      metrics=['mae'])

        self.models['lstm'] = model
        return model

    def build_hybrid_model(self, fcnn_layers=[32], lstm_units=[32],
                           dense_units=16, dropout_rate=0.2):
        """
        构建FCNN+LSTM混合模型

        参数:
            fcnn_layers: FCNN分支的神经元数量列表
            lstm_units: LSTM分支的神经元数量列表
            dense_units: 融合后的全连接层神经元数量
            dropout_rate: Dropout层的丢弃率
        """
        # 假设输入形状是 (时间步, 特征数)
        # 分离静态特征和时序特征（这里简单地将一半特征视为静态，一半视为时序）
        time_steps, n_features = self.input_shape
        static_features = n_features // 2
        temporal_features = n_features - static_features

        # 输入层
        input_layer = Input(shape=self.input_shape, name='main_input')

        # 静态特征分支 (取前半部分特征)
        static_branch = Input(shape=(static_features,), name='static_input')
        x = Dense(fcnn_layers[0], activation='relu')(static_branch)
        x = Dropout(dropout_rate)(x)
        for units in fcnn_layers[1:]:
            x = Dense(units, activation='relu')(x)
            x = Dropout(dropout_rate)(x)
        static_output = x

        # 时序特征分支 (取后半部分特征)
        temporal_branch = Input(shape=(time_steps, temporal_features), name='temporal_input')
        y = LSTM(lstm_units[0], return_sequences=True)(temporal_branch)
        y = Dropout(dropout_rate)(y)
        for units in lstm_units[1:]:
            return_seq = (units != lstm_units[-1])
            y = LSTM(units, return_sequences=return_seq)(y)
            y = Dropout(dropout_rate)(y)
        temporal_output = y

        # 融合两个分支
        merged = concatenate([static_output, temporal_output])
        z = Dense(dense_units, activation='relu')(merged)
        z = Dropout(dropout_rate)(z)

        # 输出层
        output_layer = Dense(1, activation='linear')(z)

        # 构建模型
        model = Model(inputs=[static_branch, temporal_branch],
                      outputs=output_layer, name="Hybrid_Model")

        # 编译模型
        optimizer = Adam(learning_rate=self.learning_rate)
        model.compile(optimizer=optimizer,
                      loss='mse',
                      metrics=['mae'])

        self.models['hybrid'] = model
        return model

    def train(self, model_type, X_train, y_train, X_val, y_val,
              batch_size=32, epochs=100, model_save_path=None):
        """
        训练模型

        参数:
            model_type: 模型类型，'fcnn'、'lstm' 或 'hybrid'
            X_train: 训练特征
            y_train: 训练标签
            X_val: 验证特征
            y_val: 验证标签
            batch_size: 批次大小
            epochs: 训练轮次
            model_save_path: 模型保存路径，None则不保存

        返回:
            训练历史记录
        """
        if model_type not in self.models:
            raise ValueError(f"模型类型 {model_type} 不存在，请先构建模型")

        model = self.models[model_type]

        # 定义回调函数
        callbacks = [
            # 早停法，防止过拟合
            EarlyStopping(monitor='val_loss', patience=10,
                          restore_best_weights=True),
            # 学习率衰减
            ReduceLROnPlateau(monitor='val_loss', factor=0.5,
                              patience=5, min_lr=1e-6)
        ]

        # 如果指定了保存路径，添加模型检查点回调
        if model_save_path:
            checkpoint = ModelCheckpoint(
                model_save_path, monitor='val_loss',
                save_best_only=True, mode='min'
            )
            callbacks.append(checkpoint)

        # 训练模型
        if model_type == 'hybrid':
            # 混合模型需要特殊处理输入
            # 将输入分成静态和时序两部分
            time_steps, n_features = self.input_shape
            static_features = n_features // 2

            # 静态特征：取每个时间步的前半部分特征，然后取最后一个时间步的值
            X_train_static = X_train[:, -1, :static_features]
            X_val_static = X_val[:, -1, :static_features]

            # 时序特征：取每个时间步的后半部分特征
            X_train_temporal = X_train[:, :, static_features:]
            X_val_temporal = X_val[:, :, static_features:]

            history = model.fit(
                [X_train_static, X_train_temporal], y_train,
                validation_data=([X_val_static, X_val_temporal], y_val),
                batch_size=batch_size,
                epochs=epochs,
                callbacks=callbacks,
                verbose=1
            )
        else:
            # FCNN和LSTM模型的训练
            history = model.fit(
                X_train, y_train,
                validation_data=(X_val, y_val),
                batch_size=batch_size,
                epochs=epochs,
                callbacks=callbacks,
                verbose=1
            )

        return history

    def evaluate(self, model_type, X_test, y_test):
        """
        评估模型性能

        参数:
            model_type: 模型类型，'fcnn'、'lstm' 或 'hybrid'
            X_test: 测试特征
            y_test: 测试标签

        返回:
            包含各项评估指标的字典
        """
        if model_type not in self.models:
            raise ValueError(f"模型类型 {model_type} 不存在")

        model = self.models[model_type]

        # 预测
        if model_type == 'hybrid':
            time_steps, n_features = self.input_shape
            static_features = n_features // 2
            X_test_static = X_test[:, -1, :static_features]
            X_test_temporal = X_test[:, :, static_features:]
            y_pred = model.predict([X_test_static, X_test_temporal], verbose=0)
        else:
            y_pred = model.predict(X_test, verbose=0)

        # 计算评估指标
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        metrics = {
            'MSE': mse,
            'RMSE': rmse,
            'MAE': mae,
            'R2': r2
        }

        print(f"模型评估 ({model_type}):")
        print(f"  MSE: {mse:.4f}")
        print(f"  RMSE: {rmse:.4f}")
        print(f"  MAE: {mae:.4f}")
        print(f"  R²  : {r2:.4f}")

        return metrics, y_pred

    def plot_training_history(self, history):
        """绘制训练历史曲线"""
        # 绘制损失曲线
        plt.figure(figsize=(12, 5))

        # 损失图
        plt.subplot(1, 2, 1)
        plt.plot(history.history['loss'], label='训练损失')
        plt.plot(history.history['val_loss'], label='验证损失')
        plt.title('模型损失')
        plt.xlabel('Epoch')
        plt.ylabel('Loss (MSE)')
        plt.legend()

        # MAE图
        plt.subplot(1, 2, 2)
        plt.plot(history.history['mae'], label='训练MAE')
        plt.plot(history.history['val_mae'], label='验证MAE')
        plt.title('模型MAE')
        plt.xlabel('Epoch')
        plt.ylabel('MAE')
        plt.legend()

        plt.tight_layout()
        plt.show()

    def plot_prediction(self, y_true, y_pred, title="预测 vs 实际值"):
        """绘制预测值与实际值对比图"""
        plt.figure(figsize=(10, 6))
        plt.scatter(y_true, y_pred, alpha=0.5)
        plt.plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--')
        plt.xlabel('实际价格')
        plt.ylabel('预测价格')
        plt.title(title)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.show()

    def save_model(self, model_type, path):
        """保存模型"""
        if model_type not in self.models:
            raise ValueError(f"模型类型 {model_type} 不存在")
        self.models[model_type].save(path)
        print(f"模型已保存至 {path}")

    def load_model(self, model_type, path):
        """加载模型"""
        from tensorflow.keras.models import load_model
        self.models[model_type] = load_model(path)
        print(f"模型已从 {path} 加载")


# 使用示例
if __name__ == "__main__":
    # 生成模拟数据（实际使用时替换为你的预处理数据）
    def generate_sample_data(n_samples=500):
        """生成模拟的预处理数据用于演示"""
        # FCNN输入形状: (n_samples, n_features)
        # 假设我们有31个特征（如前面预处理函数生成的）
        n_features = 31
        X_fcnn = np.random.randn(n_samples, n_features)

        # LSTM输入形状: (n_samples, time_steps, features_per_step)
        # 假设4个时间步（对应4个点），每个时间步8个特征
        time_steps = 4
        features_per_step = 8
        X_lstm = np.random.randn(n_samples, time_steps, features_per_step)

        # 生成模拟标签（第5个点的价格）
        # 简单起见，让标签与输入特征有一定相关性
        y = 3500 + 50 * X_fcnn[:, 0] + 30 * X_fcnn[:, 1] + 20 * np.random.randn(n_samples)

        # 划分训练集、验证集、测试集
        from sklearn.model_selection import train_test_split
        X_train_fcnn, X_temp_fcnn, y_train, y_temp = train_test_split(
            X_fcnn, y, test_size=0.3, random_state=42
        )
        X_val_fcnn, X_test_fcnn, y_val, y_test = train_test_split(
            X_temp_fcnn, y_temp, test_size=1 / 3, random_state=42
        )

        # LSTM数据划分
        X_train_lstm, X_temp_lstm, _, _ = train_test_split(
            X_lstm, y, test_size=0.3, random_state=42
        )
        X_val_lstm, X_test_lstm, _, _ = train_test_split(
            X_temp_lstm, y_temp, test_size=1 / 3, random_state=42
        )

        return (X_train_fcnn, X_val_fcnn, X_test_fcnn,
                X_train_lstm, X_val_lstm, X_test_lstm,
                y_train, y_val, y_test)


    # 生成模拟数据
    (X_train_fcnn, X_val_fcnn, X_test_fcnn,
     X_train_lstm, X_val_lstm, X_test_lstm,
     y_train, y_val, y_test) = generate_sample_data(n_samples=800)

    # 1. 训练FCNN模型
    print("\n===== 训练FCNN模型 =====")
    fcnn_predictor = WMPricePredictor(input_shape=X_train_fcnn.shape[1], learning_rate=0.001)
    fcnn_predictor.build_fcnn_model(layers=[64, 32])
    fcnn_history = fcnn_predictor.train(
        'fcnn', X_train_fcnn, y_train, X_val_fcnn, y_val,
        batch_size=32, epochs=100
    )
    fcnn_predictor.plot_training_history(fcnn_history)
    fcnn_metrics, fcnn_pred = fcnn_predictor.evaluate('fcnn', X_test_fcnn, y_test)
    fcnn_predictor.plot_prediction(y_test, fcnn_pred, "FCNN 预测 vs 实际值")

    # 2. 训练LSTM模型
    print("\n===== 训练LSTM模型 =====")
    lstm_input_shape = (X_train_lstm.shape[1], X_train_lstm.shape[2])
    lstm_predictor = WMPricePredictor(input_shape=lstm_input_shape, learning_rate=0.001)
    lstm_predictor.build_lstm_model(lstm_units=[32, 16])
    lstm_history = lstm_predictor.train(
        'lstm', X_train_lstm, y_train, X_val_lstm, y_val,
        batch_size=32, epochs=100
    )
    lstm_predictor.plot_training_history(lstm_history)
    lstm_metrics, lstm_pred = lstm_predictor.evaluate('lstm', X_test_lstm, y_test)
    lstm_predictor.plot_prediction(y_test, lstm_pred, "LSTM 预测 vs 实际值")

    # 3. 训练混合模型
    print("\n===== 训练混合模型 =====")
    hybrid_predictor = WMPricePredictor(input_shape=lstm_input_shape, learning_rate=0.001)
    hybrid_predictor.build_hybrid_model(fcnn_layers=[32], lstm_units=[32])
    hybrid_history = hybrid_predictor.train(
        'hybrid', X_train_lstm, y_train, X_val_lstm, y_val,
        batch_size=32, epochs=100
    )
    hybrid_predictor.plot_training_history(hybrid_history)
    hybrid_metrics, hybrid_pred = hybrid_predictor.evaluate('hybrid', X_test_lstm, y_test)
    hybrid_predictor.plot_prediction(y_test, hybrid_pred, "混合模型 预测 vs 实际值")

    # 比较各模型性能
    print("\n===== 模型性能比较 =====")
    print(f"FCNN  RMSE: {fcnn_metrics['RMSE']:.4f}, R²: {fcnn_metrics['R2']:.4f}")
    print(f"LSTM  RMSE: {lstm_metrics['RMSE']:.4f}, R²: {lstm_metrics['R2']:.4f}")
    print(f"混合模型 RMSE: {hybrid_metrics['RMSE']:.4f}, R²: {hybrid_metrics['R2']:.4f}")
