import backtrader as bt
import pandas as pd
import pymysql

# 周期
period = "M15"
# 交易品种
tradingGoods = "XAUUSD"
# 连接到数据库
conn = pymysql.connect(
    host='192.168.0.126',
    user='cmdb',
    password='cmdb123456',
    database='dql'
)

# 创建游标对象
cursor = conn.cursor()
# 执行查询
query = (f"SELECT * FROM dql_trading_fpg WHERE type='{period}' AND "
         f"tradingGoods='{tradingGoods}' AND "
         f"tradeDateTime >= '2024-06-28' AND tradeDateTime <= '2024-07-01' "
         f"ORDER BY tradeDateTime DESC")

cursor.execute(query)
# 获取查询结果
results = cursor.fetchall()
results = reversed(results)
# 关闭游标和连接
cursor.close()
conn.close()

# 从CSV文件加载数据源
results_data_list = [{"pkId": x[0], "datetime": x[4].strftime("%Y-%m-%d %H:%M:%S"), "open": float(x[9]),
                      "high": float(x[11]), "low": float(x[12]), "close": float(x[10]),
                      "volume": x[13], "openinterest": 0, "klineId": x[0],
                      "digits": x[5], "spread": x[6]} for x in results]


class PandasData(bt.feeds.PandasData):
    lines = ('pkId', 'open', 'high', 'low', 'close', 'volume', 'openinterest', 'klineId')
    params = (
        ('pkId', -1),
        ('open', -1),
        ('high', -1),
        ('low', -1),
        ('close', -1),
        ('volume', -1),
        ('openinterest', None),
        ('klineId', -1),
    )


class BaseStrategy(bt.Strategy):
    params = (
        ('name', None),  # 策略名称
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime()
        print(f'{dt} - {txt}')

    def __init__(self):
        self.order = None

    def notify_order(self, order):
        if order.status in [order.Completed]:
            current_datetime = self.datas[0].datetime.datetime(0)
            if order.isbuy():
                self.log(f'策略名称:{order.info.strategy_name} 买入订单执行完成, 价格: {order.executed.price}, 总值: {order.executed.value}, '
                         f'佣金: {order.executed.comm} 交易时间: {current_datetime}')
            elif order.issell():
                self.log(f'策略名称:{order.info.strategy_name} 卖出订单执行完成, 价格: {order.executed.price}, 总值: {order.executed.value}, '
                         f'佣金: {order.executed.comm} 交易时间：{current_datetime}')

        self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            event_info = [trader.event for trader in trade.history][0]
            print(f"策略名称：{event_info.order.info.get('strategy_name', None)} 交易完成，利润：{trade.pnl:.2f}, "
                  f"数量：{trade.size}, 价格：{trade.price:.2f} 交易时间：{self.data.datetime.datetime()}")

    def stop(self):
        cash = self.broker.get_cash()
        value = self.broker.get_value()
        total_position_value = value - cash

        print(f'策略{self.params.name} 回测结束时的现金余额: {cash:.2f}')
        print(f'策略{self.params.name} 回测结束时的净值: {value:.2f}')
        print(f'策略{self.params.name} 回测结束时的总持仓市值: {total_position_value:.2f}')

        for data in self.datas:
            position = self.getposition(data)
            if position.size != 0:
                print(f'策略{self.params.name} 资产: {data._name}, 持仓数量: {position.size}, '
                      f'持仓价格: {position.price:.2f}, '
                      f'当前市值: {position.size * data.close[0]:.2f}')


# 定义第一个策略类：均线交叉策略
# 当短期均线（短期周期设为10）上穿长期均线（长期周期设为30）时买入；当短期均线下穿长期均线时卖出。
class MovingAverageCrossStrategy(BaseStrategy):
    params = (
        ('short_period', 20),  # 短期均线周期
        ('long_period', 50),  # 长期均线周期
        ('name', None),  # 策略名称
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime()
        print(f'{dt} - {txt}')

    def __init__(self):
        self.short_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.short_period)
        self.long_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.long_period)

        self.order = None

    def next(self):
        stop_loss = self.data.open[0] + 2
        if not self.position:  # 如果没有持仓
            if self.short_ma > self.long_ma:
                self.order = self.buy(size=0.1)
                self.order.addinfo(strategy_name=self.params.name, stopLoss=stop_loss, takeProfit=0)

        elif self.short_ma < self.long_ma:
            self.order = self.sell(size=0.1)
            self.order.addinfo(strategy_name=self.params.name, stopLoss=stop_loss, takeProfit=0)


# 定义第二个策略类：布林带突破策略
# 当价格突破布林带上轨时买入；当价格跌破布林带下轨时卖出。
class BollingerBandsStrategy(BaseStrategy):
    params = (
        ('period', 20),  # 布林带周期
        ('devfactor', 2),  # 标准差倍数
        ('name', None),  # 策略名称

    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime()
        print(f'{dt} - {txt}')

    def __init__(self):
        self.bollinger = bt.indicators.BollingerBands(
            self.data.close, period=self.params.period, devfactor=self.params.devfactor)

        self.order = None

    def next(self):
        stop_loss = self.data.open[0] + 2
        if not self.position:  # 如果没有持仓
            if self.data.close > self.bollinger.lines.top:
                self.order = self.buy()  # 价格突破布林带上轨，买入
                self.order.addinfo(strategy_name=self.params.name, stopLoss=stop_loss, takeProfit=0)

        elif self.data.close < self.bollinger.lines.bot:
            self.order = self.sell()  # 价格跌破布林带下轨，卖出
            self.order.addinfo(strategy_name=self.params.name, stopLoss=stop_loss, takeProfit=0)


if __name__ == '__main__':
    # 添加 backtrader 大脑
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(10000.0)
    # 添加数据源
    df = pd.DataFrame(results_data_list)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    data = PandasData(dataname=df)

    # 添加数据源
    cerebro.adddata(data)
    data._name = "XAUUSD"  # 给数据源命名、

    # 添加两个独立的策略类到 Cerebro 引擎
    cerebro.addstrategy(MovingAverageCrossStrategy, short_period=5, long_period=10, name="StrategyA")
    cerebro.addstrategy(BollingerBandsStrategy, period=20, devfactor=1.5, name="StrategyB")

    result = cerebro.run(stdstats=True, tradehistory=True)

    # 回测结束后还可以通过cerebro来获取总净值
    final_value = cerebro.broker.getvalue()
    print(f'回测结束时的总净值: {final_value:.2f}')