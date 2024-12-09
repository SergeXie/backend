import traceback
import backtrader as bt
import datetime
from common.log import log


class ComprehensiveAnalyzer(bt.Analyzer):
    def __init__(self):
        self.long_trades = []
        self.short_trades = []
        self.total_commission = 0.0
        self.total_slippage = 0.0
        self.max_equity = 0.0
        self.max_position_size = 0
        # 精度
        digits = self.datas[0].digits[0]
        self.precision_format = f".{int(digits)}f"

    def notify_trade(self, trade):
        if trade.isclosed:
            if trade.history[0].event.size > 0:
                self.long_trades.append(trade)
            else:
                self.short_trades.append(trade)
            self.total_commission += trade.commission

            # self.total_slippage += trade.slip

        # Update max equity and max position size
        if self.strategy.broker.get_value() > self.max_equity:
            self.max_equity = self.strategy.broker.get_value()

        if self.strategy.position.size > self.max_position_size:
            self.max_position_size = self.strategy.position.size

    def get_analysis(self):
        def calculate_stats(trades):
            total_pnl = sum(trade.pnl for trade in trades)
            gross_profit = sum(trade.pnl for trade in trades if trade.pnl > 0)
            gross_loss = sum(trade.pnl for trade in trades if trade.pnl <= 0)
            count_total = len(trades)
            count_won = len([trade for trade in trades if trade.pnl > 0])
            count_lost = len([trade for trade in trades if trade.pnl <= 0])
            avg_pnl = total_pnl / count_total if count_total > 0 else 0
            avg_won = gross_profit / count_won if count_won > 0 else 0
            avg_lost = gross_loss / count_lost if count_lost > 0 else 0
            max_pnl = max([trade.pnl for trade in trades], default=0)
            max_lost = min([trade.pnl for trade in trades], default=0)
            profit_ratio = gross_profit / -gross_loss if gross_loss != 0 else 0
            avg_profit_ratio = avg_won / -avg_lost if avg_lost != 0 else 0
            avg_profit_loss_ratio = avg_won / (avg_won + -avg_lost) if avg_won + -avg_lost != 0 else 0

            max_profit_ratio = max_pnl / gross_profit if gross_profit != 0 else 0
            max_loss_ratio = max_lost / gross_loss if gross_loss != 0 else 0
            net_profit_loss_ratio = total_pnl / max_lost if max_lost != 0 else 0
            profit_loss_ratio = gross_profit / -gross_loss if gross_loss != 0 else 0

            max_consecutive_wins = 0
            current_wins = 0
            max_consecutive_losses = 0
            current_losses = 0

            for trade in trades:
                if trade.pnl > 0:
                    current_wins += 1
                    max_consecutive_wins = max(max_consecutive_wins, current_wins)
                    current_losses = 0
                elif trade.pnl <= 0:
                    current_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, current_losses)
                    current_wins = 0

            avg_holding_period = sum(trade.barlen for trade in trades) / len(trades) if trades else 0
            avg_profit_period = sum(trade.barlen for trade in trades if trade.pnl > 0)
            if avg_profit_period:
                avg_profit_period / len([trade for trade in trades if trade.pnl > 0])
            avg_loss_period = sum(trade.barlen for trade in trades if trade.pnl <= 0)
            if avg_loss_period:
                avg_loss_period / len([trade for trade in trades if trade.pnl <= 0])

            avg_breakeven_period = 0  # 默认填0

            return {
                'totalPnl': float(format(total_pnl, self.precision_format)),  # 净利润
                'grossProfit': float(format(gross_profit, self.precision_format)),  # 总盈利
                'grossLoss': float(format(gross_loss, self.precision_format)),  # 总亏损
                "profitLossRatio": float(format(profit_loss_ratio, self.precision_format)),  # 总盈利/总亏损
                # 第二列
                'countTotal': count_total,  # 交易手数
                "profitRatio": float(format(profit_ratio, self.precision_format)),  # 盈利比率 (总盈利/总亏损)
                'countWon': count_won,  # 盈利手数
                'countLost': count_lost,  # 亏损手数
                "avgCount": 0,   # 持平手数
                # 第三列
                # 'avg_pnl': avg_pnl,  # 平均利润
                'avgProfitRatio': float(format(avg_profit_ratio, self.precision_format)),  # 平均利润 (平均盈利/平均亏损)
                'avgWon': float(format(avg_won, self.precision_format)),  # 平均盈利
                'avgLost': float(format(avg_lost, self.precision_format)),  # 平均亏损
                'avgProfitLossRatio': float(format(avg_profit_loss_ratio, self.precision_format)),  # 平均盈利/平均盈亏
                # 第四列
                'maxPnl': float(format(max_pnl, self.precision_format)),  # 最大盈利
                'maxLost': float(format(max_lost, self.precision_format)),  # 最大亏损
                'maxProfitRatio': float(format(max_profit_ratio, self.precision_format)),  # 最大盈利/总盈利
                'maxLossRatio': float(format(max_loss_ratio, self.precision_format)),  # 最大亏损/总亏损
                'netProfitLossRatio': float(format(net_profit_loss_ratio, self.precision_format)),  # 净盈利/最大亏损
                # 第五列
                'maxConsecutiveWins': float(format(max_consecutive_wins, self.precision_format)), # 最大连续盈利手数
                'maxConsecutiveLosses': float(format(max_consecutive_losses, self.precision_format)), # 最大连续亏损手数

                # 第六列
                'avgLoldingPeriod': float(format(avg_holding_period, self.precision_format)),  # 平均持仓周期
                'avgProfitPeriod': float(format(avg_profit_period, self.precision_format)),  # 平均盈利周期
                'avgLossPeriod': float(format(avg_loss_period, self.precision_format)),  # 平均亏损周期
                'avgBreakevenPeriod': float(format(avg_breakeven_period, self.precision_format)), # 平均持平周期
                # 第七列
                "maxEquity": float(format(self.max_equity, self.precision_format)), # 最大使用资金
                "maxPositionSize": self.max_position_size,  # 最大持仓手数
                "totalCosts": self.total_commission + self.total_slippage, # 交易成本合计
                # 第八列
                "analysis": float(format(total_pnl / self.max_equity, self.precision_format)) if self.max_equity != 0 else 0, # 收益率
                "annualizedReturn": 0,  # 年化收益率
                "EffectiveYield": 0,  # 年化收益率
                "AverageProfitMonth": 0,  # 月度平均盈利

            }

        long_stats = calculate_stats(self.long_trades)
        short_stats = calculate_stats(self.short_trades)
        overall_stats = calculate_stats(self.long_trades + self.short_trades)

        return {
            'overall': overall_stats,
            'long': long_stats,
            'short': short_stats
        }


class CommonStrategy(bt.Strategy):

    # 日志打印
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print("%s, %s" % (dt, txt))

    def __init__(self, goodsId):
        self.goodsId = goodsId
        self.order = None
        self.last_cash = self.broker.get_cash()  # 起始本金
        self.trader_result = []
        self.trader_report = {}
        self.starting_cash = self.broker.startingcash  # 起始资金
        self.initial_cash = self.broker.get_cash()
        self.max_cash = self.initial_cash
        self.trade_count = 0
        self.winning_trades = 0  # 盈利单数
        self.losing_trades = 0  # 亏损单数
        self.total_profit = 0.0
        self.total_loss = 0.0
        self.max_winning_trade = 0.0
        self.max_losing_trade = 0.0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_consecutive_wins = 0
        self.max_consecutive_losses = 0
        self.max_consecutive_profit_sum = 0.0
        self.max_consecutive_loss_sum = 0.0
        self.current_consecutive_profit_sum = 0.0
        self.current_consecutive_loss_sum = 0.0
        self.isbursted = 0
        self.mdr = 0.0
        self.maxfur = 0.0
        self.buy_winning_trades = 0
        self.sell_winning_trades = 0
        self.max_loss = 0
        self.netAssetValues = []  # 用于存储净值数据
        self.floatingPointValues = []  # 用于存储浮动盈亏数据
        self.profit_list = []  # 盈利金额列表
        self.loss_list = []  # 亏损金额列表
        self.profit_points_list = []  # 盈利点值列表
        self.loss_points_list = []  # 亏损点值列表
        self.profit_volume = 0  # 盈利单总手数
        self.loss_volume = 0  # 亏损单总手数
        self.traded_positions = {}  # 存储已交易的持仓
        self.absolute_drawdown = 0
        self.maximal_drawdown = 0
        self.relative_drawdown = 0
        self.max_profit_trade = 0
        self.max_loss_trade = 0
        self.consecutive_wins_list = []
        self.consecutive_losses_list = []
        self.order_point = []

        self.trade_ref_dict = {}


    def calculate_values(self):
        """
        计算浮值和净值
        :return:
        """
        # 点差
        spread = int(self.datas[0].spread[0])
        # if spread != 0:
        #     # 设置固定滑点(点差) 设置固定滑点 后续公式 手数 * spread /10 现在固定 spread / 100
        #     self.broker.set_slippage_fixed(fixed=64 / 100)

    def calculate_float_net_values(self):
        # 精度
        digits = self.datas[0].digits[0]
        precision_format = f".{int(digits)}f"

        # 计算浮值（按照最新的收盘价折算未平仓的交易单总盈亏） 每一根bar的持仓数量 * （当前k线的收盘价 - 持仓价格）
        # 每个持仓的数量乘以当前收盘价与买入价的差值。所有持仓的浮值总和就是总浮值。
        float_value = 0
        for data in self.datas:
            position = self.getposition(data)  # 访问仓位信息
            if position.size != 0 and data in self.traded_positions:
                float_value += float(format(position.size * 100 * (data.close[0] - position.price), precision_format))

        # 计算浮值
        float_value_ = float(format(self.broker.get_value() - float_value, precision_format))
        self.floatingPointValues.append(float_value_)

        # 净值市值
        self.netAssetValues.append(float(format(self.broker.get_value(), precision_format)))

    def notify_order(self, order):
        if order.status in [order.Margin, order.Rejected, order.Expired]:
            self.log("交易被拒绝/现金不足/取消 :{}".format(order.status))
            self.isbursted = 1

        if order.status in [order.Completed]:
            cash = self.broker.get_cash()
            value = self.broker.getvalue()
            order_type = 'Buy' if order.isbuy() else 'Sell'

            self.log(f'{order_type} 订单执行完成，价格：{order.executed.price}, 交易价：{order.executed.value} '
                     f'当前关仓价：{self.datas[0].close[0]}, 数量：{order.executed.size}, 当前资金：{cash}, 订单类型：{order.ordtype}')

    def notify_trade(self, trade):
        """
        ref: 交易的引用编号，通常是一个唯一的标识符。
        data: 与交易相关的市场数据对象，可能包含价格、成交量等信息。
        tradeid: 交易的ID，区分可能同时存在的多个交易。
        size: 交易的大小，表示买入或卖出的资产数量。
        price: 交易的价格，表示每单位资产的买入或卖出价格。
        value: 交易的总价值，通常是 size 乘以 price。
        commission: 交易的佣金费用。
        pnl: 交易的盈亏（Profit and Loss），未实现的盈亏指的是当前开放的交易的盈亏。
        pnlcomm: 考虑佣金后的交易盈亏。
        justopened: 表示交易是否刚刚开启。
        isopen: 表示交易是否仍然开放。
        isclosed: 表示交易是否已经关闭。
        baropen: 交易开启时的bar（或者说是蜡烛图）索引。
        dtopen: 交易开启时的日期时间戳。
        barclose: 交易关闭时的bar索引。
        dtclose: 交易关闭时的日期时间戳。
        barlen: 交易持续的bar数量。
        historyon: 表示是否记录交易历史。
        history: 交易历史记录的列表。
        status: 交易的状态码，可能表示交易是新开的、开放的、关闭的等。
        :param trade:
        :return:
        """
        try:
            trader_dict = dict()
            # 精度
            digits = self.datas[0].digits[0]
            precision_format = f".{int(digits)}f"
            # 点差
            spread = int(self.datas[0].spread[0])

            if trade.isclosed:
                order_type = 'close'
                trader_dict["openTime"] = trade.open_datetime().strftime('%Y-%m-%d %H:%M:%S')
                trader_dict["openPrice"] = float(format(trade.price, precision_format))
                trader_dict["closeTime"] = trade.close_datetime().strftime('%Y-%m-%d %H:%M:%S')
            elif trade.history[0].event.order.isbuy():
                order_type = 'buy'
                trader_dict["openPrice"] = float(format(trade.price, precision_format))
                trader_dict["openTime"] = trade.open_datetime().strftime('%Y-%m-%d %H:%M:%S')
                trader_dict["closeTime"] = None
            elif trade.history[0].event.order.issell():
                order_type = 'sell'
                trader_dict["openPrice"] = float(format(trade.price, precision_format))
                trader_dict["openTime"] = trade.open_datetime().strftime('%Y-%m-%d %H:%M:%S')
                trader_dict["closeTime"] = None
            else:
                order_type = None
                trader_dict["openTime"] = None
                trader_dict["closeTime"] = None
                trader_dict["openPrice"] = None

            if trade.history[0].event.order.isbuy():
                place_type = 'buy'
            elif trade.history[0].event.order.issell():
                place_type = 'sell'
            else:
                place_type = None

            # 订单交易
            event_info = [trader.event for trader in trade.history][0]
            self.starting_cash += trade.pnlcomm
            trader_dict["tradeid"] = trade.ref
            trader_dict["orderType"] = order_type
            trader_dict["placeType"] = place_type
            trader_dict["goodsId"] = self.goodsId
            trader_dict["size"] = trade.history[-1].event.size
            trader_dict["price"] = float(format(trade.history[-1].event.price, precision_format))
            trader_dict["timestamp"] = self.datas[0].datetime.datetime().strftime('%Y-%m-%d %H:%M:%S')
            trader_dict["stopLoss"] = event_info.order.info.get("stopLoss", 0.0)
            trader_dict["takeProfit"] = event_info.order.info.get("takeProfit", 0.0)
            trader_dict["taxes"] = 0
            trader_dict["swap"] = 0
            trader_dict["commission"] = trade.commission
            trader_dict["pnl"] = float(format(trade.pnlcomm, precision_format))
            trader_dict["spread"] = spread / 100 if spread else 0
            trader_dict["initialCash"] = float(format(self.starting_cash, precision_format))

            self.trader_result.append(trader_dict)

            # 交易报告
            if trade.isclosed:
                # 计算最大回撤率
                tmp = (self.broker.getvalue() - self.last_cash) / self.last_cash
                # 最大资金利用率
                self.maxfur = max(self.maxfur, tmp)
                # 计算最大回撤率
                self.mdr = max(self.mdr, tmp)
                profit = trade.pnlcomm

                # 更新最大亏损金额
                self.max_loss = min(self.max_loss, profit)

                # 计算盈利点值: 计算开仓价和平仓价之间的差值，来获得每笔交易的盈利点数。然后，所有盈利点数累加得到总的盈利点值
                points = trade.price - trade.history[-1].event.price

                if points > 0:
                    self.profit_points_list.append(points)
                else:
                    self.loss_points_list.append(abs(points))
                if trade.history[0].event.order.size > 0:
                    self.profit_volume += 0.1
                    self.buy_winning_trades += 1
                elif trade.history[0].event.order.size < 0:
                    self.loss_volume += 0.1
                    self.sell_winning_trades += 1

                if profit > 0:
                    # 如果盈利，记录盈利金额、点值和手数
                    self.profit_list.append(profit)
                    self.profit_points_list.append(points)
                    self.winning_trades += 1
                    self.total_profit += profit
                    self.current_consecutive_profit_sum += profit

                    # 计算平均连续获利交易
                    self.consecutive_wins += 1

                    if self.consecutive_losses > 0:
                        self.consecutive_losses_list.append(self.consecutive_losses)

                        if abs(self.current_consecutive_loss_sum) > abs(self.max_consecutive_loss_sum):
                            self.max_consecutive_loss_sum = self.current_consecutive_loss_sum
                        self.current_consecutive_loss_sum = 0.0
                    self.consecutive_losses = 0
                    self.max_consecutive_wins = max(self.max_consecutive_wins, self.consecutive_wins)

                else:
                    # 如果亏损，记录亏损金额、点值和手数
                    self.loss_list.append(abs(profit))
                    self.loss_points_list.append(abs(points))
                    self.losing_trades += 1
                    self.total_loss += profit
                    self.current_consecutive_loss_sum += abs(profit)
                    self.consecutive_losses += 1
                    # 计算平均连续亏损交易
                    if self.consecutive_wins > 0:
                        self.consecutive_wins_list.append(self.consecutive_wins)
                        if self.current_consecutive_profit_sum > self.max_consecutive_profit_sum:
                            self.max_consecutive_profit_sum = self.current_consecutive_profit_sum
                        self.current_consecutive_profit_sum = 0.0

                    self.consecutive_wins = 0
                    self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)

                self.trade_count += 1

                if profit > self.max_winning_trade:
                    self.max_winning_trade = profit
                if profit < self.max_losing_trade:
                    self.max_losing_trade = profit

            # 计算当前余额并更新最大资金值
            current_cash = self.broker.get_cash()

            self.max_cash = max(self.max_cash, current_cash)

            # 计算绝对亏损和最大亏损和相对亏损
            self.absolute_drawdown = max(self.absolute_drawdown, self.initial_cash - current_cash)
            drawdown = self.max_cash - current_cash
            self.maximal_drawdown = max(self.maximal_drawdown, drawdown)
            if self.max_cash > 0:
                self.relative_drawdown = max(self.relative_drawdown, (drawdown / self.max_cash) * 100)

            # 计算最大连续获利和连续亏损金额
            profit = trade.pnlcomm
            self.max_profit_trade = max(self.max_profit_trade, profit)
            self.max_loss_trade = min(self.max_loss_trade, profit)

            current_datetime = self.datas[0].datetime.datetime(0)
            print(f"交易完成，利润：{trade.pnl}, 数量：{trade.size}, 价格：{trade.price} 交易时间：{current_datetime}")

            self.calculate_float_net_values()


            # 用于计算实时买卖点
            date_obj = datetime.datetime.strptime(trader_dict["timestamp"], "%Y-%m-%d %H:%M:%S")
            # 将datetime对象转换为时间戳
            if order_type == 'buy' or order_type == 'sell':  # 在开仓时候记录[orderid:时间戳]
                self.trade_ref_dict[trade.ref] = int(date_obj.timestamp())
                date_obj = int(date_obj.timestamp())
            elif order_type == 'close':
                date_obj = self.trade_ref_dict.get(trade.ref)

            # print(trade.ref, date_obj)
            self.order_point.append({
                "datatime": self.datas[0].datetime.datetime(),
                "order_type": order_type,
                "price": float(format(trade.history[-1].event.price, precision_format)),
                "size": trade.size,
                "orderId": date_obj,
            })

        except Exception as e:
            info = traceback.format_exc()
            log.info("策略计算结果出错！：{}".format(info))

    def stop(self):
        try:
            # 策略结束时计算并输出盈亏比
            total_profit_amount = sum(self.profit_list)  # 总盈利金额
            total_loss_amount = sum(self.loss_list)  # 总亏损金额
            total_profit_points = sum(self.profit_points_list)  # 总盈利点值
            total_loss_points = sum(self.loss_points_list)  # 总亏损点值
            total_profit_trades = len(self.profit_list)  # 总盈利交易次数
            total_loss_trades = len(self.loss_list)  # 总亏损交易次数

            if (total_profit_trades > 0 and total_loss_trades > 0
                    and self.profit_volume > 0 and self.loss_volume > 0):

                # 计算并输出两种盈亏比
                profit_ratio_1 = (total_profit_amount / self.profit_volume) / (
                        total_loss_amount / self.loss_volume)

                profit_points_per_trade = total_profit_points / total_profit_trades
                loss_points_per_trade = total_loss_points / total_loss_trades
                profit_ratio_2 = profit_points_per_trade / loss_points_per_trade

            else:
                profit_ratio_1 = 0
                profit_ratio_2 = 0

            # 精度
            digits = self.datas[0].digits[0]
            precision_format = f".{int(digits)}f"
            total_net_profit = self.total_profit + self.total_loss
            profit_factor = self.total_profit / abs(self.total_loss) if self.total_loss != 0 else 0
            expected_profit = total_net_profit / self.trade_count if self.trade_count != 0 else 0
            absolute_loss = self.initial_cash - (self.initial_cash + total_net_profit)
            profit_trades = (self.winning_trades / self.trade_count) * 100 if self.trade_count > 0 else 0
            loss_trades = (self.losing_trades / self.trade_count) * 100 if self.trade_count > 0 else 0

            average_consecutive_wins = sum(self.consecutive_wins_list) / len(
                self.consecutive_wins_list) if self.consecutive_wins_list else 0

            average_consecutive_losses = sum(self.consecutive_losses_list) / len(
                self.consecutive_losses_list) if self.consecutive_losses_list else 0

            if self.consecutive_wins > 0:
                if self.current_consecutive_profit_sum > self.max_consecutive_profit_sum:
                    self.max_consecutive_profit_sum = self.current_consecutive_profit_sum
            if self.consecutive_losses > 0:
                if abs(self.current_consecutive_loss_sum) > abs(self.max_consecutive_loss_sum):
                    self.max_consecutive_loss_sum = self.current_consecutive_loss_sum

            self.trader_report = {
                # 起始资金
                "startingCash": self.initial_cash,
                # 可用资金
                "FreeMargin": self.broker.getcash(),
                # 总净盈利
                'totalNetProfit': float(format(total_net_profit, precision_format)),
                # 总获利金额
                'totalProfit': float(format(self.total_profit, precision_format)),
                # 总亏损金额
                'totalLoss': float(format(self.total_loss, precision_format)),
                # 盈利比
                'ProfitFactor': float(format(profit_factor, precision_format)),
                # 预期收益: 总净盈利 / 交易总数
                'expectedPayoff': float(format(expected_profit, precision_format)),
                # 绝对亏损：
                'absoluteDrawdown': float(format(self.absolute_drawdown, precision_format)),
                # 最大亏损
                'maximalDrawdown': float(format(self.maximal_drawdown, precision_format)),
                # 相对亏损
                'relativeLosses': float(format(self.relative_drawdown, precision_format)),
                # 交易总计
                'totalTrades': self.trade_count,
                # 卖单的交易总数
                'shortPositions': self.sell_winning_trades,
                # 卖单百分比
                'shortPositionsRatio': float(format((self.sell_winning_trades / self.trade_count) * 100,
                                                    precision_format)) if self.trade_count > 0 else 0,
                # 买单的交易总数
                'longPositions': self.buy_winning_trades,
                # 买单的百分比
                'longPositionsRatio': float(format((self.buy_winning_trades / self.trade_count) * 100,
                                                   precision_format)) if self.trade_count > 0 else 0,
                # 盈利交易次数
                'profitTrades': float(format(self.winning_trades, precision_format)),
                # 盈利交易次数百分比
                'profitTradesRatio': float(format(profit_trades, precision_format)),
                # 亏损交易
                'lossTrades': float(format(self.losing_trades, precision_format)),
                # 亏损交易(%占总百分比)
                'lossTradesRatio': float(format(loss_trades, precision_format)),
                # 最大的单笔获利金额
                'largestProfit': float(format(self.max_winning_trade, precision_format)),
                # 最大的单笔亏损金
                'largestLoss': float(format(self.max_losing_trade, precision_format)),

                # 平均获利金额
                'averageProfitTrade': float(format(self.total_profit / self.winning_trades,
                                                   precision_format)) if self.winning_trades > 0 else 0,
                # 平均亏损金额
                'averageLossTrade': float(
                    format(self.total_loss / self.losing_trades, precision_format)) if self.losing_trades > 0 else 0,

                # 最大的连续获利金额
                'maximalConsecutiveProfit': float(format(self.max_consecutive_profit_sum, precision_format)),
                # 最大的连续亏损金额
                'maximalConsecutiveLoss': float(format(self.max_consecutive_loss_sum, precision_format)),
                # 最大的连续获利次数
                'maximumConsecutiveWins': float(format(self.max_consecutive_wins, precision_format)),
                # 最多的连续亏损次数
                'maximumConsecutiveLosses': float(format(self.max_consecutive_losses, precision_format)),
                # 连续盈利交易的平均数
                'averageConsecutiveWins': float(format(average_consecutive_wins,
                                                       precision_format)) if self.trade_count > 0 else 0,
                # 连续亏损交易的平均数
                'averageConsecutiveLosses': float(format(average_consecutive_losses,
                                                         precision_format)) if self.trade_count > 0 else 0,
                # 收益率
                "yieldRate": float(
                    format((self.broker.getvalue() - self.initial_cash) / self.initial_cash * 100, precision_format)),
                # 胜率
                "winRate": float(format(self.winning_trades / self.trade_count * 100, precision_format)) if self.winning_trades else 0,
                # 盈亏比
                "plr": float(format(profit_ratio_1, precision_format)),
                "avgProfit": float(format(total_net_profit / self.trade_count, precision_format)) if total_net_profit else 0,  # 平均每次收益
                
                "mdr": float(format(self.mdr, precision_format)),
                "isBursted": self.isbursted,
                "maxFUR": float(format(self.maxfur, precision_format)),
                "score": 0
            }

            print('策略绩效指标:', self.trader_report)

        except Exception as e:
            info = traceback.format_exc()
            log.info("策略计算结果出错！：{}".format(info))

    def get_analysis(self):

        trader_return = {
            'trader_result': self.trader_result,
            'trader_report': self.trader_report,
            'order_point': self.order_point,
            'floating_point_values': self.floatingPointValues,
            'net_asset_values': self.netAssetValues,
        }
        return trader_return

