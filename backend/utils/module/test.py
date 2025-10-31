import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.utils import shuffle


def preprocess_wm_data(all_wm_pattern,
                       test_size=0.1,
                       val_size=0.2,
                       random_state=42,
                       use_kline_context=False):
    """
    处理W形态数据的完整预处理函数：从原始样本列表到模型可输入的训练/验证/测试集。

    参数说明：
    ----------
    all_wm_pattern : list
        包含多个W形态样本的列表，每个样本为字典（同你提供的单个W形态数据结构）。
    test_size : float, 0~1
        测试集占总样本的比例（默认0.1，即10%）。
    val_size : float, 0~1
        验证集占“训练+验证”集的比例（默认0.2，即20%）。
    random_state : int
        随机种子（保证结果可复现）。
    use_kline_context : bool
        是否使用target_klines的上下文特征（默认False，若为True需保证样本有完整target_klines）。

    返回值：
    ----------
    tuple
        (X_train_scaled, X_val_scaled, X_test_scaled,  # 标准化后的特征
         y_train, y_val, y_test,                      # 标签（第5个点的price）
         scaler)                                      # 标准化器（用于后续预测时的特征转换）
    """

    # -------------------------- 1. 数据清洗：筛选有效样本 --------------------------
    valid_samples = []
    for idx, sample in enumerate(all_wm_pattern):
        # 检查1：样本必须包含完整的points数组（5个特征点）
        if "points" not in sample or len(sample["points"]) != 5:
            print(f"样本{idx}：points数组缺失或长度≠5，已剔除")
            continue

        # 检查2：每个point必须包含kline_data及核心价格字段
        valid_point = True
        for p_idx, point in enumerate(sample["points"]):
            required_keys = ["timestamp", "kline_data"]
            kline_required = ["price", "hloc"]
            if not all(k in point for k in required_keys):
                valid_point = False
                break
            if not all(k in point["kline_data"] for k in kline_required):
                valid_point = False
                break
        if not valid_point:
            print(f"样本{idx}：points包含无效字段，已剔除")
            continue

        # 检查3：若使用上下文特征，需保证target_klines存在
        if use_kline_context and "target_klines" not in sample:
            print(f"样本{idx}：use_kline_context=True但无target_klines，已剔除")
            continue

        # 保留有效样本
        valid_samples.append(sample)

    if len(valid_samples) == 0:
        raise ValueError("无有效样本！请检查all_wm_pattern的结构是否正确。")
    print(f"原始样本数：{len(all_wm_pattern)}，有效样本数：{len(valid_samples)}")

    # -------------------------- 2. 特征工程：从前4个点提取特征 --------------------------
    # 初始化特征列表和标签列表
    features_list = []
    labels = []

    for sample in valid_samples:
        # 提取前4个点（P0-P3）和第5个点（P4，作为标签）
        points = sample["points"]
        p0, p1, p2, p3 = points[0], points[1], points[2], points[3]
        p4_price = points[4]["kline_data"]["price"]  # 标签：第5个点的price
        labels.append(p4_price)

        # 特征字典：存储当前样本的所有特征
        feat = {}

        # ---------------- 2.1 绝对价格特征：P0-P3的price和hloc四价 ----------------
        for i, p in enumerate([p0, p1, p2, p3]):
            kd = p["kline_data"]
            feat[f"p{i}_price"] = kd["price"]
            feat[f"p{i}_high"] = kd["hloc"][0]  # hloc[0] = high
            feat[f"p{i}_low"] = kd["hloc"][1]  # hloc[1] = low
            feat[f"p{i}_close"] = kd["hloc"][2]  # hloc[2] = close
            feat[f"p{i}_open"] = kd["hloc"][3]  # hloc[3] = open

        # ---------------- 2.2 价格波动特征：P0-P3的振幅、涨跌幅 ----------------
        for i, p in enumerate([p0, p1, p2, p3]):
            kd = p["kline_data"]
            high, low, close, open_ = kd["hloc"]
            feat[f"p{i}_amplitude"] = high - low  # 振幅 = 最高价 - 最低价
            if open_ != 0:  # 避免除零
                feat[f"p{i}_return"] = (close - open_) / open_  # 涨跌幅 = (收盘价-开盘价)/开盘价
            else:
                feat[f"p{i}_return"] = 0

        # ---------------- 2.3 相对关系特征：P0-P3的点间价差、比率 ----------------
        # 点间绝对价差（P1-P0, P2-P1, P3-P2）
        feat["p1-p0_price_diff"] = p1["kline_data"]["price"] - p0["kline_data"]["price"]
        feat["p2-p1_price_diff"] = p2["kline_data"]["price"] - p1["kline_data"]["price"]
        feat["p3-p2_price_diff"] = p3["kline_data"]["price"] - p2["kline_data"]["price"]

        # 点间价差比率（反映趋势变化）
        diff_p0p1 = feat["p1-p0_price_diff"]
        diff_p1p2 = feat["p2-p1_price_diff"]
        diff_p2p3 = feat["p3-p2_price_diff"]
        feat["p2-p1/p1-p0_ratio"] = diff_p1p2 / (diff_p0p1 if diff_p0p1 != 0 else 1)
        feat["p3-p2/p2-p1_ratio"] = diff_p2p3 / (diff_p1p2 if diff_p1p2 != 0 else 1)

        # 相对基准价（以P0为基准，P1-P3的相对价格）
        feat["p1_rel_p0"] = p1["kline_data"]["price"] / p0["kline_data"]["price"]
        feat["p2_rel_p0"] = p2["kline_data"]["price"] / p0["kline_data"]["price"]
        feat["p3_rel_p0"] = p3["kline_data"]["price"] / p0["kline_data"]["price"]

        # ---------------- 2.4 时间特征：P0-P3的时间间隔（转换为小时） ----------------
        def timestamp_to_hours(ts_str):
            """将"YYYY-MM-DD HH:MM:SS"转换为时间戳（小时数，便于计算间隔）"""
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp() / 3600

        t0 = timestamp_to_hours(p0["timestamp"])
        t1 = timestamp_to_hours(p1["timestamp"])
        t2 = timestamp_to_hours(p2["timestamp"])
        t3 = timestamp_to_hours(p3["timestamp"])
        feat["t1-t0_hours"] = t1 - t0
        feat["t2-t1_hours"] = t2 - t1
        feat["t3-t2_hours"] = t3 - t2

        # ---------------- 2.5 可选：target_klines上下文特征（增强泛化性） ----------------
        if use_kline_context:
            target_klines = sample["target_klines"]
            # 以P0对应的K线为中心，取前后各1根K线的均价（共3根）
            p0_kline_id = p0["kline_data"]["kLineId"]
            # 找到P0在target_klines中的索引
            p0_kline_idx = None
            for k_idx, kline in enumerate(target_klines):
                if kline["kLineId"] == p0_kline_id:
                    p0_kline_idx = k_idx
                    break
            if p0_kline_idx is not None:
                # 取前后1根K线（避免越界）
                start_idx = max(0, p0_kline_idx - 1)
                end_idx = min(len(target_klines) - 1, p0_kline_idx + 1)
                context_klines = target_klines[start_idx:end_idx + 1]
                # 计算上下文K线的均价（open+high+low+close)/4
                context_avg = np.mean([(k["open"] + k["high"] + k["low"] + k["close"]) / 4
                                       for k in context_klines])
                feat["p0_context_avg"] = context_avg
            else:
                feat["p0_context_avg"] = 0

        # 将当前样本的特征加入列表
        features_list.append(feat)

    # 转换为DataFrame（便于后续处理）
    features_df = pd.DataFrame(features_list)
    labels_series = pd.Series(labels, name="p4_price")

    # -------------------------- 3. 异常值处理：剔除极端异常值 --------------------------
    # 基于价格标签的3σ原则剔除异常样本（避免极端值影响训练）
    mean_y = labels_series.mean()
    std_y = labels_series.std()
    upper_bound = mean_y + 3 * std_y
    lower_bound = mean_y - 3 * std_y
    # 筛选标签在[lower_bound, upper_bound]内的样本
    normal_mask = (labels_series >= lower_bound) & (labels_series <= upper_bound)
    features_df = features_df[normal_mask].reset_index(drop=True)
    labels_series = labels_series[normal_mask].reset_index(drop=True)
    print(f"剔除异常值后样本数：{len(features_df)}")

    # -------------------------- 4. 数据划分：训练集+验证集+测试集 --------------------------
    # 第一步：划分训练+验证集 与 测试集
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        features_df, labels_series, test_size=test_size, random_state=random_state, shuffle=True
    )
    # 第二步：划分训练集与验证集
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=val_size / (1 - test_size),  # 按比例调整
        random_state=random_state, shuffle=True
    )
    print(f"数据划分完成：训练集{len(X_train)}个，验证集{len(X_val)}个，测试集{len(X_test)}个")

    # -------------------------- 5. 特征标准化：消除量级影响 --------------------------
    # 使用StandardScaler（Z-Score标准化：(x-mean)/std）
    scaler = StandardScaler()
    # 仅用训练集拟合标准化器（避免数据泄露）
    X_train_scaled = scaler.fit_transform(X_train)
    # 用训练集的均值和标准差转换验证集和测试集
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)

    # -------------------------- 6. 返回预处理结果 --------------------------
    return (X_train_scaled, X_val_scaled, X_test_scaled,
            y_train.values, y_val.values, y_test.values,
            scaler)