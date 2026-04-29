import json
import traceback
import pandas as pd
from dateutil import parser
from sqlalchemy import select
from common.log import log
from schemas.base import DqlStrategyTestResult, TradingStrategy
from common.common import format_datetime, to_float, match_filter_data, match_ratio, generate_random_string, \
    model_classes, fetch_indicators, select_goods_common, \
    calculate_trade_metrics, calculate_consecutive_win_loss, calculate_plr, calculate_mdr, calculate_max_fur
from datetime import datetime
from types import SimpleNamespace

def calculate_additional_metrics(account_list):
    # 交易单数
    trade_count = len(account_list)

    # 盈亏
    total_pnl = sum(trade['pnl'] for trade in account_list)

    # 最大每手盈利
    max_profit = max(trade['pnl'] for trade in account_list) if account_list else 0

    # 最大每手亏损
    max_loss = min(trade['pnl'] for trade in account_list) if account_list else 0

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
        "totalPnl": round(total_pnl, 2),
        "grossProfit": round(gross_profit, 2),
        "grossLoss": gross_loss,
        "profitLossRatio": profit_loss_ratio,
        "countTotal": count_total,
        "profitRatio": round(profit_ratio, 2),
        "countWon": count_won,
        "countLost": count_lost,
        "avgProfitRatio": round(avg_profit_ratio),
        "avgWon": round(avg_won, 2),
        "avgLost": round(avg_lost, 2),
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
        "totalCosts": round(total_costs, 2),
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


# 提取交易信息
def extract_transactions(section_header, stop_text):
    trades = []
    if section_header:
        row = section_header.find_next('tr', align='center').find_next_sibling('tr')
        while row:
            cols = row.find_all('td')
            if row.find('b', string=stop_text):
                break
            if len(cols) > 1:
                transaction = {
                    'tradeid': cols[0].text.strip() if len(cols) > 0 else 0,
                    'timestamp': format_datetime(cols[1].text.strip()) if len(cols) > 1 else None,
                    'openTime': format_datetime(cols[1].text.strip()) if len(cols) > 1 else None,
                    'orderType': cols[2].text.strip() if len(cols) > 2 else '0',
                    'goodsId': cols[4].text.strip() if len(cols) > 4 else None,
                    'size': to_float(cols[3].text.strip()) if len(cols) > 3 else 0.0,
                    'openPrice': to_float(cols[5].text.strip()) if len(cols) > 5 else 0.0,
                    'stopLoss': to_float(cols[6].text.strip()) if len(cols) > 6 else 0.0,
                    'takeProfit': to_float(cols[7].text.strip()) if len(cols) > 7 else 0.0,
                    'closeTime': format_datetime(cols[8].text.strip()) if len(cols) > 8 else None,
                    'price': to_float(cols[9].text.strip()) if len(cols) > 9 else 0.0,
                    'commission': to_float(cols[10].text.strip()) if len(cols) > 10 else 0.0,
                    'taxes': to_float(cols[11].text.strip()) if len(cols) > 11 else 0.0,
                    'swap': to_float(cols[12].text.strip()) if len(cols) > 12 else 0.0,
                    'pnl': to_float(cols[13].text.strip()) if len(cols) > 13 else 0.0,
                }
                trades.append(transaction)
            row = row.find_next_sibling('tr', align='right')
    return trades


def extract_order_prefixes(value_):
    """
    从 account_list 中提取 tradeid 和 goodsId 为空的数据的 orderType 的前缀（@ 之前部分），并去重。
    """
    if "@" in value_:
        # 提取 @ 之前的数据并加入 set
        prefix = value_.split("@")[0]

        return prefix


def normalize_to_float(value):
    if isinstance(value, str):
        # 去除空格并转换为浮点数
        return float(value.replace(" ", ""))
    return float(value)  # 如果已经是浮点数，则直接返回


def calculate_trading_indicator_statistics(soup, account_list):

    df = pd.DataFrame(account_list)
    # 进一步处理
    df["netProfit"] = df["pnl"] + df["swap"]
    df["isProfit"] = df["netProfit"] > 0
    df["isLoss"] = df["netProfit"] < 0
    df["orderType"] = df["orderType"].str.lower()

    # 计算连续盈利和连续亏损
    profits = df["netProfit"].tolist()
    consecutive_profits = []
    consecutive_losses = []
    current_profit = 0
    current_loss = 0
    consec_win = 0
    consec_loss = 0
    max_consec_win = 0
    max_consec_loss = 0

    for p in profits:
        if p > 0:
            current_profit += p
            consecutive_profits.append(current_profit)
            current_loss = 0
            consec_win += 1
            max_consec_win = max(max_consec_win, consec_win)
            consec_loss = 0
        elif p < 0:
            current_loss += p
            consecutive_losses.append(current_loss)
            current_profit = 0
            consec_loss += 1
            max_consec_loss = max(max_consec_loss, consec_loss)
            consec_win = 0
        else:
            current_profit = 0
            current_loss = 0
            consec_win = 0
            consec_loss = 0

    # 提取起始资金
    starting_cash_str = soup.find(string="Balance:").find_next().text
    starting_cash = float(starting_cash_str.replace(' ', ''))

    # 统计计算
    total_net_profit = df["netProfit"].sum()
    total_profit = df[df["netProfit"] > 0]["netProfit"].sum()
    total_loss = -df[df["netProfit"] < 0]["netProfit"].sum()
    absolute_drawdown = df["netProfit"].cumsum().min()
    maximal_drawdown = df["netProfit"].cumsum().cummax() - df["netProfit"].cumsum()
    max_drawdown = maximal_drawdown.max()

    profit_trades = df[df["isProfit"]]
    loss_trades = df[df["isLoss"]]
    average_profit_trade = round(profit_trades["netProfit"].mean(), 2) if not profit_trades.empty else 0
    average_loss_trade = round(loss_trades["netProfit"].mean(), 2) if not loss_trades.empty else 0
    largest_profit = round(df["netProfit"].max(), 2) if not df.empty else 0
    largest_loss = round(df["netProfit"].min(), 2) if not df.empty else 0
    profit_factor = total_profit / total_loss if total_loss != 0 else 0
    expected_payoff = total_net_profit / len(df) if len(df) > 0 else 0
    relative_loss = max_drawdown / starting_cash if starting_cash != 0 else 0

    trader_report = {
        "startingCash": starting_cash,
        "FreeMargin": round(starting_cash + total_net_profit, 2),
        "totalNetProfit": round(total_net_profit, 2),
        "totalProfit": round(total_profit, 2),
        "totalLoss": round(total_loss, 2),
        "ProfitFactor": round(profit_factor, 2),
        "expectedPayoff": round(expected_payoff, 2),
        "absoluteDrawdown": round(absolute_drawdown, 2),
        "maximalDrawdown": round(max_drawdown, 2),
        "relativeLosses": round(relative_loss, 4),
        "totalTrades": len(df),
        "shortPositions": int((df["orderType"] == "sell").sum()),
        "shortPositionsRatio": round((df["orderType"] == "sell").mean() * 100, 2) if not df.empty else 0,
        "longPositions": int((df["orderType"] == "buy").sum()),
        "longPositionsRatio": round((df["orderType"] == "buy").mean() * 100, 2) if not df.empty else 0,
        "profitTrades": int(df["isProfit"].sum()),
        "profitTradesRatio": round(df["isProfit"].mean() * 100, 2) if not df.empty else 0,
        "lossTrades": int(df["isLoss"].sum()),
        "lossTradesRatio": round(df["isLoss"].mean() * 100, 2) if not df.empty else 0,
        "largestProfit": largest_profit,
        "largestLoss": largest_loss,
        "averageProfitTrade": average_profit_trade,
        "averageLossTrade": average_loss_trade,
        "maximalConsecutiveProfit": round(max(consecutive_profits or [0]), 2),
        "maximalConsecutiveLoss": round(min(consecutive_losses or [0]), 2),
        "maximumConsecutiveWins": max_consec_win,
        "maximumConsecutiveLosses": max_consec_loss,
        "yieldRate": 0.0,
        "winRate": 0.0,
        "plr": 0.0,
        "avgProfit": 0.0,
        "mdr": 0.0,
        "isBursted": 0,
        "maxFUR": 0.0,
        "score": 0.0,
    }

    return trader_report


def generate_trader_report(soup, account_list):
    """
    生成交易报告
    """
    try:

        # 提取报告数据
        trader_report = calculate_trading_indicator_statistics(soup, account_list)
        # 计算所需的指标
        initial_cash = trader_report["startingCash"]
        consecutive_metrics = calculate_consecutive_win_loss(account_list)
        trade_metrics = calculate_trade_metrics(account_list, initial_cash)
        plr = calculate_plr(account_list)
        mdr = calculate_mdr(account_list, initial_cash)
        max_fur = calculate_max_fur(account_list)
        additional_metrics = calculate_additional_metrics(account_list)

        trader_report["startingCash"] = initial_cash
        trader_report["averageConsecutiveWins"] = consecutive_metrics["averageConsecutiveWins"]
        trader_report["averageConsecutiveLosses"] = consecutive_metrics["averageConsecutiveLosses"]
        trader_report["yieldRate"] = trade_metrics["yieldRate"]
        trader_report["winRate"] = trade_metrics["winRate"]
        trader_report["avgProfit"] = trade_metrics["avgProfit"]
        trader_report["plr"] = plr
        trader_report["ProfitFactor"] = plr
        trader_report["mdr"] = mdr
        trader_report["max_fur"] = max_fur
        trader_report["totalTrades"] = additional_metrics["tradeCount"]
        newReportTemplate = calculate_metrics(account_list)

        return trader_report, additional_metrics, newReportTemplate

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"解析报告出错：{info}")


def process_manual_generate_trader_report(soup, account_list):
    """
    生成交易报告
    """
    try:
        # 提取报告数据
        trader_report = {
            "startingCash": soup.find(string="Balance:").find_next().text,
            "FreeMargin": soup.find(string="Free Margin:").find_next().text,
            "totalNetProfit": soup.find(string="Total Net Profit:").find_next().text,
            "totalProfit": soup.find(string="Gross Profit:").find_next().text,
            "totalLoss": soup.find(string="Gross Loss:").find_next().text,
            "ProfitFactor": soup.find(string="Profit Factor:").find_next().text,
            "expectedPayoff": soup.find(string="Expected Payoff:").find_next().text,
            "absoluteDrawdown": soup.find(string="Absolute Drawdown:").find_next().text,
            "maximalDrawdown": match_filter_data(soup.find(string="Maximal Drawdown:").find_next().text),
            "relativeLosses": match_filter_data(soup.find(string="Relative Drawdown:").find_next().text),
            "totalTrades": soup.find(string="Total Trades:").find_next().text,
            "shortPositions": match_filter_data(soup.find(string="Short Positions (won %):").find_next().text),
            "shortPositionsRatio": match_ratio(soup.find(string="Short Positions (won %):").find_next().text),
            "longPositions": match_filter_data(soup.find(string="Long Positions (won %):").find_next().text),
            "longPositionsRatio": match_ratio(soup.find(string="Long Positions (won %):").find_next().text),
            "profitTrades": match_filter_data(soup.find(string="Profit Trades (% of total):").find_next().text),
            "profitTradesRatio": match_ratio(soup.find(string="Profit Trades (% of total):").find_next().text),
            "lossTrades": match_filter_data(soup.find(string="Loss trades (% of total):").find_next().text),
            "lossTradesRatio": match_ratio(soup.find(string="Loss trades (% of total):").find_next().text),
            "largestProfit": 0,
            "largestLoss": 0,
            "averageProfitTrade": 0,
            "averageLossTrade": 0,
            "maximalConsecutiveProfit": 0,
            "maximalConsecutiveLoss": 0,
            "maximumConsecutiveWins": 0,
            "maximumConsecutiveLosses": 0,
            "averageConsecutiveWins": 0,
            "averageConsecutiveLosses": 0,
            "yieldRate": 0,
            "winRate": 0,
            "plr": 0,
            "avgProfit": 0,
            "mdr": 0,
            "isBursted": 0,
            "maxFUR": 0,
            "score": 0,
        }
        # 计算所需的指标
        initial_cleaned = trader_report["startingCash"].replace(' ', '')
        initial_cash = float(initial_cleaned)
        consecutive_metrics = calculate_consecutive_win_loss(account_list)
        trade_metrics = calculate_trade_metrics(account_list, initial_cash)
        plr = calculate_plr(account_list)
        mdr = calculate_mdr(account_list, initial_cash)
        max_fur = calculate_max_fur(account_list)
        additional_metrics = calculate_additional_metrics(account_list)

        trader_report["startingCash"] = initial_cash
        trader_report["averageConsecutiveWins"] = consecutive_metrics["averageConsecutiveWins"]
        trader_report["averageConsecutiveLosses"] = consecutive_metrics["averageConsecutiveLosses"]
        trader_report["yieldRate"] = trade_metrics["yieldRate"]
        trader_report["winRate"] = trade_metrics["winRate"]
        trader_report["avgProfit"] = trade_metrics["avgProfit"]
        trader_report["plr"] = plr
        trader_report["mdr"] = mdr
        trader_report["max_fur"] = max_fur
        trader_report["totalTrades"] = additional_metrics["tradeCount"]
        newReportTemplate = calculate_metrics(account_list)

        # Largest Profit Trade 和 Loss Trade
        largest_row = soup.find('td', string='Largest')
        if largest_row:
            # 提取 Largest profit 和 loss 数据
            largest_profit = largest_row.find_next('td', class_='mspt').text.strip()
            largest_loss = largest_row.find_next('td', class_='mspt').find_next('td', class_='mspt').text.strip()

            # 去除空格并转换为浮动数值
            trader_report["largestProfit"] = float(
                largest_profit.replace(" ", "").replace(",", "")) if largest_profit else 0
            trader_report["largestLoss"] = float(largest_loss.replace(" ", "").replace(",", "")) if largest_loss else 0

        # Average Profit Trade 和 Loss Trade
        average_row = soup.find('td', string='Average')
        if average_row:
            # 提取 Average profit 和 loss 数据
            average_profit = average_row.find_next('td', class_='mspt').text.strip()
            average_loss = average_row.find_next('td', class_='mspt').find_next('td', class_='mspt').text.strip()

            # 去除空格并转换为浮动数值
            trader_report["averageProfitTrade"] = float(
                average_profit.replace(" ", "").replace(",", "")) if average_profit else 0
            trader_report["averageLossTrade"] = float(
                average_loss.replace(" ", "").replace(",", "")) if average_loss else 0

        # Maximum Consecutive Wins 和 Consecutive Losses
        maximum_row = soup.find('td', string='Maximum')
        if maximum_row:
            # 提取 Maximum consecutive wins 和 consecutive losses 数据
            max_consecutive_wins = maximum_row.find_next('td', class_='mspt').text.strip()
            max_consecutive_losses = maximum_row.find_next('td', class_='mspt').find_next('td',
                                                                                          class_='mspt').text.strip()

            # 处理数据
            max_consecutive_wins_value = max_consecutive_wins.split('(')[1].split(')')[0]  # 提取括号内的数字
            max_consecutive_losses_value = max_consecutive_losses.split('(')[1].split(')')[0]  # 提取括号内的数字

            trader_report["maximumConsecutiveWins"] = float(
                max_consecutive_wins_value.replace(' ', '')) if max_consecutive_wins_value else 0
            trader_report["maximumConsecutiveLosses"] = float(
                max_consecutive_losses_value.replace(' ', '')) if max_consecutive_losses_value else 0

        # Maximal Consecutive Profit 和 Loss
        maximal_row = soup.find('td', string='Maximal')
        if maximal_row:
            # 提取 Maximal consecutive profit 和 loss 数据
            maximal_consecutive_profit = maximal_row.find_next('td', class_='mspt').text.strip()
            maximal_consecutive_loss = maximal_row.find_next('td', class_='mspt').find_next('td',
                                                                                            class_='mspt').text.strip()
            # 处理数据，提取括号内的数字
            maximal_consecutive_profit_value = maximal_consecutive_profit.split('(')[0].strip()  # 提取括号外的数字
            maximal_consecutive_loss_value = maximal_consecutive_loss.split('(')[0].strip()  # 提取括号外的数字

            # 更新数据
            trader_report["maximalConsecutiveProfit"] = float(
                maximal_consecutive_profit_value.replace(" ", "").replace(",",
                                                                          "")) if maximal_consecutive_profit_value else 0
            trader_report["maximalConsecutiveLoss"] = float(
                maximal_consecutive_loss_value.replace(" ", "").replace(",",

                                                                        "")) if maximal_consecutive_loss_value else 0

        return trader_report, additional_metrics, newReportTemplate

    except Exception as e:
        info = traceback.format_exc()
        log.error(f"解析报告出错：{info}")


async def data_filters(db, account_list, startTime, endTime, upload_type=None):
    """
    根据起始和结束时间过滤 account_list 订单数据，只包含起始和结束时间的订单
    """

    """
       根据起始和结束时间过滤 account_list 订单数据，只包含起始和结束时间范围内的订单。
       :param account_list: 订单列表，每个订单包含 timestamp 时间字段
       :param startTime: 过滤起始时间，字符串格式 "YYYY-MM-DD HH:MM:SS"
       :param endTime: 过滤结束时间，字符串格式 "YYYY-MM-DD HH:MM:SS"
       :return: 过滤后的订单列表
       """
    # 转换时间为 datetime 对象
    start_dt = parser.parse(startTime)
    end_dt = parser.parse(endTime)

    # 过滤数据
    filtered_list = [
        order for order in account_list
        if order.get("timestamp")  # 确保 timestamp 不是 None 或空
           and start_dt <= datetime.strptime(order["timestamp"], "%Y-%m-%d %H:%M:%S") <= end_dt
    ]
    if upload_type != "2":  # 不是手动上传的
        # 过滤出 closeTime 为空的交易记录 就是持仓订单的
        open_trades = [trade for trade in filtered_list if trade['closeTime'] is None]
        print(len(open_trades))
        # 更新持仓订单的pnl，就是未关仓的
        for open_order in open_trades:
            identifier = open_order["identifier"]
            key = identifier.split('@')[0]  # 提取 @ 前面的部分 例如: NTROILM5S0001@1737024960@
            # 交易策略
            trading_strategy_db = await db.execute(select(TradingStrategy).filter(
                TradingStrategy.tradeUid == key))

            trading_strategy_datas = trading_strategy_db.scalars().first()
            # 分割字符串
            platform, goods = trading_strategy_datas.goods.split('-')

            select_model_class, goods_ = await select_goods_common(db, trading_strategy_datas.goods, model_classes)
            # 查K线
            select_k_time = select(select_model_class).where(
                select_model_class.platform == platform,
                select_model_class.tradingGoods == goods,
                select_model_class.type == "M1",
                select_model_class.tradeDateTime <= end_dt
            ).order_by(select_model_class.tradeDateTime.desc()).limit(1)

            # 执行查询
            result = await db.execute(select_k_time)
            kline_data = result.scalar_one_or_none()

            if kline_data:
                open_order["price"] = kline_data.closed
                if open_order["orderType"] == "sell":
                    # 做空 PnL = (开仓价格−平仓价格（现价 K线M1的收盘价）)×交易手数×杠杆−隔夜利息
                    open_order["pnl"] = round((open_order["openPrice"] - kline_data.closed) * (open_order["size"] * goods_.profitRatio), 3)
                else:
                    # 做多 PnL=(平仓价格（现价 K线M1的收盘价）− 开仓价格)×交易手数×杠杆−隔夜利息
                    open_order["pnl"] = round((kline_data.closed - open_order["openPrice"]) * (open_order["size"] * goods_.profitRatio), 3)

            else:
                print("No data found")

    return filtered_list


async def process_manual_upload(soup, data_json, strategy,
                                startTime, endTime, uid, goods, period, db, upload_type):
    account_list = []
    # 手动上传的逻辑：如策略查询、交易数据处理等
    closed_transactions_header = soup.find('b', string='Closed Transactions:')
    open_transactions_header = soup.find('b', string='Open Trades:')

    closed_transactions = extract_transactions(closed_transactions_header, stop_text='Closed P/L:')
    open_transactions = extract_transactions(open_transactions_header, stop_text='Floating P/L:')

    account_list.extend(closed_transactions)
    account_list.extend(open_transactions)

    filtered_result = await data_filters(db, account_list, startTime, endTime, upload_type)

    # 提取报告数据
    trader_report, additional_metrics, newReportTemplate = process_manual_generate_trader_report(soup, filtered_result)

    try:
        # 创建策略结果记录
        add_strategy_record = DqlStrategyTestResult(
            uid=generate_random_string("TR"),
            title=strategy.name,
            notes=strategy.description,
            strategyUid=uid,
            goodsId=goods,
            period=period,
            startTime=startTime,
            endTime=endTime,
            traderResult=json.dumps(
                {
                    "traderResult": filtered_result,
                    "traderReport": trader_report,
                    "floatingPointValues": [],
                    "netAssetValues": []
                }
            ),
            parameter=strategy.parameters if strategy.parameters else json.dumps({}),
            isBursted=0, status=0, yieldRate=trader_report["yieldRate"],
            mdr=trader_report["mdr"], winRate=trader_report["winRate"],
            plr=trader_report["plr"], tradeCount=additional_metrics["tradeCount"],
            pnl=additional_metrics["pnl"], maxProfit=additional_metrics["maxProfit"],
            maxLoss=additional_metrics["maxLoss"], avgProfit=trader_report["avgProfit"],
            maxFUR=trader_report["max_fur"], score=0,
            is_delete=0, spread=0,
            leverage=500,
            calculationStatus=1,
            newReportTemplate=json.dumps(newReportTemplate),
            traderReportType=1  # 统一为自动上传类型
        )
        db.add(add_strategy_record)
        await db.commit()
        log.info("手动上传交易报告入库成功：策略UID {}".format(strategy.uid))

    except Exception as e:
        info = traceback.format_exc()
        log.error("交易报告提交失败：{}".format(info))
        await db.rollback()  # 如果发生异常，回滚事务
        await db.close()


async def process_auto_upload(soup, db, grouped_transactions, startTime, endTime):
    # 自动上传的逻辑：例如交易数据的解析，策略计算等
    async with db.begin():  # 开启事务
        for identifier, orders in grouped_transactions.items():
            filtered_result = await data_filters(db, orders, startTime, endTime)
            if filtered_result:
                # 提取报告数据
                trader_report, additional_metrics, newReportTemplate = generate_trader_report(soup, filtered_result)
                # 添加入库
                try:
                    # 自动上传，根据 trading_strategy_uid_list 进行查询交易策略表的uid
                    trading_strategy_db = await db.execute(select(TradingStrategy).filter(
                        TradingStrategy.tradeUid == identifier))

                    trading_strategy_datas = trading_strategy_db.scalars().first()
                    if not trading_strategy_datas:
                        continue

                    strategys = await fetch_indicators(db, trading_strategy_datas.strategyUid)

                    # -------创建策略结果记录-------
                    add_strategy_record = DqlStrategyTestResult(
                        uid=generate_random_string("TR"),
                        title=strategys.name,
                        notes=strategys.description,
                        strategyUid=trading_strategy_datas.strategyUid,
                        goodsId=trading_strategy_datas.goods,
                        period=trading_strategy_datas.period,
                        startTime=startTime,
                        endTime=endTime,
                        traderResult=json.dumps(
                            {
                                "traderResult": filtered_result,
                                "traderReport": trader_report,
                                "floatingPointValues": [],
                                "netAssetValues": []
                            }
                        ),
                        parameter=trading_strategy_datas.parameter,
                        isBursted=0, status=0, yieldRate=trader_report["yieldRate"],
                        mdr=trader_report["mdr"], winRate=trader_report["winRate"],
                        plr=trader_report["plr"], tradeCount=additional_metrics["tradeCount"],
                        pnl=additional_metrics["pnl"], maxProfit=additional_metrics["maxProfit"],
                        maxLoss=additional_metrics["maxLoss"], avgProfit=trader_report["avgProfit"],
                        maxFUR=trader_report["max_fur"], score=0,
                        is_delete=0, spread=0,leverage=500,
                        calculationStatus=1,
                        newReportTemplate=json.dumps(newReportTemplate),
                        traderReportType=1
                    )
                    db.add(add_strategy_record)
                    log.info(f"周期:{trading_strategy_datas.period} 交易报告提交成功  品种：{trading_strategy_datas.goods}")
                except Exception as e:
                    info = traceback.format_exc()
                    log.error("交易报告提交失败：{}".format(info))
                    await db.rollback()  # 如果发生异常，回滚事务
                    await db.close()


class ManualComprehensiveAnalyzer:
    # 假设类里已有这些属性
    precision_format = ".3f"
    max_equity = 0.0
    max_position_size = 0
    total_commission = 0.0
    total_slippage = 0.0

    def _period_minutes(self, period: str) -> int:
        """将周期字符串转成分钟数：M1/M5/M15/M30/H1/H4/D1/W1/MN"""
        p = period.upper()
        if p.startswith("M") and p != "MN":
            return int(p[1:])                     # M1/M5/M15/M30
        if p == "H1":
            return 60
        if p == "H4":
            return 240
        if p == "D1":
            return 1440
        if p == "W1":
            return 10080
        if p == "MN":
            # 月线无法稳定换算成分钟，给 0，下面会特殊处理
            return 0
        # 默认当做分钟
        try:
            return int(p)
        except Exception:
            return 0

    def _calc_barlen(self, open_time: str | None, close_time: str | None, period: str) -> float:
        """根据 openTime/closeTime 和周期估算 bar 数；closeTime 为空时返回 0"""
        if not open_time or not close_time:
            return 0.0
        try:
            ot = datetime.fromisoformat(open_time.replace(" ", "T"))
            ct = datetime.fromisoformat(close_time.replace(" ", "T"))
            minutes = (ct - ot).total_seconds() / 60.0
            per_min = self._period_minutes(period)
            if per_min <= 0:
                return 0.0
            return max(0.0, minutes / per_min)
        except Exception:
            return 0.0

    def _normalize_trades(self, trader_result: list[dict]):
        """
        将 list[dict] 规范成含属性的对象列表，且只保留已平仓（orderType == 'close' 且 closeTime != None）的记录。
        同时区分多空：placeType == 'buy' 视为多单，'sell' 视为空单。
        """
        longs, shorts = [], []
        for row in trader_result:
            pnl = float(row.get("pnl", 0.0))
            barlen = self._calc_barlen(row.get("openTime"), row.get("closeTime"), row.get("period", "M30"))

            trade_obj = SimpleNamespace(
                pnl=pnl,
                barlen=barlen,
                raw=row,  # 原始字典，以备需要
            )

            place = (row.get("placeType") or "").lower()
            if place == "buy":
                longs.append(trade_obj)
            elif place == "sell":
                shorts.append(trade_obj)
            else:
                # 未知方向，默认计入总表但不分多空（下面 overall 会用 longs+shorts 汇总，这里忽略即可）
                pass
        return longs, shorts

    def get_analysis_from_result(self, trader_result: list[dict]) -> dict:
        """
        直接接收 traderResult(list[dict]) 来做统计分析。
        """
        def calculate_stats(trades):
            total_pnl = sum(t.pnl for t in trades)
            gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
            gross_loss = sum(t.pnl for t in trades if t.pnl <= 0)  # 负数或0
            count_total = len(trades)
            count_won = sum(1 for t in trades if t.pnl > 0)
            count_lost = sum(1 for t in trades if t.pnl <= 0)
            avg_pnl = (total_pnl / count_total) if count_total > 0 else 0.0
            avg_won = (gross_profit / count_won) if count_won > 0 else 0.0
            avg_lost = (gross_loss / count_lost) if count_lost > 0 else 0.0  # 注意是负值或0

            max_pnl = max([t.pnl for t in trades], default=0.0)
            max_lost = min([t.pnl for t in trades], default=0.0)  # 最小的盈亏即最大亏损（负数）

            # 盈亏比（总、平均）
            profit_loss_ratio = (gross_profit / -gross_loss) if gross_loss != 0 else 0.0
            avg_profit_ratio = (avg_won / -avg_lost) if avg_lost != 0 else 0.0
            avg_profit_loss_ratio = (avg_won / (avg_won + -avg_lost)) if (avg_won + -avg_lost) != 0 else 0.0

            # 单笔极值占比
            max_profit_ratio = (max_pnl / gross_profit) if gross_profit != 0 else 0.0
            max_loss_ratio = (max_lost / gross_loss) if gross_loss != 0 else 0.0
            net_profit_loss_ratio = (total_pnl / max_lost) if max_lost != 0 else 0.0

            # 连胜/连亏
            max_consecutive_wins = current_wins = 0
            max_consecutive_losses = current_losses = 0
            for t in trades:
                if t.pnl > 0:
                    current_wins += 1
                    max_consecutive_wins = max(max_consecutive_wins, current_wins)
                    current_losses = 0
                else:
                    current_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, current_losses)
                    current_wins = 0

            # 周期统计
            avg_holding_period = (sum(t.barlen for t in trades) / count_total) if count_total else 0.0

            total_profit_period = sum(t.barlen for t in trades if t.pnl > 0)
            avg_profit_period = (total_profit_period / count_won) if count_won else 0.0

            total_loss_period = sum(t.barlen for t in trades if t.pnl <= 0)
            avg_loss_period = (total_loss_period / count_lost) if count_lost else 0.0

            # 持平单（pnl == 0）
            count_breakeven = sum(1 for t in trades if t.pnl == 0)
            total_breakeven_period = sum(t.barlen for t in trades if t.pnl == 0)
            avg_breakeven_period = (total_breakeven_period / count_breakeven) if count_breakeven else 0.0

            f = self.precision_format
            return {
                # 第一列
                'totalPnl': float(format(total_pnl, f)),                 # 净利润
                'grossProfit': float(format(gross_profit, f)),          # 总盈利
                'grossLoss': float(format(gross_loss, f)),              # 总亏损（负数）
                "profitLossRatio": float(format(profit_loss_ratio, f)), # 总盈利/总亏损(绝对值)

                # 第二列
                'countTotal': count_total,                              # 交易笔数
                "profitRatio": float(format(profit_loss_ratio, f)),     # 与上同名概念，这里保留你的字段
                'countWon': count_won,                                  # 盈利笔数
                'countLost': count_lost,                                # 亏损/持平 笔数
                "avgCount": count_breakeven,                            # 持平笔数（原来你写0，这里给真实数量）

                # 第三列
                # 'avg_pnl': float(format(avg_pnl, f)),                 # 如需可打开
                'avgProfitRatio': float(format(avg_profit_ratio, f)),   # 平均盈利/平均亏损(绝对值)
                'avgWon': float(format(avg_won, f)),                    # 平均盈利
                'avgLost': float(format(avg_lost, f)),                  # 平均亏损（负数）
                'avgProfitLossRatio': float(format(avg_profit_loss_ratio, f)),  # 平均盈利/(平均盈利+|平均亏损|)

                # 第四列
                'maxPnl': float(format(max_pnl, f)),                    # 最大盈利
                'maxLost': float(format(max_lost, f)),                  # 最大亏损（负数）
                'maxProfitRatio': float(format(max_profit_ratio, f)),   # 最大盈利/总盈利
                'maxLossRatio': float(format(max_loss_ratio, f)),       # 最大亏损/总亏损
                'netProfitLossRatio': float(format(net_profit_loss_ratio, f)),  # 净盈利/最大亏损(负数)

                # 第五列
                'maxConsecutiveWins': float(format(max_consecutive_wins, f)),   # 最大连赢
                'maxConsecutiveLosses': float(format(max_consecutive_losses, f)),# 最大连亏

                # 第六列（周期）
                'avgLoldingPeriod': float(format(avg_holding_period, f)),       # 平均持仓bar数
                'avgProfitPeriod': float(format(avg_profit_period, f)),         # 平均盈利bar数
                'avgLossPeriod': float(format(avg_loss_period, f)),             # 平均亏损bar数
                'avgBreakevenPeriod': float(format(avg_breakeven_period, f)),   # 平均持平bar数

                # 第七列（沿用你类的成员）
                "maxEquity": float(format(self.max_equity, f)),         # 最大使用资金
                "maxPositionSize": self.max_position_size,              # 最大持仓手数
                "totalCosts": self.total_commission + self.total_slippage,  # 成本合计

                # 第八列
                "analysis": float(format((total_pnl / self.max_equity) if self.max_equity else 0.0, f)),  # 收益率
                "annualizedReturn": 0.0,
                "EffectiveYield": 0.0,
                "AverageProfitMonth": 0.0,
            }

        # --- 入口：把 trader_result 规范化为多空两组 ---
        long_trades, short_trades = self._normalize_trades(trader_result)

        # --- 计算 ---
        long_stats = calculate_stats(long_trades)
        short_stats = calculate_stats(short_trades)
        overall_stats = calculate_stats(long_trades + short_trades)

        return {
            'overall': overall_stats,
            'long': long_stats,
            'short': short_stats
        }
