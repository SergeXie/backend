import backtrader as bt
import pandas as pd
from utils.common import PandasData, indicator_classes

def run_backtrader_strategy(
    trading_data,
    indicator_class_name,
    indicator_params,
    name,
    description,
    uid,
    pId,
    index,
    subType
):
    try:
        cerebro = bt.Cerebro()
        df = pd.DataFrame(trading_data)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        data = PandasData(dataname=df)
        cerebro.adddata(data)
        cerebro.addstrategy(indicator_classes.get(indicator_class_name),
                            indicator_params, name, description)
        result = cerebro.run(stdstats=True, tradehistory=True)
        result_data_list = result[0].get_analysis()
        return {
            "uid": uid,
            "pId": pId,
            "index": index,
            "parameter": indicator_params,
            "subType": subType,
            "startPoint": result_data_list[1],
            "endPoint": result_data_list[2],
            "buyselldata": result_data_list[3] if len(result_data_list[3:4]) > 0 else {},
            "data": result_data_list[0]
        }
    except Exception as e:
        import traceback
        print("回测异常:", traceback.format_exc())
        return {
            "uid": uid,
            "pId": pId,
            "index": index,
            "parameter": indicator_params,
            "subType": subType,
            "startPoint": None,
            "endPoint": None,
            "buyselldata": {},
            "data": []
        }