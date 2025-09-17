import datetime
from utils.public_strategy import CommonStrategy


class PendulumTraderStrategy(CommonStrategy):

    def __init__(self, indicator_params, goodsId=None, begin_time=None, baseLots=0.1):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        # 保存昨日收盘价和收盘价
        self.pendulum_start_price = 0
        self.pendulum_end_price = 0

    def next(self):
        current_dt = self.datas[0].datetime.datetime(0)
        ts = current_dt
        if ts.time() > datetime.time(23, 0, 0) and self.pendulum_end_price == 0:
            self.pendulum_end_price = self.data.close[0]
        elif ts.time() > datetime.time(18, 0, 0) and self.pendulum_start_price == 0:
            self.pendulum_start_price = self.data.close[0]
        elif ts.time() > datetime.time(5, 0, 0):
            if self.position.size != 0:
                self.close()
                self.pendulum_start_price = 0
                self.pendulum_end_price = 0
        elif ts.time() > datetime.time(2, 0, 0):
            if self.position.size == 0:
                if self.pendulum_end_price > 0 and self.pendulum_start_price > 0:
                    if self.pendulum_end_price > self.pendulum_start_price:
                        self.sell(size=1)
                    else:
                        self.buy(size=1)