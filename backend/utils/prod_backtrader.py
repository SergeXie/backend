import datetime
import backtrader as bt
from utils.common import datetimesp


class MyStrategy(bt.Strategy):

    def __init__(self, params=None, tradeId=0, goodsTraderId=0):
        self.orefs = list()
        self.starting_cash = self.broker.startingcash  # 起始资金
        self.fail_trades = []
        self.goodsTraderId = goodsTraderId
        self.tradeId = tradeId
        self.trader_result = []
        self.total_trader_result = []
        self.params = params if params else []  # 接收订单参数

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f'{dt} {txt}')  # Print date and close

    def data_dict(self, ticks, trader_goods):
        """
        下单过程中，附带额外信息
        :param ticks:
        :param trader_goods:
        :return:
        """
        data = dict(ticksId=ticks["ticksId"],
                    stopLoss=ticks["stopLoss"],
                    takeProfit=ticks["takeProfit"],
                    goods=trader_goods["goods"],
                    position=ticks["position"],
                    close_price=self.datas[0].close[0],
                    klineId=ticks.get("klineId", 0))

        return data

    def execute_order(self, ticks, position, orderType, trader_goods, tradeid, price, size, exectype,
                      valid_ex, parent=None, stop_loss=0, take_profit=0):
        order = None
        # 市价交易
        if exectype == bt.Order.Market:
            if take_profit > 0 or stop_loss > 0:
                transmit = False
            else:
                transmit = True
            if position == 'long':
                if orderType == "buy":
                    order = self.buy(tradeid=tradeid, price=price, size=float(size),
                                     exectype=exectype,
                                     transmit=transmit)

                    order.addinfo(**self.data_dict(ticks, trader_goods))
                else:
                    order = self.sell(tradeid=tradeid, price=price, size=float(size),
                                      exectype=exectype,
                                      transmit=transmit)

                    order.addinfo(**self.data_dict(ticks, trader_goods))

            elif position == 'short':
                if orderType == "sell":
                    order = self.sell(tradeid=tradeid, price=price, size=float(size),
                                      exectype=exectype,
                                      transmit=transmit)

                    order.addinfo(**self.data_dict(ticks, trader_goods))
                else:
                    order = self.buy(tradeid=tradeid, price=price, size=float(size),
                                     exectype=exectype,
                                     transmit=transmit)

                    order.addinfo(**self.data_dict(ticks, trader_goods))

        # 限价挂单交易
        elif exectype in [bt.Order.Limit, bt.Order.Stop]:
            if take_profit > 0 or stop_loss > 0:
                transmit = False
            else:
                transmit = True

            if ticks["type"] in [1, 3]:  # 1=buy limit or 3=sell limit
                order = self.buy(tradeid=tradeid, price=price, size=float(size),
                                 exectype=exectype, valid=valid_ex,
                                 parent=parent, transmit=transmit)

                order.addinfo(**self.data_dict(ticks, trader_goods))

            else:  # buy stop or sell stop
                order = self.sell(tradeid=tradeid, price=price, size=float(size),
                                  exectype=exectype, valid=valid_ex, parent=parent,
                                  transmit=transmit)

                order.addinfo(**self.data_dict(ticks, trader_goods))

        if order:
            print('{}: Oref {} / {} at {}'.format(
                self.datetime.date(), order.ref, "Buy"
                if exectype == bt.Order.Market and ticks["position"] == 'long' else "Sell" if
                exectype == bt.Order.Market and ticks["position"] == 'short'
                else "Buy Limit" if exectype == bt.Order.Limit and ticks["type"] == 1
                else "Sell Limit" if exectype == bt.Order.Limit and ticks["type"] == 2 else "Buy Stop"
                if exectype == bt.Order.Stop and ticks["type"] == 3 else "Sell Stop", price))

        self.handle_stop_loss_and_take_profit(position, orderType, tradeid, size, stop_loss, take_profit, order,
                                              valid_ex, ticks, trader_goods)

    def handle_stop_loss_and_take_profit(self, position, orderType, tradeid, size, stop_loss,
                                         take_profit, order, valid_ex, ticks, trader_goods):
        """
        止损函数
        :param position: 方向
        :param orderType: 订单类型
        :param tradeid: 订单ID
        :param size: 手数
        :param stop_loss: 止损
        :param take_profit:  止盈
        :param order: 主订单
        :param valid_ex: 有效期
        :param ticks: 订单参数
        :param trader_goods: 交易品种
        :return:
        """
        # 当止盈止损都成立时，执行。
        if take_profit > 0 and stop_loss > 0:
            if ticks["type"] in [1, 3]:
                sell_stop = self.sell(tradeid=tradeid, exectype=bt.Order.Stop, price=stop_loss, size=float(size),
                                      parent=order,
                                      valid=valid_ex, transmit=False)

                sell_stop.addinfo(**self.data_dict(ticks, trader_goods))

                sell_limit = self.sell(tradeid=tradeid, exectype=bt.Order.Limit, price=take_profit, size=float(size),
                                       parent=order,
                                       valid=valid_ex, transmit=True, oargs=self.data_dict(ticks, trader_goods))

                sell_limit.addinfo(**self.data_dict(ticks, trader_goods))

            elif ticks["type"] in [2, 4]:
                buy_stop = self.buy(tradeid=tradeid, exectype=bt.Order.Stop, price=stop_loss, size=float(size),
                                    parent=order,
                                    valid=valid_ex, transmit=False)

                buy_stop.addinfo(**self.data_dict(ticks, trader_goods))

                buy_limit = self.buy(tradeid=tradeid, exectype=bt.Order.Limit, price=take_profit, size=float(size),
                                     parent=order,
                                     valid=valid_ex, transmit=True)

                buy_limit.addinfo(**self.data_dict(ticks, trader_goods))

            else:
                if orderType == "buy":
                    sell_stop = self.sell(tradeid=tradeid, exectype=bt.Order.Stop, price=stop_loss,
                                          size=float(size),
                                          parent=order,
                                          valid=valid_ex, transmit=False)

                    sell_stop.addinfo(**self.data_dict(ticks, trader_goods))

                    sell_limit = self.sell(tradeid=tradeid, exectype=bt.Order.Limit, price=take_profit,
                                           size=float(size),
                                           parent=order,
                                           valid=valid_ex, transmit=True, oargs=self.data_dict(ticks, trader_goods))

                    sell_limit.addinfo(**self.data_dict(ticks, trader_goods))

                else:
                    buy_stop = self.buy(tradeid=tradeid, exectype=bt.Order.Stop, price=stop_loss, size=float(size),
                                        parent=order,
                                        valid=valid_ex, transmit=False)

                    buy_stop.addinfo(**self.data_dict(ticks, trader_goods))

                    buy_limit = self.buy(tradeid=tradeid, exectype=bt.Order.Limit, price=take_profit,
                                         size=float(size),
                                         parent=order,
                                         valid=valid_ex, transmit=True)

                    buy_limit.addinfo(**self.data_dict(ticks, trader_goods))

        else:
            if stop_loss > 0:
                if ticks["type"] in [1, 3]:
                    order = self.sell(tradeid=tradeid, exectype=bt.Order.Limit, price=stop_loss, size=float(size),
                                      parent=order,
                                      valid=valid_ex, transmit=True, oargs=self.data_dict(ticks, trader_goods))

                    order.addinfo(**self.data_dict(ticks, trader_goods))

                elif ticks["type"] in [2, 4]:
                    order = self.buy(tradeid=tradeid, exectype=bt.Order.Limit, price=stop_loss, size=float(size),
                                     parent=order, valid=valid_ex, transmit=True)

                    order.addinfo(**self.data_dict(ticks, trader_goods))

                else:
                    if orderType == "buy":
                        order = self.sell(tradeid=tradeid, exectype=bt.Order.Limit, price=stop_loss, size=float(size),
                                          parent=order,
                                          valid=valid_ex, transmit=True, oargs=self.data_dict(ticks, trader_goods))

                        order.addinfo(**self.data_dict(ticks, trader_goods))
                    elif orderType == "sell":
                        order = self.buy(tradeid=tradeid, exectype=bt.Order.Limit, price=stop_loss, size=float(size),
                                         parent=order, valid=valid_ex, transmit=True)

                        order.addinfo(**self.data_dict(ticks, trader_goods))

            elif take_profit > 0:
                if ticks["type"] in [1, 3]:
                    order = self.sell(tradeid=tradeid, exectype=bt.Order.Limit,
                                      price=take_profit, size=float(size), parent=order,
                                      valid=valid_ex, transmit=True)

                    order.addinfo(**self.data_dict(ticks, trader_goods))
                elif ticks["type"] in [2, 4]:
                    order = self.buy(tradeid=tradeid, exectype=bt.Order.Limit,
                                     price=take_profit, size=float(size), parent=order,
                                     valid=valid_ex, transmit=True)

                    order.addinfo(**self.data_dict(ticks, trader_goods))

                else:
                    if orderType == "buy":
                        order = self.sell(tradeid=tradeid, exectype=bt.Order.Limit, price=stop_loss, size=float(size),
                                          parent=order,
                                          valid=valid_ex, transmit=True, oargs=self.data_dict(ticks, trader_goods))

                        order.addinfo(**self.data_dict(ticks, trader_goods))
                    elif orderType == "sell":
                        order = self.buy(tradeid=tradeid, exectype=bt.Order.Limit, price=stop_loss, size=float(size),
                                         parent=order, valid=valid_ex, transmit=True)

                        order.addinfo(**self.data_dict(ticks, trader_goods))

    def next(self):
        # 当前关盘价格
        close_price = self.datas[0].close[0]
        for trader_goods in self.params:
            for ticks in trader_goods.get("ticks", []):
                current_kline_id = self.data.klineId[0]
                if int(current_kline_id) == ticks['klineId']:
                    # 市价单
                    if ticks["operate"] == "marketOrder":
                        self.execute_order(
                            ticks,
                            ticks["position"],
                            ticks["orderType"],
                            trader_goods,
                            ticks["ticksId"], ticks["price"], ticks["size"],
                            bt.Order.Market,
                            valid_ex=None,
                            parent=None,
                            stop_loss=ticks["stopLoss"],
                            take_profit=ticks["takeProfit"],
                            )

                    # 挂单操作
                    elif ticks["operate"] == "pendingOrder":
                        valid_ex = (
                                self.data.datetime.datetime(0) + datetime.timedelta(minutes=(datetime.datetime.strptime(
                                        ticks["valid"],'%Y-%m-%d %H:%M:%S') - self.data.datetime.datetime(0)
                                        ).total_seconds() // 60)) if ticks["valid"] else None

                        if ticks["type"] in [1, 2]:
                            self.execute_order(
                                ticks,
                                ticks["position"],
                                ticks["orderType"],
                                trader_goods,
                                ticks["ticksId"],
                                ticks["price"], ticks["size"], bt.Order.Limit,
                                valid_ex, stop_loss=ticks["stopLoss"],
                                take_profit=ticks["takeProfit"])

                        elif ticks["type"] in [3, 4]:
                            self.execute_order(
                                ticks,
                                ticks["position"],
                                ticks["orderType"],
                                trader_goods,
                                ticks["ticksId"], ticks["price"],
                                ticks["size"], bt.Order.Stop,
                                valid_ex, stop_loss=ticks["stopLoss"],
                                take_profit=ticks["takeProfit"])

    def notify_order(self, order):
        print('{}: Order ref: {} / Order Price: {} / Order value: {} / '
              'Order size: {}/ Type: {} / exectype:{} /Status: {} '.format(
            self.data.datetime.datetime(0),
            order.tradeid,
            order.executed.price,
            order.executed.value,
            order.executed.size,
            'Buy' * order.isbuy() or 'Sell',
            order.exectype,
            order.getstatusname()))

        # 未被处理的订单
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            ticks_id = order.info.get('ticksId', None)
            if order.isbuy():
                self.log(f'买入成交，价格：{order.executed.price}, 成交金额:{order.executed.value} '
                         f'数量：{order.executed.size}  订单号: {ticks_id}')
            elif order.issell():
                self.log(f'卖单成交，价格：{order.executed.price}, 成交金额:{order.executed.value} '
                         f'数量：{order.executed.size} 订单号: {ticks_id}')

        if order.status in [order.Margin, order.Rejected, order.Expired]:
            trader_goods = order.info.get('goods', None)
            takeProfit = order.info.get('takeProfit', 0.0)
            stopLoss = order.info.get('stopLoss', 0.0)
            klineId = order.info.get('klineId', 0)
            position = order.info.get('position', None)
            self.log('订单ref:{}/保证金不足/拒绝/订单已到期:'.format(order.ref))
            data_dict = dict()
            data_dict["ticksId"] = order.tradeid
            data_dict["traderGoods"] = trader_goods
            if position == 0:
                data_dict["position"] = "long"
            elif position == 1:
                data_dict["position"] = "short"
            else:
                data_dict["position"] = position
            data_dict["orderType"] = "buy" if order.ordtype == 0 else "sell"
            data_dict["size"] = order.size
            data_dict["tradeDateTime"] = str(self.data.datetime.datetime(0))
            data_dict["price"] = order.price
            data_dict["stopLoss"] = stopLoss
            data_dict["takeProfit"] = takeProfit
            data_dict["ExecType"] = order.exectype
            # 状态：Completed 表示订单完成 Margin 表示保证金不足 Rejected 表示订单拒绝 Expired 订单到期
            data_dict["statusReason"] = order.getstatusname(order.status)
            data_dict["pnl"] = 0
            data_dict["pnlcomm"] = 0
            data_dict["commission"] = 0
            data_dict["isclosed"] = False
            data_dict["klineId"] = klineId
            self.fail_trades.append(data_dict)

    # 交易状态通知，一买一卖算交易
    def notify_trade(self, trade):

        self.return_ = """
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
        # print("=======trader======")
        # print(trade)
        # print("=======trader======")
        open_data_dict = dict()
        if trade.isopen:  # 开仓
            # 遍历交易历史记录列表，获取每条交易的status信息
            for trade_history in trade.history:
                status_info = trade_history.status  # trader状态事件
                event_info = trade_history.event  # 订单事件
                trader_goods = event_info.order.info.get('goods', None)
                takeProfit = event_info.order.info.get('takeProfit', 0.0)
                stopLoss = event_info.order.info.get('stopLoss', 0.0)
                position = event_info.order.info.get('position', None)
                open_data_dict["ticksId"] = trade.tradeid
                open_data_dict["traderGoods"] = trader_goods
                if position == 0:
                    open_data_dict["position"] = "long"
                elif position == 1:
                    open_data_dict["position"] = "short"
                else:
                    open_data_dict["position"] = position
                open_data_dict["size"] = status_info.size
                open_data_dict["tradeDateTime"] = datetimesp(trade.dtopen)
                # OrdType: 0 = buy  1=sell 2
                open_data_dict["orderType"] = "buy" if event_info.order.ordtype == 0 else "sell"
                open_data_dict["price"] = status_info.price
                open_data_dict["stopLoss"] = stopLoss
                open_data_dict["takeProfit"] = takeProfit
                open_data_dict["commission"] = event_info.commission
                open_data_dict["isclosed"] = False
                # ExecType: 0 = market  2 = limit  3 = Stop
                open_data_dict["ExecType"] = event_info.order.exectype
                open_data_dict["statusReason"] = event_info.order.getstatusname(event_info.order.status)
                open_data_dict["pnl"] = round(status_info.pnl, 2)
                open_data_dict["pnlcomm"] = round(status_info.pnlcomm, 2)
                open_data_dict["klineId"] = event_info.order.info.get('klineId', 0)

                print("open_data_dict:{}".format(open_data_dict))

                self.trader_result.append(open_data_dict)

        if trade.isclosed:
            print("self.trader_result:{}".format(self.trader_result))
            # 遍历交易历史记录列表，获取每条交易的status信息
            target_trade = next((order for order in self.trader_result
                                 if order["ticksId"] == trade.tradeid), None)
            if target_trade:
                # 修改状态
                target_trade["isclosed"] = True
                target_trade["commission"] = trade.commission
                target_trade["pnl"] = round(trade.pnl, 2)
                target_trade["pnlcomm"] = round(trade.pnlcomm, 2)
                print("{}修改状态".format(trade.tradeid))

            else:
                # 交易成功
                status_info = [trader.status for trader in trade.history][0]
                event_info = [trader.event for trader in trade.history][0]
                position = event_info.order.info.get("position", None)
                open_data_dict["ticksId"] = trade.tradeid
                open_data_dict["traderGoods"] = event_info.order.info.get("goods", None)
                if position == 0:
                    open_data_dict["position"] = "long"
                elif position == 1:
                    open_data_dict["position"] = "short"
                else:
                    open_data_dict["position"] = position
                open_data_dict["size"] = status_info.size
                open_data_dict["tradeDateTime"] = datetimesp(trade.dtopen)
                open_data_dict["orderType"] = "buy" if event_info.order.ordtype == 0 else "sell"
                open_data_dict["price"] = status_info.price
                open_data_dict["stopLoss"] = event_info.order.info.get("stopLoss", 0.0)
                open_data_dict["takeProfit"] = event_info.order.info.get("takeProfit", 0.0)
                open_data_dict["commission"] = trade.commission
                open_data_dict["isclosed"] = True
                open_data_dict["ExecType"] = event_info.order.exectype
                open_data_dict["statusReason"] = event_info.order.getstatusname(event_info.order.status)
                open_data_dict["pnl"] = trade.pnl
                open_data_dict["pnlcomm"] = trade.pnlcomm
                open_data_dict["klineId"] = event_info.order.info.get('klineId', 0)

                print("close_data_dict:{}".format(open_data_dict))

                self.trader_result.append(open_data_dict)

                print(f'交易完成 ref:{trade.ref}  tradeid:{trade.tradeid} '
                      f'利润：{trade.pnl}, 数量：{trade.size}, 价格：{trade.price}')

    # 在策略结束时计算存款/提款
    def stop(self):
        pnl = round(self.broker.getcash() - self.starting_cash, 2)

        self.total_trader_result.append(
            {"tradeId": self.tradeId,
             "goodsTraderId":self.goodsTraderId,
             "summary": {"TotalDeposit": self.starting_cash,  # 总值
                         "initialCash": self.starting_cash,  # 本金
                         "FloatingPL": pnl,  # 盈亏
                         "commission": 0,  # 手续费
                         "FreeMargin": round(self.broker.getcash(), 2)},  # 可用资金
                         "openTrades": self.trader_result,
                         "FailTrades": self.fail_trades}
        )

        print("Strategy completed")

    def get_analysis(self):
        return self.total_trader_result


if __name__ == '__main__':
    # Instantiate Cerebro engine
    cerebro = bt.Cerebro()

    data = bt.feeds.YahooFinanceCSVData(dataname='CLTBAUDPI.csv')
    cerebro.adddata(data)

    # Add strategys to Cerebro
    cerebro.addstrategy(MyStrategy, params=[
        {'ticksId': '202400104', 'size': 1.0, 'type': 'buy', 'position': 'long', 'price': 2293.19, 'klineId': 371912},
        {'ticksId': '202400105', 'size': 2.0, 'type': 'sell', 'position': 'long', 'price': 2293.19, 'klineId': 371914},
        {'ticksId': '202400103', 'size': 10.0, 'type': 'buy', 'position': 'long', 'price': 2293.19,
         'klineId': 1114000}])

    # Run Cerebro Engine
    cerebro.run()
