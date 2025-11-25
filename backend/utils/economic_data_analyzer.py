from typing import Literal, Tuple

# 定义市场反应的五种等级
# 定义评分结果的描述
ScoreDescription = Literal['爆冷 (Massive Miss) / 强空', '差于预期 (Worse than Expected) / 弱空', '持平 (In Line) / 中性', '强于预期 (Better than Expected) / 弱多', '爆好 (Massive Beat) / 强多']

StrengthRating = Literal['强多 (Strong Bullish)', '强空 (Strong Bearish)', '一般 (Moderate/Neutral)']

class EconomicDataAnalyzer:

    def __init__(self):
        pass

    @classmethod
    def calculate_impact_score(
            cls,
            prior: float,  # 前值 (上一次的报告值)
            forecast: float,  # 预期值 (市场普遍预测值)
            actual: float  # 实际值 (本次报告的实际值)
    ) -> Tuple[float, ScoreDescription]:
        """
        计算经济数据（如失业人数，越低越好）的市场影响数值评分（-10 到 +10）。
        同时返回对应的描述。

        评分机制融合了偏差率和前值对比。

        参数:
        - prior (float): 前值
        - forecast (float): 预期值
        - actual (float): 实际值

        返回:
        - Tuple[float, ScoreDescription]: 评分数值和对应的描述。
        """

        # --- 1. 定义判断参数 ---

        # 偏差率阈值 (百分比，用于区分强弱)
        MAJOR_DEVIATION_PCT = 0.03  # 3% 的偏差视为“爆”级
        MINOR_DEVIATION_PCT = 0.005  # 0.5% 的偏差视为“弱”级

        # 基础分数 (基于偏差率)
        if forecast == 0:
            # 避免除零，如果预期为0，且实际不为0，直接给极端分数
            deviation_pct = (actual - forecast) * 10
        else:
            deviation_pct = (actual - forecast) / abs(forecast)

        # 将偏差率映射到 -8 到 +8 的分数区间
        # 偏差率每 1% 转换为约 1.5 分 (可调)
        score = - (deviation_pct * 150)  # 乘以负号，因为失业人数是越低越好 (负偏差->正分)
        score = max(-8.0, min(8.0, score))  # 将分数限制在 [-8, 8]

        # --- 2. 强弱修正 (基于前值) ---
        # 如果 Actual 突破了 Prior，则给予额外的奖励/惩罚，使分数达到 [-10, 10]

        # 强多修正：实际值低于预期 AND 实际值低于前值
        if actual < forecast and actual < prior:
            score += 2.0  # 给予强多奖励

        # 强空修正：实际值高于预期 AND 实际值高于前值
        elif actual > forecast and actual > prior:
            score -= 2.0  # 给予强空惩罚

        # 确保最终分数在 [-10, 10] 之间
        final_score = max(-10.0, min(10.0, score))

        # --- 3. 确定描述 (基于最终分数) ---

        if final_score >= 7.5:
            description: ScoreDescription = '爆好 (Massive Beat) / 强多'
        elif final_score >= 2.5:
            description = '强于预期 (Better than Expected) / 弱多'
        elif final_score <= -7.5:
            description = '爆冷 (Massive Miss) / 强空'
        elif final_score <= -2.5:
            description = '差于预期 (Worse than Expected) / 弱空'
        else:
            description = '持平 (In Line) / 中性'

        return final_score, description

    @classmethod
    # 定义强弱等级
    def evaluate_strength(
            cls,
            prior: float,  # 前值 (上一次的报告值)
            forecast: float,  # 预期值 (市场普遍预测值)
            actual: float,  # 实际值 (本次报告的实际值)
            name: str = "指标"  # 可选：用于输出提示的指标名称
    ) -> StrengthRating:
        """
        根据失业人数/失业率等“越低越好”的指标数据，评估市场强弱。

        评估标准：
        1. 强多：实际值 < 预期值 AND 实际值 < 前值
        2. 强空：实际值 > 预期值 AND 实际值 > 前值
        3. 一般：其他所有情况

        参数:
        - prior (float): 前值
        - forecast (float): 预期值
        - actual (float): 实际值
        - name (str): 指标名称，用于日志输出

        返回:
        - StrengthRating: 市场强弱等级字符串。
        """

        print(f"\n--- 评估 {name} ---")
        print(f"前值 (Prior): {prior}, 预期 (Forecast): {forecast}, 实际 (Actual): {actual}")

        # --------------------------------------------------------
        # 1. 强多 (Strong Bullish) 评估
        # 实际值低于预期 AND 实际值低于前值 (双重利好)
        # --------------------------------------------------------
        if actual < forecast and actual < prior:
            print(f"判断依据: 实际 ({actual}) < 预期 ({forecast}) 且 实际 ({actual}) < 前值 ({prior})")
            return '强多 (Strong Bullish)'

        # --------------------------------------------------------
        # 2. 强空 (Strong Bearish) 评估
        # 实际值高于预期 AND 实际值高于前值 (双重利空)
        # --------------------------------------------------------
        elif actual > forecast and actual > prior:
            print(f"判断依据: 实际 ({actual}) > 预期 ({forecast}) 且 实际 ({actual}) > 前值 ({prior})")
            return '强空 (Strong Bearish)'

        # --------------------------------------------------------
        # 3. 一般 (Moderate/Neutral) 评估
        # --------------------------------------------------------
        else:
            print("判断依据: 未满足强多或强空的双重条件。")
            return '一般 (Moderate/Neutral)'