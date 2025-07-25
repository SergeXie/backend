import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import EarlyStopping

def train_wmclass_predictor(data, test_size=0.2, random_state=42, epochs=100):
    """
    使用深度学习模型训练wmclass预测器
    
    参数:
    data: DataFrame，包含特征列(col1-col8)和目标列(wmclass)
    test_size: 测试集比例，默认为0.2
    random_state: 随机种子，用于结果重现
    
    返回:
    model: 训练好的Keras模型
    scaler: 用于特征标准化的StandardScaler对象
    metrics: 包含模型评估指标的字典
    """
    # 检查数据是否包含必要的列
    required_columns = ['col1', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7', 'col8', 'wmclass']
    if not set(required_columns).issubset(data.columns):
        missing = set(required_columns) - set(data.columns)
        raise ValueError(f"数据缺少必要的列: {missing}")
    
    # 分离特征和目标变量
    X = data[['col1', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7', 'col8']].values
    y = data['wmclass'].values
    
    # 对目标变量进行编码（如果有多个类别）
    unique_classes = np.unique(y)
    num_classes = len(unique_classes)
    
    # 创建类别映射，处理可能的负数类别
    class_map = {cls: i for i, cls in enumerate(unique_classes)}
    y_encoded = np.array([class_map[cls] for cls in y])
    
    # 如果是多类分类，转换为one-hot编码
    if num_classes > 2:
        y_categorical = to_categorical(y_encoded)
        loss_function = 'categorical_crossentropy'
        final_activation = 'softmax'
    else:
        y_categorical = y_encoded
        loss_function = 'binary_crossentropy'
        final_activation = 'sigmoid'
    
    # 划分训练集和测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_categorical, test_size=test_size, random_state=random_state
    )
    
    # 特征标准化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 构建深度学习模型
    model = Sequential([
        Dense(64, activation='relu', input_shape=(8,)),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dropout(0.2),
        Dense(num_classes, activation=final_activation)
    ])
    
    # 编译模型
    model.compile(
        optimizer='adam',
        loss=loss_function,
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
    
    # 转换预测结果为类别
    if num_classes > 2:
        y_pred = np.argmax(y_pred_proba, axis=1)
        y_test_decoded = np.argmax(y_test, axis=1)
    else:
        y_pred = (y_pred_proba > 0.5).astype(int).flatten()
        y_test_decoded = y_test
    
    # 将编码的预测结果转换回原始类别
    inverse_class_map = {v: k for k, v in class_map.items()}
    y_pred_original = np.array([inverse_class_map[pred] for pred in y_pred])
    y_test_original = np.array([inverse_class_map[test] for test in y_test_decoded])
    
    # 计算评估指标
    accuracy = accuracy_score(y_test_original, y_pred_original)
    report = classification_report(y_test_original, y_pred_original, output_dict=True)
    
    metrics = {
        'accuracy': accuracy,
        'classification_report': report,
        'training_history': history.history
    }
    
    print(f"模型测试准确率: {accuracy:.4f}")
    print(classification_report(y_test_original, y_pred_original))
    
    return model, scaler, metrics, class_map

def predict_wmclass(model, scaler, new_data, class_map):
    """
    使用训练好的模型预测新数据的wmclass
    
    参数:
    model: 训练好的Keras模型
    scaler: 用于特征标准化的StandardScaler对象
    new_data: DataFrame或numpy数组，包含特征列(col1-col8)
    class_map: 类别映射字典
    
    返回:
    predictions: 预测的wmclass值数组
    """
    # 确保输入数据包含正确的特征
    if isinstance(new_data, pd.DataFrame):
        features = new_data[['col1', 'col2', 'col3', 'col4', 'col5', 'col6', 'col7', 'col8']].values
    else:
        # 假设输入是numpy数组，且顺序正确
        features = new_data
    
    # 标准化特征
    features_scaled = scaler.transform(features)
    
    # 预测
    predictions_proba = model.predict(features_scaled)
    
    # 转换为类别
    num_classes = len(class_map)
    if num_classes > 2:
        predictions_encoded = np.argmax(predictions_proba, axis=1)
    else:
        predictions_encoded = (predictions_proba > 0.5).astype(int).flatten()
    
    # 转换回原始类别
    inverse_class_map = {v: k for k, v in class_map.items()}
    predictions = np.array([inverse_class_map[pred] for pred in predictions_encoded])
    
    return predictions

# 使用示例
if __name__ == "__main__":
    # 假设data是包含所有数据的DataFrame
    # 这里仅为示例，实际使用时替换为你的数据
    # data = pd.read_csv("your_data.csv")
    
    # 训练模型
    # model, scaler, metrics, class_map = train_wmclass_predictor(data)
    
    # 使用模型进行预测
    # 假设new_samples是包含新样本的DataFrame或numpy数组
    # predictions = predict_wmclass(model, scaler, new_samples, class_map)
    # print("预测结果:", predictions)
    pass
