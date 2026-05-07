import numpy as np
import pandas as pd
from scipy.spatial.distance import euclidean


def df_to_sequence(df: pd.DataFrame):
    """将DataFrame转为特征向量序列"""
    return df[['open', 'high', 'low', 'close']].values.tolist()


def dtw_distance(seq1, seq2):
    """计算DTW距离，递归实现"""
    len_seq1 = len(seq1)
    len_seq2 = len(seq2)

    # 创建距离矩阵，初始化为正无穷
    D = np.inf * np.ones((len_seq1, len_seq2))
    D[0, 0] = euclidean(seq1[0], seq2[0])

    # 填充矩阵 D
    for i in range(1, len_seq1):
        D[i, 0] = euclidean(seq1[i], seq2[0]) + D[i - 1, 0]
    for j in range(1, len_seq2):
        D[0, j] = euclidean(seq1[0], seq2[j]) + D[0, j - 1]

    for i in range(1, len_seq1):
        for j in range(1, len_seq2):
            D[i, j] = euclidean(seq1[i], seq2[j]) + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])

    return D[len_seq1 - 1, len_seq2 - 1]


def fast_dtw(seq1, seq2, radius=1):
    """FastDTW算法，分治实现"""
    len_seq1 = len(seq1)
    len_seq2 = len(seq2)

    # 如果序列的长度小于一定阈值，使用传统的DTW
    if len_seq1 <= radius + 1 or len_seq2 <= radius + 1:
        return dtw_distance(seq1, seq2)

    # 计算窗口范围
    window = min(radius, abs(len_seq1 - len_seq2))

    # 缩小序列，按比例缩小窗口范围
    seq1_resampled = seq1[::2]
    seq2_resampled = seq2[::2]

    # 递归调用
    return fast_dtw(seq1_resampled, seq2_resampled, radius)


def calc_dtw_distance(df1: pd.DataFrame, df2: pd.DataFrame):
    """计算两个DataFrame的DTW距离"""
    seq1 = df_to_sequence(df1)
    seq2 = df_to_sequence(df2)
    return int(fast_dtw(seq1, seq2))  # flost转为int


# # ===================== 测试 =====================
# df1 = pd.DataFrame({
#     "open": [2022.80, 2022.95, 2023.10, 2023.97, 2024.19,0],
#     "high": [2023.20, 2023.12, 2024.10, 2024.70, 2024.42,0],
#     "low": [2022.52, 2022.61, 2022.58, 2023.82, 2023.77,0],
#     "close": [2022.98, 2023.11, 2023.97, 2024.18, 2023.88,0],
# })
#
# df2 = pd.DataFrame({
#     "open": [2019.46, 2019.55, 2020.26, 2020.77, 2020.92],
#     "high": [2019.85, 2020.27, 2021.15, 2021.64, 2021.09],
#     "low": [2019.25, 2019.50, 2020.26, 2020.57, 2020.45],
#     "close": [2019.58, 2020.27, 2020.76, 2020.91, 2020.89],
# })
#
# dist = calc_dtw_distance(df1, df2)
# print("DTW 距离:", dist)
