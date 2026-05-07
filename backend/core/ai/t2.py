# ------------------------------------------------------------------------------
# 1. 从all_wm_pattern中提取并预处理数据
from typing import List, Dict, Tuple
import numpy as np


def extract_data_to_statusclass(all_wm_pattern: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
    """
    从all_wm_pattern列表中提取特征和标签：
    - 特征：前4个点位范围内的K线数据(去除成交量) + 前4个点位的相对价格特征(去除p4自身偏差)
    - 标签：第5个点位是否达到1/2/3倍价差（Δ = 第4点price - 第3点price）
    已去除第5维(成交量)和第9维(p4自身偏差)特征
    """
    X_list = []  # 存储所有样本的特征
    y_list = []  # 存储所有样本的标签

    for wm_dict in all_wm_pattern:
        # --------------------------
        # 步骤1：提取当前W形态的关键数据
        # --------------------------
        # 提取5个关键点位的price（points[0]到points[4]）
        points = wm_dict["points"]

        # 前4点和第5点的price
        p1 = points[0]["kline_data"]["price"]
        p2 = points[1]["kline_data"]["price"]
        p3 = points[2]["kline_data"]["price"]
        p4 = points[3]["kline_data"]["price"]
        p5 = points[4]["kline_data"]["price"]  # 用于构建标签

        # 计算价差Δ和绝对值
        delta = p4 - p3
        abs_delta = np.abs(delta)

        # 提取前4点范围内的K线数据（target_klines）
        target_klines = wm_dict["target_klines"]


        # --------------------------
        # 步骤2：构建K线序列特征（去除成交量特征）
        # --------------------------
        seq_len = len(target_klines)  # 每个样本的K线数量
        seq_len = 200
        # 每根K线的4个特征：open, high, low, close（已去除volume）
        kline_feat = np.zeros((seq_len, 4))

        for i, kline in enumerate(target_klines):
            # 提取K线的基础特征（仅保留open, high, low, close）
            kline_feat[i, 0] = kline.get("open", 0.0)
            kline_feat[i, 1] = kline.get("high", 0.0)
            kline_feat[i, 2] = kline.get("low", 0.0)
            kline_feat[i, 3] = kline.get("close", 0.0)

        # --------------------------
        # 步骤3：特征归一化
        # --------------------------
        # 价格特征归一化：(x - p4) / abs_delta（与价差倍数关联）
        # 现在只有4个价格特征需要归一化（已去除成交量）
        norm_kline_feat = np.zeros_like(kline_feat)
        for i in range(4):  # 循环范围从4改为3（0-3）
            norm_kline_feat[:, i] = (kline_feat[:, i] - p4) / abs_delta

        # --------------------------
        # 步骤4：构建前4点相对特征（去除p4自身偏差）
        # --------------------------
        # 前3点相对于p4的价格偏差（已去除p4自身偏差）
        points_feat = np.array(
            [(p1 - p4) / abs_delta, (p2 - p4) / abs_delta, (p3 - p4) / abs_delta])
        # 扩展维度并重复，与K线序列特征对齐
        points_feat_repeat = np.tile(points_feat, (seq_len, 1))  # (seq_len, 3)

        # --------------------------
        # 步骤5：拼接最终特征
        # --------------------------
        # 最终特征：K线序列特征（4维） + 前3点相对特征（3维） → 7维
        final_feat = np.concatenate([norm_kline_feat, points_feat_repeat], axis=1)  # (seq_len, 7)
        X_list.append(final_feat)

        # --------------------------
        # 步骤6：构建标签（多标签分类）
        # --------------------------
        # 标签定义：[空，M，W]
        if "空" in wm_dict['pattern_type']:
            y1 = 1
            y2 = 0
            y3 = 0
        elif "M" in wm_dict['pattern_type']:
            y1 = 0
            y2 = 1
            y3 = 0
        else:
            y1 = 0
            y2 = 0
            y3 = 1
        # print(y1,y2)
        y_list.append([y1, y2, y3])

    # 转换为numpy数组（确保所有样本的K线长度一致）
    max_seq_len = max([x.shape[0] for x in X_list]) if X_list else 0
    # 特征维度变为7（4+3）
    X_processed = np.zeros((len(X_list), max_seq_len, 7))

    for i, x in enumerate(X_list):
        seq_len = x.shape[0]
        X_processed[i, :seq_len, :] = x  # 前seq_len填充真实数据，其余补0

    y_processed = np.array(y_list)  # (样本数, 3)

    # print(f"数据提取完成：共{len(X_processed)}个有效样本，每个样本{max_seq_len}根K线，7维特征")
    return X_processed, y_processed

def extract_data_to_diffclass(all_wm_pattern: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
    """
    从all_wm_pattern列表中提取特征和标签：
    - 特征：前4个点位范围内的K线数据(去除成交量) + 前4个点位的相对价格特征(去除p4自身偏差)
    - 标签：第5个点位是否达到1/2/3倍价差（Δ = 第4点price - 第3点price）
    已去除第5维(成交量)和第9维(p4自身偏差)特征
    """
    X_list = []  # 存储所有样本的特征
    y_list = []  # 存储所有样本的标签

    for wm_dict in all_wm_pattern:
        # --------------------------
        # 步骤1：提取当前W形态的关键数据
        # --------------------------
        # 提取5个关键点位的price（points[0]到points[4]）
        points = wm_dict["points"]
        if len(points) != 5:
            print(f"警告：当前W形态的points数量不是5个，跳过该样本")
            continue

        # 前4点和第5点的price
        p1 = points[0]["kline_data"]["price"]
        p2 = points[1]["kline_data"]["price"]
        p3 = points[2]["kline_data"]["price"]
        p4 = points[3]["kline_data"]["price"]
        p5 = points[4]["kline_data"]["price"]  # 用于构建标签

        # 计算价差Δ和绝对值
        delta = p4 - p3
        abs_delta = np.abs(delta)
        if abs_delta < 1e-6:  # 避免Δ为0导致除以0
            print(f"警告：当前W形态的Δ接近0，跳过该样本")
            continue

        # 提取前4点范围内的K线数据（target_klines）
        target_klines = wm_dict["target_klines"]
        if len(target_klines) == 0:
            print(f"警告：当前W形态的target_klines为空，跳过该样本")
            continue

        # --------------------------
        # 步骤2：构建K线序列特征（去除成交量特征）
        # --------------------------
        seq_len = len(target_klines)  # 每个样本的K线数量
        seq_len = 200
        # 每根K线的4个特征：open, high, low, close（已去除volume）
        kline_feat = np.zeros((seq_len, 4))

        for i, kline in enumerate(target_klines):
            # 提取K线的基础特征（仅保留open, high, low, close）
            kline_feat[i, 0] = kline.get("open", 0.0)
            kline_feat[i, 1] = kline.get("high", 0.0)
            kline_feat[i, 2] = kline.get("low", 0.0)
            kline_feat[i, 3] = kline.get("close", 0.0)

        # --------------------------
        # 步骤3：特征归一化
        # --------------------------
        # 价格特征归一化：(x - p4) / abs_delta（与价差倍数关联）
        # 现在只有4个价格特征需要归一化（已去除成交量）
        norm_kline_feat = np.zeros_like(kline_feat)
        for i in range(4):  # 循环范围从4改为3（0-3）
            norm_kline_feat[:, i] = (kline_feat[:, i] - p4) / abs_delta

        # --------------------------
        # 步骤4：构建前4点相对特征（去除p4自身偏差）
        # --------------------------
        # 前3点相对于p4的价格偏差（已去除p4自身偏差）
        points_feat = np.array(
            [(p1 - p4) / abs_delta, (p2 - p4) / abs_delta, (p3 - p4) / abs_delta])
        # 扩展维度并重复，与K线序列特征对齐
        points_feat_repeat = np.tile(points_feat, (seq_len, 1))  # (seq_len, 3)

        # --------------------------
        # 步骤5：拼接最终特征
        # --------------------------
        # 最终特征：K线序列特征（4维） + 前3点相对特征（3维） → 7维
        final_feat = np.concatenate([norm_kline_feat, points_feat_repeat], axis=1)  # (seq_len, 7)
        X_list.append(final_feat)

        # --------------------------
        # 步骤6：构建标签（多标签分类）
        # --------------------------
        # 标签定义：1=达到价差，0=未达到
        if "M" in wm_dict['pattern_type']:
            y1 = 1 if (p5 <= p4 - 1 * abs_delta) else 0  # 1倍价差
            y2 = 1 if (p5 <= p4 - 2 * abs_delta) else 0  # 2倍价差
            y3 = 1 if (p5 <= p4 - 3 * abs_delta) else 0  # 3倍价差
        elif "W" in wm_dict['pattern_type']:
            y1 = 1 if (p5 >= p4 + 1 * abs_delta) else 0
            y2 = 1 if (p5 >= p4 + 2 * abs_delta) else 0
            y3 = 1 if (p5 >= p4 + 3 * abs_delta) else 0
        else:
            y1, y2, y3 = 0, 0, 0
        if y3 == 1:
            y1, y2 = 0, 0
        if y2 == 1:
            y1 = 0
        y_list.append([y1, y2, y3])

    # 转换为numpy数组（确保所有样本的K线长度一致）
    max_seq_len = max([x.shape[0] for x in X_list]) if X_list else 0
    # 特征维度变为7（4+3）
    X_processed = np.zeros((len(X_list), max_seq_len, 7))

    for i, x in enumerate(X_list):
        seq_len = x.shape[0]
        X_processed[i, :seq_len, :] = x  # 前seq_len填充真实数据，其余补0

    y_processed = np.array(y_list)  # (样本数, 3)

    # print(f"数据提取完成：共{len(X_processed)}个有效样本，每个样本{max_seq_len}根K线，7维特征")
    return X_processed, y_processed

def extract_xdata(all_wm_pattern: List[Dict]):
    X_list = []  # 存储所有样本的特征

    for wm_dict in all_wm_pattern:
        # print(wm_dict)
        # --------------------------
        # 步骤1：提取当前W形态的关键数据
        # --------------------------
        points = wm_dict.points

        # 前4点和第5点的price
        p1 = points[0]["kline_data"].price
        p2 = points[1]["kline_data"].price
        p3 = points[2]["kline_data"].price
        p4 = points[3]["kline_data"].price

        # 计算价差Δ和绝对值
        delta = p4 - p3
        abs_delta = np.abs(delta)

        # 提取前4点范围内的K线数据（target_klines）
        target_klines = wm_dict.target_klines

        # --------------------------
        # 步骤2：构建K线序列特征（去除成交量特征）
        # --------------------------
        seq_len = len(target_klines)  # 每个样本的K线数量
        seq_len = 200
        # 每根K线的4个特征：open, high, low, close（已去除volume）
        kline_feat = np.zeros((seq_len, 4))

        for i, kline in enumerate(target_klines):
            # 提取K线的基础特征（仅保留open, high, low, close）
            kline_feat[i, 0] = kline.get("open", 0.0)
            kline_feat[i, 1] = kline.get("high", 0.0)
            kline_feat[i, 2] = kline.get("low", 0.0)
            kline_feat[i, 3] = kline.get("close", 0.0)

        # --------------------------
        # 步骤3：特征归一化
        # --------------------------
        # 价格特征归一化：(x - p4) / abs_delta（与价差倍数关联）
        # 现在只有4个价格特征需要归一化（已去除成交量）
        norm_kline_feat = np.zeros_like(kline_feat)
        for i in range(4):  # 循环范围从4改为3（0-3）
            norm_kline_feat[:, i] = (kline_feat[:, i] - p4) / abs_delta

        # --------------------------
        # 步骤4：构建前4点相对特征（去除p4自身偏差）
        # --------------------------
        # 前3点相对于p4的价格偏差（已去除p4自身偏差）
        points_feat = np.array(
            [(p1 - p4) / abs_delta, (p2 - p4) / abs_delta, (p3 - p4) / abs_delta])
        # 扩展维度并重复，与K线序列特征对齐
        points_feat_repeat = np.tile(points_feat, (seq_len, 1))  # (seq_len, 3)

        # --------------------------
        # 步骤5：拼接最终特征
        # --------------------------
        # 最终特征：K线序列特征（4维） + 前3点相对特征（3维） → 7维
        final_feat = np.concatenate([norm_kline_feat, points_feat_repeat], axis=1)  # (seq_len, 7)
        X_list.append(final_feat)



    # 转换为numpy数组（确保所有样本的K线长度一致）
    max_seq_len = max([x.shape[0] for x in X_list]) if X_list else 0
    # 特征维度变为7（4+3）
    X_processed = np.zeros((len(X_list), max_seq_len, 7))

    for i, x in enumerate(X_list):
        seq_len = x.shape[0]
        X_processed[i, :seq_len, :] = x  # 前seq_len填充真实数据，其余补0

    # print(f"数据提取完成：共{len(X_processed)}个有效样本，每个样本{max_seq_len}根K线，7维特征")
    return X_processed




# ------------------------------------------------------------------------------
# 3. 模拟all_wm_pattern数据（替换为你的真实数据）
# ------------------------------------------------------------------------------
# def simulate_all_wm_pattern(num_samples: int = 200) -> List[Dict]:
#     """
#     模拟all_wm_pattern列表（含多个W形态字典），真实场景中直接使用你的all_wm_pattern即可
#     """
#     np.random.seed(42)
#     all_wm = []
#
#     for _ in range(num_samples):
#         # 模拟5个关键点位
#         p1 = np.random.uniform(3400, 3500)
#         p2 = np.random.uniform(3100, 3200)
#         p3 = np.random.uniform(3300, 3400)
#         p4 = np.random.uniform(3250, 3300)
#         p5 = p4 + np.abs(p4 - p3) * np.random.uniform(0.5, 3.5)  # 第5点价格（随机达到0.5-3.5倍价差）
#
#         points = [
#             {"timestamp": f"2025-05-{np.random.randint(1, 10):02d} 21:00:00", "kline_data": {"price": p1}},
#             {"timestamp": f"2025-05-{np.random.randint(10, 18):02d} 09:00:00", "kline_data": {"price": p2}},
#             {"timestamp": f"2025-05-{np.random.randint(18, 23):02d} 05:00:00", "kline_data": {"price": p3}},
#             {"timestamp": f"2025-05-{np.random.randint(23, 25):02d} 17:00:00", "kline_data": {"price": p4}},
#             {"timestamp": f"2025-05-{np.random.randint(25, 31):02d} 21:00:00", "kline_data": {"price": p5}}
#         ]
#
#         # 模拟69根K线数据（open, high, low, close, volume）
#         seq_len = 69
#         target_klines = []
#         for i in range(seq_len):
#             base_price = p1 - (p1 - p2) * (i / 23) if i < 23 else (
#                 p2 + (p3 - p2) * ((i - 23) / 23) if i < 46 else p3 - (p3 - p4) * ((i - 46) / 23))
#             open_p = base_price + np.random.normal(0, 5)
#             close_p = base_price + np.random.normal(0, 5)
#             target_klines.append({
#                 "kLineId": 8827533.0 + i,
#                 "timestamp": f"2025-05-{np.random.randint(1, 31):02d} {np.random.choice([01, 05, 09, 13, 17, 21]):02d}:00:00",
#                 "open": open_p,
#                 "high": max(open_p, close_p) + np.random.normal(0, 8),
#                 "low": min(open_p, close_p) - np.random.normal(0, 8),
#                 "close": close_p,
#                 "volume": np.random.uniform(0, 1000)
#             })
#
#         # 构建单个W形态字典
#         wm_dict = {
#             "pattern_type": "W形态",
#             "points": points,
#             "start_timestamp": points[0]["timestamp"],
#             "end_timestamp": points[4]["timestamp"],
#             "target_klines": target_klines,
#             "period": "H4"
#         }
#         all_wm.append(wm_dict)
#
#     return all_wm


# ------------------------------------------------------------------------------
# 4. 主流程：加载数据→训练模型→推理预测
# ------------------------------------------------------------------------------
# if __name__ == "__main__":
#     # --------------------------
#     # 步骤1：准备数据（真实场景中直接使用你的all_wm_pattern）
#     # --------------------------
#     # 模拟200个W形态样本（替换为你的真实all_wm_pattern）
#     all_wm_pattern = simulate_all_wm_pattern(num_samples=200)
#
#     # 从all_wm_pattern中提取特征和标签
#     X, y = extract_data_from_all_wm_pattern(all_wm_pattern)
#     if len(X) == 0:
#         print("没有有效样本，程序终止")
#         exit()
#
#     # 划分训练集和测试集（8:2）
#     split_idx = int(0.8 * len(X))
#     X_train, X_test = X[:split_idx], X[split_idx:]
#     y_train, y_test = y[:split_idx], y[split_idx:]
#
#     # --------------------------
#     # 步骤2：构建并训练模型
#     # --------------------------
#     max_seq_len = X.shape[1]  # 所有样本的最大K线长度
#     model = build_lstm_model(max_seq_len=max_seq_len, feat_dim=9)
#     print("\n模型结构：")
#     model.summary()

    # 训练模型
    # print("\n开始训练模型...")
    # history = model.fit(
    #     X_train, y_train,
    #     batch_size=16,
    #     epochs=30,
    #     validation_data=(X_test, y_test),
    #     shuffle=True
    # )
    #
    # # 评估模型
    # test_loss, test_acc = model.evaluate(X_test, y_test)
    # print(f"\n测试集性能：损失={test_loss:.4f}, 准确率={test_acc:.4f}")
    #
    # # --------------------------
    # # 步骤3：推理预测（以测试集第一个样本为例）
    # # --------------------------
    # print("\n推理示例：")
    # # 取测试集第一个样本
    # sample_idx = 0
    # X_sample = X_test[sample_idx:sample_idx + 1]  # (1, max_seq_len, 9)
    # y_true = y_test[sample_idx]  # 真实标签
    #
    # # 预测概率
    # y_pred_prob = model.predict(X_sample, verbose=0)[0]  # (3,)
    #
    # # 打印结果
    # print(f"样本{sample_idx} - 真实标签：1倍价差={y_true[0]}, 2倍价差={y_true[1]}, 3倍价差={y_true[2]}")
    # print(
    #     f"样本{sample_idx} - 预测概率：1倍价差={y_pred_prob[0]:.4f}, 2倍价差={y_pred_prob[1]:.4f}, 3倍价差={y_pred_prob[2]:.4f}")