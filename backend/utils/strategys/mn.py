# <start> 按下面的形式输入你的参数
# @param(key="NumericalDifference", type="float", title="packconnection NumericalDifference",defaultValue =1.0)
# @param(key="TrendPackconnectionColor", type="color", title="Trend PackconnectionColor",defaultValue ="#00FF00")
# <end>

from utils.public_strategy import CommonStrategy


class MnStrategy(CommonStrategy):

    def __init__(self, indicator_params, goodsId=None, begin_time=None):
        # 调用父类方法 （固定写法）
        super().__init__(goodsId)
        # 接收参数示例
        # ND = indicator_params.get("NumericalDifference")

    def next(self):
        if len(self) % 2 == 0 and len(self) != 0:
            self.order = self.close(size=0.1)  # 平仓，以下一日开盘价卖出
        elif len(self) % 2 == 1 and len(self) != 0:
            self.order = self.sell(size=0.1)
        # 编写策略
        pass
    
    def stop(self):
        super().stop()


