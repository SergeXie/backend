import backtrader as bt
import numpy as np

from common.conf import settings
from core.bt.tools.zigzag_calculator_byclass import ZigZagCalculator
from core.bt.tools.wm_pattern_recognizer import WMPatternRecognizer2
from core.bt.indicators.wm_predict_bymath import get_klines_in_range
from core.ai.ai_rest_client import call_dl_api2
from core.ai.t2 import extract_xdata

# 过滤特定警告


class ResWMpredictByModelData(bt.Strategy):
    # 定义参数
    params = (
        ('inp_depth', 12),
    )

    def __init__(self, indicator_params, indicator_name, comments):
        self.indicator_params = indicator_params
        self.indicator_name = indicator_name
        self.comments = comments
        self.result_data_dict = dict()
        self.Id_TS_dict = {}

        self.BarState = []
        self.BarStateText = []
        self.BarStateText1 = []
        self.verticalBrokenline = []
        self.W_sum = 0
        self.M_sum = 0
        self.all_kline_data = []
        self.Ts_to_hloc = {}

        self.kline_goods = self.indicator_params.get("Kline_goods", '')
        self.kline_period = self.indicator_params.get("Kline_period", '')
        self.end_time = self.indicator_params.get("end_time", '')
        self.begin_time = self.indicator_params.get("begin_time", '')

        # ----------
        # 参数 # 0为指标,1为模型
        self.wm_from = self.indicator_params.get('WMfrom', 1)
        self.pre_from = self.indicator_params.get('Prefrom', 1)
        # ---------

        # 实例化独立的算法类
        self.zigzag_calculator = ZigZagCalculator(inp_depth=self.p.inp_depth)
        self.pattern_recognizer = WMPatternRecognizer2()

        # 确保数据长度足够时再开始计算
        self.addminperiod(self.p.inp_depth)

    def next(self):
        self.Id_TS_dict[int(self.data.klineId[0])] = self.datas[0].datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')

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
        self.all_kline_data.append(current_kline_data)
        self.Ts_to_hloc[self.data.datetime.datetime(0).strftime('%Y-%m-%d %H:%M:%S')] = [self.data.high[0],
                                                                                         self.data.low[0],
                                                                                         self.data.open[0],
                                                                                         self.data.close[0]]

        # 调用ZigZag算法类的处理方法
        # process_kline会返回是否产生了新的zigzag点，如果产生，就通知形态识别器
        new_zigzag_point_or_updated = self.zigzag_calculator.process_kline(current_kline_data)

    def stop(self):
        digit = int(self.datas[0].digits[0])
        zigzag_points = self.zigzag_calculator.get_zigzag_points(as_dict=False)

        zigzag_list = []
        for zig in zigzag_points:
            zigzag_list.append(zig)
            self.pattern_recognizer.analyze_zigzag_points(zigzag_list)
        # 获取非形态数据
        # wm_pattern = self.pattern_recognizer.get_all_none_patterns()
        # for pattern in wm_pattern:
        #     # 获取该模式时间范围内的所有K线
        #     target_klines = get_klines_in_range(
        #         all_klines=self.all_kline_data,  # 替换为实际的全量K线数据
        #         start_timestamp=pattern['start_timestamp'],
        #         end_timestamp=pattern['end_timestamp']
        #     )
        #     pattern['target_klines'] = target_klines
        #     pattern['period'] = "None"
        #
        # print('空的',len(wm_pattern))
        #
        # with open('./dataset/all_no_pattern_kline_M30.pkl', 'wb') as file:
        #     pickle.dump(wm_pattern, file)
        # pass
        # # 加载数据
        # with open('./dataset/all_no_pattern_kline_H4.pkl', 'rb') as file:
        #     h4 = pickle.load(file)
        # with open('./dataset/all_no_pattern_kline_H1.pkl', 'rb') as file:
        #     h1 = pickle.load(file)
        # with open('./dataset/all_no_pattern_kline_M5.pkl', 'rb') as file:
        #     m5 = pickle.load(file)
        # with open('./dataset/all_no_pattern_kline_M15.pkl', 'rb') as file:
        #     m15 = pickle.load(file)
        # with open('./dataset/all_no_pattern_kline_M30.pkl', 'rb') as file:
        #     m30 = pickle.load(file)
        # print(type(h4), len(h1), len(m5), len(m15), len(m30))
        #
        # all = m5+m15+m30+h1+h4
        # with open('./dataset/all_no_pattern_kline.pkl', 'wb') as file:
        #     pickle.dump(all, file)
        #
        # pass

        # 加载wm形态

        # 指标时间段内的全部形态
        all_5point = self.pattern_recognizer.get_all_5point_list()
        for pattern in all_5point:
            # 获取该模式时间范围内的所有K线
            target_klines = get_klines_in_range(
                all_klines=self.all_kline_data,  # 替换为实际的全量K线数据
                start_timestamp=pattern.start_timestamp,
                end_timestamp=pattern.end_timestamp
            )
            pattern.target_klines = target_klines
            # pattern['target_klines'] = target_klines
            pattern.period = "none"
            # pattern['period'] = "none"

        print('加载保存的数据')


        #  ----------------------------------------这里先预测是否是形态--------------------------------
        test_x = extract_xdata(all_5point)
        request_data = {
            "test_x": test_x.tolist(),
            "model": 'pre_status'
        }

        # 发送预测请求
        print('正在请求形态分类')
        response = call_dl_api2(
            url=settings.AI_URL,
            task='wm_predic_v2',
            goods=self.kline_goods,
            period=self.kline_period,
            begin_time=self.begin_time,
            end_time=self.end_time,
            data=request_data,
            timeout=120.0,
        )
        if response.get('status_code') == 200:
            print('接口请求正常')

        y_pred_prob = response['y_pred_prob']
        print(y_pred_prob)

        # print(len(y_pred_prob))
        # print(y_pred_prob)
        predict_wm_pattern = []

        maybe_w = None
        maybe_m = None
        for index, p_list in enumerate(y_pred_prob):
            max_value = np.max(p_list)  # 获取最大值
            max_index = np.argmax(p_list)
            if max_index != 0:
                predict_wm_pattern.append(all_5point[index])
                # print(max_index)
                if max_index == 1:
                    maybe_m = all_5point[index]
                elif max_index == 2:
                    maybe_w = all_5point[index]

        print('模型计算形态')
        print('====================')

        # --------------------------------------------------------------------------------------------
        # if self.wm_from == 0:  # 0:math
        #     print('指标计算形态')
        #     maybe_m = self.pattern_recognizer.get_maybe_m_patterns()[-1]
        #     maybe_w = self.pattern_recognizer.get_maybe_w_patterns()[-1]
        #     for pattern in [maybe_m, maybe_w]:
        #         # 获取该模式时间范围内的所有K线
        #         target_klines = get_klines_in_range(
        #             all_klines=self.all_kline_data,  # 替换为实际的全量K线数据
        #             start_timestamp=pattern['start_timestamp'],
        #             end_timestamp=pattern['end_timestamp']
        #         )
        #         pattern['target_klines'] = target_klines
        #         pattern['period'] = "none"
        #     predict_wm_pattern = [maybe_m, maybe_w]
        # elif self.wm_from == 1:
        #     print('模型计算形态')

        # all_wm_pattern_kline = [klines_to_dataframe(merge_klines(i['target_klines'])) for i in all_wm_pattern]
        # ----------------------------------指标计算概率-----------------------------------------
        # if self.pre_from == 0:
        #     print('指标计算概率')
        #     try:
        #         last_m_start = maybe_m['start']
        #         last_m_end = maybe_m['end']
        #         last_m_kline = get_klines_in_range(self.all_kline_data, last_m_start, last_m_end)
        #         last_m_kline_df = klines_to_dataframe(merge_klines(last_m_kline))
        #         distance = [calc_dtw_distance(last_m_kline_df, i) for i in all_wm_pattern_kline]
        #         weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
        #         m_zigzag_points = [i['points'] for i in all_wm_pattern if "M" in i['pattern_type']]
        #         weight = [weight[index] for index, i in enumerate(all_wm_pattern) if "M" in i['pattern_type']]
        #         p = probability(m_zigzag_points, datafrom='m', weight=weight)
        #         print("m概率:", p)
        #         price_diff = self.Ts_to_hloc.get(maybe_m['start_third'])[1] - \
        #                      self.Ts_to_hloc.get(maybe_m['start_four'])[0]  # 高点到低点的价差
        #         klineId = maybe_m['kLineId_3']
        #         self.BarStateText1.append({
        #             "kLineId": maybe_m['points'][2]['kline_data']['kLineId'],
        #             "price": maybe_m['points'][2]['kline_data']['price'],
        #             "timestamp": self.Id_TS_dict.get(maybe_m['points'][2]['kline_data']['kLineId']),
        #             "value": 'M形态'
        #         })
        #         for index, i in enumerate(p['probabilities']):
        #             base_price = self.Ts_to_hloc.get(maybe_m['start_third'])[1]
        #             price = base_price + price_diff * index
        #             price = np.round(price, digit)
        #             # print(i)
        #             i = np.round(i * 100, 2)
        #             # print('来了', price,self.Id_TS_dict.get(klineId))
        #             # print(index)
        #
        #             self.BarStateText.append({
        #                 "kLineId": klineId,
        #                 "price": price,
        #                 "timestamp": self.Id_TS_dict.get(klineId),
        #                 "value": f"{np.round(price, 2)}: " + str(i) + '%'
        #             })
        #             self.BarState.append([
        #                 {
        #                     "kLineId": int(klineId),
        #                     "price": price,
        #                 },
        #                 {
        #                     "kLineId": int(klineId),
        #                     "price": price,
        #                 }
        #             ])
        #         # -----------------------w计算概率-----------------------------------------
        #         last_w_start = maybe_w['start']
        #         last_w_end = maybe_w['end']
        #         last_w_kline = get_klines_in_range(self.all_kline_data, last_w_start, last_w_end)
        #         last_w_kline_df = klines_to_dataframe(merge_klines(last_w_kline))
        #         distance = [calc_dtw_distance(last_w_kline_df, i) for i in all_wm_pattern_kline]
        #         weight = convert_to_weight(distance)  # 计算得到最后一个可能的m与历史的权重
        #         w_zigzag_points = [i['points'] for i in all_wm_pattern if "W" in i['pattern_type']]
        #         weight = [weight[index] for index, i in enumerate(all_wm_pattern) if "W" in i['pattern_type']]
        #         p = probability(w_zigzag_points, datafrom='w', weight=weight)
        #         print("w概率:", p)
        #         price_diff = self.Ts_to_hloc.get(maybe_w['start_third'])[0] - \
        #                      self.Ts_to_hloc.get(maybe_w['start_four'])[1]  # 高点到低点的价差
        #         klineId = maybe_w['kLineId_3']
        #         self.BarStateText1.append({
        #             "kLineId": maybe_w['points'][2]['kline_data']['kLineId'],
        #             "price": maybe_w['points'][2]['kline_data']['price'],
        #             "timestamp": self.Id_TS_dict.get(maybe_w['points'][2]['kline_data']['kLineId']),
        #             "value": 'W形态'
        #         })
        #         for index, i in enumerate(p['probabilities']):
        #             base_price = self.Ts_to_hloc.get(maybe_w['start_third'])[0]
        #             price = base_price + price_diff * index
        #             price = np.round(price, digit)
        #             # print(i)
        #             i = np.round(i * 100, 2)
        #             # print('来了', price,self.Id_TS_dict.get(klineId))
        #             # print(index)
        #
        #             self.BarStateText.append({
        #                 "kLineId": klineId,
        #                 "price": price,
        #                 "timestamp": self.Id_TS_dict.get(klineId),
        #                 "value": f"{np.round(price, 2)}: " + str(i) + '%'
        #             })
        #             self.BarState.append([
        #                 {
        #                     "kLineId": int(klineId),
        #                     "price": price,
        #                 },
        #                 {
        #                     "kLineId": int(klineId),
        #                     "price": price,
        #                 }
        #             ])
        #     except Exception as e:
        #         print(e)

        #  ----------------------------------------模型预测价差--------------------------------
        if self.pre_from == 1:
            # 发送预测请求
            # print('正在请求新的接口')
            # response = call_dl_api2(
            #     # url=settings.AI_URL,
            #     url='http://192.168.1.182:8083/api/ai/myai',
            #     task='wm_train_model',
            #     goods=self.kline_goods,
            #     period=self.kline_period,
            #     begin_time=self.begin_time,
            #     end_time=self.end_time,
            #     data={},
            #     timeout=120.0,
            # )

            print('模型计算概率')
            test_x = extract_xdata(predict_wm_pattern)
            request_data = {
                "test_x": test_x.tolist(),
                "model": 'pre_diff'
            }
            # 发送预测请求
            print('正在请求概率计算')
            response = call_dl_api2(
                # url=settings.AI_URL,
                url='http://192.168.1.60:8083/api/ai/myai',
                task='wm_predic_v3',
                goods=self.kline_goods,
                period=self.kline_period,
                begin_time=self.begin_time,
                end_time=self.end_time,
                data=request_data,
                timeout=120.0,
            )
            if response.get('status_code') == 200:
                print('概率计算正常')

            diff_results = response['diff_results']
            patterns = response['patterns']

            print(diff_results)
            print(patterns)

            for index, p_list in enumerate(diff_results):
                print(index, p_list)
                self.probabilities_result_add(predict_wm_pattern[index], p_list, patterns[index])

        return super().stop()

    def get_analysis(self):

        # 组织数据结构，从独立的算法类获取数据
        zigzag_points = self.zigzag_calculator.get_zigzag_points()
        self.result_data_dict["lines"] = [
            {
                "type": "brokenline",
                "color": self.indicator_params.get("UpColor", "#00FFFF"),
                "data": zigzag_points
            },
        ]
        # 画横线
        for i in self.BarState:
            self.result_data_dict["lines"].append({
                "type": "graphical",
                "BackgroundColor": self.indicator_params.get("TrendDMAColor", "#0000FF"),
                "lineWidth": 1,
                "lineStyle": 1,
                "color": "#FFFFFF",
                "globalAlpha": 0.1,
                "data": i
            })
        # 写概率
        for i in self.BarStateText:
            # print(i)
            self.result_data_dict["lines"].append({
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                "position": 'right',
                "data": [i],
            })
        # 写形态
        for i in self.BarStateText1:
            # print(i)
            self.result_data_dict["lines"].append({
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#0000FF"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFFFFF"),
                "position": 'top',
                "data": [i],
            })
        # 画竖线
        for i in self.verticalBrokenline:
            self.result_data_dict["lines"].append({
                "type": "verticalBrokenline",
                "color": self.indicator_params.get("FFFF00", "#FFFF00"),
                "data": [i]
            })

        self.result_data_dict["lines"].append({
            "type": "bottomText",
            "color": self.indicator_params.get("DnColor", "#FF0000"),
            "data": f"W形态个数: {self.W_sum}, M形态个数: {self.M_sum},"
        })
        return [self.result_data_dict["lines"], None, None]

    def probabilities_result_add(self, status, probabilities, patterns):
        # print('绘制概率的结果',status)
        points_list = status.points
        points_4 = points_list[3]
        points_3 = points_list[2]
        base_price = points_3['kline_data'].price
        price_diff = points_4['kline_data'].price - base_price

        klineId = points_4['kline_data'].kLineId
        value_str = patterns

        for index, i in enumerate(probabilities):
            price = base_price - price_diff * index

            self.BarStateText1.append({
                "kLineId": points_3['kline_data'].kLineId,
                "price": points_3['kline_data'].price,
                "timestamp": self.Id_TS_dict.get(points_3['kline_data'].kLineId),
                "value": value_str
            })
            self.BarStateText.append({
                "kLineId": klineId,
                "price": price,
                "timestamp": self.Id_TS_dict.get(klineId),
                "value": f"{np.round(price, 2)}: " + str(np.round(i * 100, 2)) + '%'
            })
            self.BarState.append([
                {
                    "kLineId": int(klineId),
                    "price": price,
                },
                {
                    "kLineId": int(klineId),
                    "price": price,
                }
            ])
        self.verticalBrokenline.append(
            {
                "kLineId": klineId,
                "price": price,
                "price2": [base_price + price_diff, base_price - price_diff * 2],
                "timestamp": self.Id_TS_dict.get(klineId),
            })
