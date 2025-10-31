import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping


def train_binary_classifier(data, positive_class, test_size=0.2, random_state=42, epochs=100):
    """
    训练二分类模型，区分positive_class和0

    参数:
    data: DataFrame，包含特征列(col1-col12)和目标列(wmclass)
    positive_class: 正类，应为-1或1
    test_size: 测试集比例，默认为0.2
    random_state: 随机种子，用于结果重现

    返回:
    model: 训练好的Keras模型
    scaler: 用于特征标准化的StandardScaler对象
    metrics: 包含模型评估指标的字典
    """
    # 检查数据是否包含必要的列
    required_columns = ['col1', 'col2', 'col3', 'col4', 'col5',
                        'col6', 'col7', 'col8', 'col9', 'col10', 'col11', 'col12', 'wmclass']
    if not set(required_columns).issubset(data.columns):
        missing = set(required_columns) - set(data.columns)
        raise ValueError(f"数据缺少必要的列: {missing}")

    # 筛选数据，只保留positive_class和0的样本
    filtered_data = data[data['wmclass'].isin([positive_class, 0])]

    # 分离特征和目标变量
    X = filtered_data[['col1', 'col2', 'col3', 'col4', 'col5', 'col6',
                       'col7', 'col8', 'col9', 'col10', 'col11', 'col12']].values

    # 目标变量编码：positive_class为1，0为0
    y = (filtered_data['wmclass'] == positive_class).astype(int).values

    # 划分训练集和测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )

    # 特征标准化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 构建二分类深度学习模型
    model = Sequential([
        Dense(64, activation='relu', input_shape=(12,)),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dropout(0.2),
        Dense(1, activation='sigmoid')  # 二分类使用sigmoid激活函数
    ])

    # 编译模型
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',  # 二分类使用binary_crossentropy损失函数
        metrics=['accuracy']
    )

    # 设置早停机制防止过拟合
    early_stopping = EarlyStopping(
        monitor='val_loss',
        patience=10,
        restore_best_weights=True
    )

    # 训练模型
    history = model.fit(
        X_train_scaled, y_train,
        epochs=epochs,
        batch_size=32,
        validation_split=0.1,
        callbacks=[early_stopping],
        verbose=1
    )

    # 在测试集上评估模型
    y_pred_proba = model.predict(X_test_scaled)
    y_pred = (y_pred_proba > 0.5).astype(int).flatten()  # 二分类阈值设为0.5

    # 转换回原始类别用于评估
    y_pred_original = np.where(y_pred == 1, positive_class, 0)
    y_test_original = np.where(y_test == 1, positive_class, 0)

    # 计算评估指标
    accuracy = accuracy_score(y_test_original, y_pred_original)
    report = classification_report(y_test_original, y_pred_original, output_dict=True)

    metrics = {
        'accuracy': accuracy,
        'classification_report': report,
        'training_history': history.history
    }

    print(f"模型(区分{positive_class}和0)测试准确率: {accuracy:.4f}")
    print(classification_report(y_test_original, y_pred_original))

    return model, scaler, metrics


def predict_binary(model, scaler, new_data, positive_class):
    """
    使用二分类模型预测新数据

    参数:
    model: 训练好的Keras模型
    scaler: 用于特征标准化的StandardScaler对象
    new_data: DataFrame或numpy数组，包含特征列(col1-col12)
    positive_class: 模型的正类，应为-1或1

    返回:
    predictions: 预测结果数组，值为positive_class或0
    probabilities: 预测为positive_class的概率数组
    """
    # 确保输入数据包含正确的特征
    if isinstance(new_data, pd.DataFrame):
        features = new_data[['col1', 'col2', 'col3', 'col4', 'col5',
                             'col6', 'col7', 'col8', 'col9', 'col10', 'col11', 'col12']].values
    else:
        # 假设输入是numpy数组，且顺序正确
        features = new_data

    # 标准化特征
    features_scaled = scaler.transform(features)

    # 预测概率
    probabilities = model.predict(features_scaled).flatten()

    # 转换为类别
    predictions = np.where(probabilities > 0.5, positive_class, 0)

    return predictions, probabilities


def train_two_classifiers(data, test_size=0.2, random_state=42, epochs=100):
    """
    训练两个二分类模型：一个区分-1和0，另一个区分1和0

    参数:
    data: DataFrame，包含特征列和目标列(wmclass)
    test_size: 测试集比例
    random_state: 随机种子
    epochs: 最大训练轮次

    返回:
    包含两个模型及相关信息的字典
    """
    # 训练区分-1和0的模型
    print("开始训练区分-1和0的模型...")
    model_neg, scaler_neg, metrics_neg = train_binary_classifier(
        data, -1, test_size, random_state, epochs
    )

    # 训练区分1和0的模型
    print("\n开始训练区分1和0的模型...")
    model_pos, scaler_pos, metrics_pos = train_binary_classifier(
        data, 1, test_size, random_state, epochs
    )

    return {
        'model_neg': model_neg,  # 区分-1和0的模型
        'scaler_neg': scaler_neg,  # 对应的数据标准化器
        'metrics_neg': metrics_neg,  # 模型评估指标
        'model_pos': model_pos,  # 区分1和0的模型
        'scaler_pos': scaler_pos,  # 对应的数据标准化器
        'metrics_pos': metrics_pos  # 模型评估指标
    }


# 使用示例
if __name__ == "__main__":
    # 假设data是包含所有数据的DataFrame
    # 这里仅为示例，实际使用时替换为你的数据
    # data = pd.read_csv("your_data.csv")

    # 生成示例数据用于测试
    np.random.seed(42)
    data_size = 1000
    data = pd.DataFrame({
        f'col{i}': np.random.randn(data_size) for i in range(1, 13)
    })
    # 随机生成-1, 0, 1的目标变量
    data['wmclass'] = np.random.choice([-1, 0, 1], size=data_size, p=[0.3, 0.4, 0.3])

    # 训练两个模型
    classifiers = train_two_classifiers(data)

    # 使用模型进行预测
    # 生成一些新样本
    new_samples = pd.DataFrame({
        f'col{i}': np.random.randn(10) for i in range(1, 13)
    })

    # 使用第一个模型预测(-1 vs 0)
    predictions_neg, probs_neg = predict_binary(
        classifiers['model_neg'],
        classifiers['scaler_neg'],
        new_samples,
        -1
    )

    # 使用第二个模型预测(1 vs 0)
    predictions_pos, probs_pos = predict_binary(
        classifiers['model_pos'],
        classifiers['scaler_pos'],
        new_samples,
        1
    )

    print("\n预测结果(-1 vs 0):", predictions_neg)
    print("预测概率(-1的概率):", [f"{p:.4f}" for p in probs_neg])

    print("\n预测结果(1 vs 0):", predictions_pos)
    print("预测概率(1的概率):", [f"{p:.4f}" for p in probs_pos])
