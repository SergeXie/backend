from datetime import datetime


def calculate_consecutive_win_loss(account_list):
    consecutive_wins = 0
    consecutive_losses = 0
    win_count = 0
    loss_count = 0
    max_consecutive_wins = 0
    max_consecutive_losses = 0

    for trade in account_list:
        if trade["closeTime"]:
            if trade['pnl'] > 0:
                win_count += 1
                consecutive_wins += 1
                max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
                consecutive_losses = 0  # Reset consecutive losses
            elif trade['pnl'] < 0:
                loss_count += 1
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                consecutive_wins = 0  # Reset consecutive wins

    average_consecutive_wins = consecutive_wins / win_count if win_count > 0 else 0
    average_consecutive_losses = consecutive_losses / loss_count if loss_count > 0 else 0

    return {
        'averageConsecutiveWins': round(average_consecutive_wins, 2),
        'averageConsecutiveLosses': round(average_consecutive_losses, 2),
    }


# 计算 yieldRate, winRate, avgProfit
def calculate_trade_metrics(account_list, initial_cash):
    total_profit = sum(trade['pnl'] for trade in account_list if trade["closeTime"])
    total_trades = len(account_list)
    win_trades = len([trade for trade in account_list if trade['pnl'] > 0 and trade["closeTime"]])

    yield_rate = (total_profit / initial_cash) * 100 if initial_cash else 0
    win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
    avg_profit = total_profit / total_trades if total_trades > 0 else 0

    return {
        'yieldRate': round(yield_rate, 2),
        'winRate': round(win_rate, 2),
        'avgProfit': round(avg_profit, 2)
    }


# 计算 plr (盈亏比)
def calculate_plr(account_list):
    positive_pnl = [trade['pnl'] for trade in account_list if trade['pnl'] > 0 and trade["closeTime"]]
    negative_pnl = [trade['pnl'] for trade in account_list if trade['pnl'] < 0 and trade["closeTime"]]

    avg_profit = sum(positive_pnl) / len(positive_pnl) if positive_pnl else 0
    avg_loss = abs(sum(negative_pnl) / len(negative_pnl)) if negative_pnl else 0

    plr = avg_profit / avg_loss if avg_loss > 0 else 0

    return round(plr, 2)


# 计算最大回撤率 (mdr)
def calculate_mdr(account_list, initial_cash):
    max_drawdown = 0
    peak_value = initial_cash
    for trade in account_list:
        if trade["closeTime"]:
            peak_value = max(peak_value, peak_value + trade['pnl'])
            drawdown = (peak_value - (initial_cash + trade['pnl'])) / peak_value
            max_drawdown = max(max_drawdown, drawdown)

    return round(max_drawdown, 2)


# 计算最大资金使用率 (maxFUR)
def calculate_max_fur(account_list):
    max_fur = 0
    for trade in account_list:
        if trade["closeTime"]:
            # 假设 'size' 表示交易量, openPrice 表示开盘价格, closePrice 表示平仓价格
            margin_used = abs(trade['size'] * (trade['openPrice'] - trade['price']))
            max_fur = max(max_fur, margin_used)

    return round(max_fur, 2)


def calculate_additional_metrics(account_list):
    # 交易单数
    trade_count = len(account_list)

    # 盈亏
    total_pnl = sum(trade['pnl'] for trade in account_list if trade["closeTime"])

    # 最大每手盈利
    max_profit = max(trade['pnl'] for trade in account_list if trade["closeTime"]) if account_list else 0

    # 最大每手亏损
    max_loss = min(trade['pnl'] for trade in account_list if trade["closeTime"]) if account_list else 0

    return {
        "tradeCount": trade_count,
        "pnl": total_pnl,
        "maxProfit": max_profit,
        "maxLoss": max_loss
    }


def calculate_metrics(account_list):
    """
    计算多头、空头和全部交易的指标。
    """
    # 根据方向分类交易记录
    long_trades = [trade for trade in account_list if trade.get('orderType') == 'buy']
    short_trades = [trade for trade in account_list if trade.get('orderType') == 'sell']

    # 计算指标
    overall_metrics = calculate_single_metrics(account_list)
    long_metrics = calculate_single_metrics(long_trades)
    short_metrics = calculate_single_metrics(short_trades)

    # 构建最终结果
    new_report_template = {
        "long": long_metrics,  # 多头指标
        "overall": overall_metrics,  # 全部交易指标
        "short": short_metrics  # 空头指标
    }

    return new_report_template


def calculate_single_metrics(account_list):
    # 初始化结果字典
    metrics = {
        "totalPnl": 0,
        "grossProfit": 0,
        "grossLoss": 0,
        "profitLossRatio": 0,
        "countTotal": 0,
        "profitRatio": 0,
        "countWon": 0,
        "countLost": 0,
        "avgProfitRatio": 0,
        "avgWon": 0,
        "avgLost": 0,
        "avgProfitLossRatio": 0,
        "maxPnl": 0,
        "maxLost": 0,
        "maxProfitRatio": 0,
        "maxLossRatio": 0,
        "netProfitLossRatio": 0,
        "maxConsecutiveWins": 0,
        "maxConsecutiveLosses": 0,
        "avgLoldingPeriod": 0,
        "avgProfitPeriod": 0,
        "avgLossPeriod": 0,
        "avgBreakevenPeriod": 0,
        "maxEquity": 0,
        "maxPositionSize": 0,
        "totalCosts": 0,
        "analysis": 0,
        "annualizedReturn": 0,  # 年化收益率
        "EffectiveYield": 0,  # 年化收益率
        "AverageProfitMonth": 0,  # 月度平均盈利
    }

    if not account_list:
        return metrics  # 如果没有交易记录，直接返回默认值

    # 基础数据计算
    total_pnl = sum(trade['pnl'] for trade in account_list)
    gross_profit = sum(trade['pnl'] for trade in account_list if trade['pnl'] > 0)
    gross_loss = round(abs(sum(trade['pnl'] for trade in account_list if trade['pnl'] < 0)), 2)
    count_total = len(account_list)
    count_won = len([trade for trade in account_list if trade['pnl'] > 0])
    count_lost = len([trade for trade in account_list if trade['pnl'] < 0])
    max_pnl = max((trade['pnl'] for trade in account_list), default=0)
    max_lost = min((trade['pnl'] for trade in account_list), default=0)
    total_costs = sum(trade.get('commission', 0) + trade.get('swap', 0) for trade in account_list)

    # 利润相关计算
    avg_won = gross_profit / count_won if count_won > 0 else 0
    avg_lost = gross_loss / count_lost if count_lost > 0 else 0
    avg_profit_ratio = total_pnl / count_total if count_total > 0 else 0
    avg_profit_loss_ratio = avg_won / avg_lost if avg_lost > 0 else 0
    profit_ratio = (count_won / count_total) * 100 if count_total > 0 else 0

    # 比率相关
    profit_loss_ratio = round(gross_profit / gross_loss if gross_loss > 0 else 0, 2)
    max_profit_ratio = round(max_pnl / gross_profit if gross_profit > 0 else 0, 2)
    max_loss_ratio = abs(max_lost) / gross_loss if gross_loss > 0 else 0
    net_profit_loss_ratio = total_pnl / abs(max_lost) if max_lost < 0 else 0

    # 连续交易相关
    consecutive_metrics = calculate_consecutive_win_loss_two(account_list)
    max_consecutive_wins = consecutive_metrics['maxConsecutiveWins']
    max_consecutive_losses = consecutive_metrics['maxConsecutiveLosses']

    # 时间相关
    avg_holding_period, avg_profit_period, avg_loss_period, avg_breakeven_period = calculate_periods(account_list)

    # 持仓相关
    max_equity = max(trade.get('equity', 0) for trade in account_list)
    max_position_size = max(trade.get('size', 0) for trade in account_list)

    # 汇总到结果字典
    metrics.update({
        "totalPnl": total_pnl,
        "grossProfit": gross_profit,
        "grossLoss": gross_loss,
        "profitLossRatio": profit_loss_ratio,
        "countTotal": count_total,
        "profitRatio": round(profit_ratio, 2),
        "countWon": count_won,
        "countLost": count_lost,
        "avgProfitRatio": round(avg_profit_ratio),
        "avgWon": round(avg_won, 2),
        "avgLost": avg_lost,
        "avgProfitLossRatio": round(avg_profit_loss_ratio, 2),
        "maxPnl": max_pnl,
        "maxLost": max_lost,
        "maxProfitRatio": max_profit_ratio,
        "maxLossRatio": round(max_loss_ratio, 2),
        "netProfitLossRatio": round(net_profit_loss_ratio, 2),
        "maxConsecutiveWins": max_consecutive_wins,
        "maxConsecutiveLosses": max_consecutive_losses,
        "avgLoldingPeriod": round(avg_holding_period, 2),
        "avgProfitPeriod": round(avg_profit_period, 2),
        "avgLossPeriod": round(avg_loss_period, 2),
        "avgBreakevenPeriod": round(avg_breakeven_period, 2),
        "maxEquity": max_equity,
        "maxPositionSize": max_position_size,
        "totalCosts": total_costs,
        "analysis": total_pnl / max_equity * 100 if max_equity > 0 else 0
    })

    return metrics


# 辅助函数：计算连续交易指标
def calculate_consecutive_win_loss_two(account_list):
    consecutive_wins = 0
    consecutive_losses = 0
    max_consecutive_wins = 0
    max_consecutive_losses = 0

    for trade in account_list:
        if trade['pnl'] > 0:
            consecutive_wins += 1
            max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            consecutive_losses = 0
        elif trade['pnl'] < 0:
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            consecutive_wins = 0

    return {
        "maxConsecutiveWins": max_consecutive_wins,
        "maxConsecutiveLosses": max_consecutive_losses
    }


# 辅助函数：计算周期相关指标
def calculate_periods(account_list):
    holding_periods = []
    profit_periods = []
    loss_periods = []
    breakeven_periods = []

    for trade in account_list:
        open_time = trade.get('openTime')
        close_time = trade.get('closeTime')
        if open_time and close_time:
            open_time = datetime.strptime(open_time, '%Y-%m-%d %H:%M:%S')
            close_time = datetime.strptime(close_time, '%Y-%m-%d %H:%M:%S')
            holding_period = (close_time - open_time).total_seconds() / 3600  # 转换为小时
            holding_periods.append(holding_period)

            if trade['pnl'] > 0:
                profit_periods.append(holding_period)
            elif trade['pnl'] < 0:
                loss_periods.append(holding_period)
            else:
                breakeven_periods.append(holding_period)

    avg_holding_period = sum(holding_periods) / len(holding_periods) if holding_periods else 0
    avg_profit_period = sum(profit_periods) / len(profit_periods) if profit_periods else 0
    avg_loss_period = sum(loss_periods) / len(loss_periods) if loss_periods else 0
    avg_breakeven_period = sum(breakeven_periods) / len(breakeven_periods) if breakeven_periods else 0

    return avg_holding_period, avg_profit_period, avg_loss_period, avg_breakeven_period
