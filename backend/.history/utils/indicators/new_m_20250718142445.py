import backtrader as bt
import numpy as np
import math
import random
import pandas as pd
from backtrader.feeds import PandasData

from utils.module.wm_pattern_recognizer import WMPatternRecognizer
from utils.module.zigzag_calculator import ZigZagCalculator


# 假设 ZigZagCalculator 和 WMPatternRecognizer 已经在当前文件中定义或已导入

class ResponseWMpredictData(bt.Strategy):
    # 定义参数
    params = (
        ('inp_depth', 12),
    )

    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data_dict = dict()

        # 实例化独立的算法类
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.p.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer()

        # 确保数据长度足够时再开始计算
        self.addminperiod(self.p.inp_depth)

    def next(self):
        # 确保数据长度足够
        if len(self) < self.p.inp_depth:
            return

        # 准备当前K线数据，传递给ZigZagCalculator
        current_kline_data = {
            "kLineId": self.data.klineId[0],  # 假设datafeed提供了klineId
            "timestamp": self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S'),
            "open": self.data.open[0],
            "high": self.data.high[0],
            "low": self.data.low[0],
            "close": self.data.close[0],
            "volume": self.data.volume[0],
        }

        # 调用ZigZag算法类的处理方法
        # process_kline会返回是否产生了新的zigzag点，如果产生，就通知形态识别器
        new_zigzag_point_or_updated = self.zigzag_calculator.process_kline(current_kline_data)

        # # 如果ZigZag有更新，就通知形态识别器进行分析
        # if new_zigzag_point_or_updated:
        #     zigzag_points = self.zigzag_calculator.get_zigzag_points()
        #     print("zigzag_points:", len(zigzag_points))
        #     dict_index2ts, dict_ts2index = self.zigzag_calculator.get_index_timestamp_maps()
        #     self.pattern_recognizer.analyze_zigzag_points(zigzag_points, dict_index2ts, dict_ts2index)
    def stop(self):
        zigzag_points = self.zigzag_calculator.get_zigzag_points()
        for zig in zigzag_points:
            print(zig)
        return super().stop()


    def get_analysis(self):
        # 组织数据结构，从独立的算法类获取数据
        zigzag_points = self.zigzag_calculator.get_zigzag_points()

        self.result_data_dict["lines"] = [
            # {
            #     "type": "text",
            #     "TextColor": self.indicator_params.get("TextColor", "#000000"),
            #     "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
            #     "position": 'top',
            #     "data": pattern_titles
            # },
            # {
            #     "type": "picture",  # 假设'picture'是您自定义的一种绘图类型，用于M/W形态
            #     "data": formatted_m_w_patterns
            # },
            {
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FFFF"),
                "data": zigzag_points
            },
        ]
        
        return [self.result_data_dict["lines"], None , None]

