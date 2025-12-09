import backtrader as bt

import pandas as pd
from datetime import datetime


# ===================== 自定义指标：滤波RSI =====================
class FilteredRSI(bt.Indicator):

    # 4. 指标核心计算逻辑
    def __init__(self):
        # 步骤1：计算基础RSI（使用收盘价）
        rsi = btind.RSI(
            self.data.close,  # 数据源（收盘价）
            period=self.params.rsi_period  # RSI周期
        )

        # 步骤2：对RSI做EMA滤波（降低噪音）
        self.lines.filtered_rsi = btind.EMA(
            rsi,
            period=self.params.filter_period
        )

        # 可选：添加超买超卖标记（可视化用）
        self.overbought = self.params.overbought
        self.oversold = self.params.oversold


# ===================== 策略集成自定义指标 =====================
class RSIStrategy(bt.Strategy):
    """
    测试策略：基于滤波RSI的买卖信号
    - 滤波RSI < 30 且上穿30 → 买入
    - 滤波RSI > 70 且下穿70 → 卖出
    """
    params = (
        ('rsi_period', 14),
        ('filter_period', 3),
    )

    def __init__(self):
        # 初始化自定义指标
        self.filtered_rsi = FilteredRSI(
            self.data,
            rsi_period=self.params.rsi_period,
            filter_period=self.params.filter_period
        )

        # 定义交叉信号
        self.buy_signal = btind.CrossUp(self.filtered_rsi, self.filtered_rsi.oversold)
        self.sell_signal = btind.CrossDown(self.filtered_rsi, self.filtered_rsi.overbought)

        # 记录交易状态（避免重复买卖）
        self.order = None

    def next(self):
        """主逻辑：生成买卖信号"""
        if self.order:
            return

        # 无持仓且触发买入信号 → 买入
        if not self.position and self.buy_signal[0]:
            self.order = self.buy(size=100)  # 买入100股

        # 有持仓且触发卖出信号 → 卖出
        elif self.position and self.sell_signal[0]:
            self.order = self.sell(size=100)  # 卖出100股




# ===================== 回测运行 =====================
def run_backtest():
    # 1. 创建回测引擎
    cerebro = bt.Cerebro()
    # 2. 添加策略
    cerebro.addstrategy(RSIStrategy)
    # 4. 添加数据源到引擎
    cerebro.adddata(data)
    # 5. 设置初始资金
    cerebro.broker.setcash(100000.0)

    cerebro.run()




if __name__ == '__main__':
    run_backtest()