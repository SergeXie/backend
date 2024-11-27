# <start> 按下面的形式输入你的参数
# @param(key="NumericalDifference", type="float", title="packconnection NumericalDifference",defaultValue =1.0)
# @param(key="TrendPackconnectionColor", type="color", title="Trend PackconnectionColor",defaultValue ="#00FF00")
# <end>

from utils.public_strategy import CommonStrategy


class MyStrategy(CommonStrategy):

    def __init__(self, indicator_params):
        # 调用父类方法 （固定写法）
        super().__init__()
        # 接收参数示例
        # ND = indicator_params.get("NumericalDifference")

    def next(self):
        # 编写策略
        pass
    
    def stop(self):
        super().stop()


