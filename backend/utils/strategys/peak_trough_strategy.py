import math
import backtrader as bt
from utils.indicators.peak_trough import PeakTroughIndicator, PeakTroughType
from utils.time_utils import LZSDTimeUtils


class ResponsePeakTroughData(bt.Strategy):
    """
    顶底分型数据响应策略
    功能：计算顶底指标，生成前端绘图所需的数据结构（连线、文字注释、破坏点图标等）。
    """
    lines = ('pt_broken',)

    def __init__(self, indicator_params, indicator_name, comments, begin_time=None):
        # --- 初始化配置 ---
        self.indicator_params = indicator_params

        # 实例化自定义的顶底指标 (PeakTroughIndicator)
        self.peak_trough = PeakTroughIndicator(self.data)

        # --- 数据容器初始化 ---
        # 记录在逻辑判断中被认定为“破坏”或“失效”的顶底 ID
        self.broken_peak = []  # 失效的顶（连续出现两个顶时，前一个被视为失效）
        self.broken_trough = []  # 失效的底

        # 记录最终有效的笔生成的数据（用于画折线）
        self.line_data = []

        # --- 最终输出给前端的格式化数据 ---
        self.broken_trough_data = []  # 失效底的坐标数据（用于画图）
        self.broken_peak_data = []  # 失效顶的坐标数据（用于画图）
        self.peak_text_data = []  # 顶部的文字注释（价差、K线数等）
        self.trough_text_data = []  # 底部的文字注释

        # --- 状态变量 ---
        self.last_type = PeakTroughType.Normal  # 上一次记录的类型（顶或底）
        self.last_k_center_id = 0  # 上一次记录的K线ID

    def next(self):
        """
        每个Bar（K线）走完时调用一次。
        主要逻辑：实时检测指标输出，识别并记录“破坏/失效”的顶底结构。
        """
        # 获取当前K线的顶底指标值
        val = self.peak_trough.lines.pt_r[0]

        # 如果值不是 NaN，说明当前K线确认了一个顶或底
        if not math.isnan(val):
            # 判断当前是顶(>0)还是底(<=0)
            pt_type = PeakTroughType.Peak if val > 0 else PeakTroughType.Trough

            # 如果不是第一次记录 (Normal状态)
            if self.last_type != PeakTroughType.Normal:
                # 核心逻辑：如果当前类型与上一次类型相同（例如连续两个顶，或连续两个底）
                if self.last_type == pt_type:
                    # 说明上一次记录的点被“破坏”了，或者需要更新
                    if pt_type == PeakTroughType.Trough:
                        # 连续两个底，记录上一个底的ID为破坏底
                        self.broken_trough.append(self.last_k_center_id)
                    else:
                        # 连续两个顶，记录上一个顶的ID为破坏顶
                        self.broken_peak.append(self.last_k_center_id)

            # 更新状态为当前类型和ID
            self.last_type = pt_type
            self.last_k_center_id = self.peak_trough.pt_center[0]

    def _index_of_line_id(self, line_id):
        """
        辅助函数：根据自定义的 klineId 查找 Backtrader 数据序列中的索引。
        返回的是负数索引（相对于当前结束点的偏移量）。
        """
        line_count = len(self.data)
        # 倒序遍历查找
        for i in range(0 - line_count - 1, 1, 1):
            if line_id == self.data.klineId[i]:
                return i
        return None

    # def stop(self):
    #     """
    #     回测结束后调用一次。
    #     主要逻辑：遍历整个历史数据，整理最终的绘图数据（线段、文字、图标）。
    #     """
    #     line_count = len(self.data)
    #     index = 0  # 用于标记是第几个顶/底
    #
    #     # --- 第一步：遍历历史，生成连线数据 (line_data) 和 文字注释 (text_data) ---
    #     for i in range(0 - line_count - 1, 1, 1):
    #         pt_type_val = self.peak_trough.lines.pt_r[i]
    #
    #         # 找到确认为顶或底的K线
    #         if not math.isnan(pt_type_val):
    #             # 确定类型
    #             pt_type = PeakTroughType.Peak if pt_type_val > 0 else PeakTroughType.Trough
    #
    #             # 获取该顶底对应的中心K线ID
    #             center_line_id = self.peak_trough.lines.pt_center[i]
    #             # 反查该ID在数据中的索引
    #             center_line_index = self._index_of_line_id(center_line_id)
    #
    #
    #
    #             if center_line_index:
    #                 # 获取价格（顶取High，底取Low）
    #                 h = self.data.high[center_line_index]
    #                 l = self.data.low[center_line_index]
    #                 price = h if pt_type == PeakTroughType.Peak else l
    #
    #                 # 格式化时间戳
    #                 timestamp_str = LZSDTimeUtils.fmt(self.data.datetime.datetime(center_line_index))
    #
    #                 # 构造基础数据点
    #                 current_point = {
    #                     "kLineId": int(center_line_id),
    #                     "timestamp": timestamp_str,
    #                     "price": price,
    #                     "index": index  # 逻辑索引，第几个点
    #                 }
    #                 self.line_data.append(current_point)
    #
    #
    #                 # --- 计算波段差值（文字注释逻辑） ---
    #                 # 如果这已经是第二个点及以上，就可以计算与上一个点的差值了
    #                 if len(self.line_data) > 1:
    #                     prev_point = self.line_data[-2]  # 上一个点
    #
    #                     # 构造显示文本
    #                     # 1. 类型描述 (如: Peak1, Trough2) - 注意：这里原来代码是 str(pt_type) + str(index)
    #                     type_desc_str = str(pt_type) + str(index)
    #
    #                     # 2. 价格差 (绝对值，保留2位小数)
    #                     price_str = str(round(abs(price - prev_point["price"]), 2))
    #
    #                     # 3. K线间隔数 (当前点索引 - 上一个点索引)
    #                     k_interval_str = "K" + str(index - prev_point["index"])
    #
    #                     # print("price_str:{}".format(price_str))  # 调试打印
    #
    #                     # 组合文本：类型+索引 差价 间隔K线数 换行 时间
    #                     text = f"{type_desc_str} {price_str} {k_interval_str}\n{timestamp_str}"
    #
    #                     entity = {
    #                         "kLineId": int(center_line_id),
    #                         "timestamp": timestamp_str,
    #                         "price": price,
    #                         "value": text  # 用于前端显示的文本内容
    #                     }
    #
    #                     # 分类存入对应的文本列表
    #                     if pt_type == PeakTroughType.Peak:
    #                         self.peak_text_data.append(entity)
    #                     else:
    #                         self.trough_text_data.append(entity)
    #
    #         index += 1  # 索引递增
    #
    #     # --- 第二步：处理在 next() 中识别出的“破坏/失效”点数据 ---
    #     broken_data_array = [self.broken_trough, self.broken_peak]
    #     pt_type_array = [PeakTroughType.Trough, PeakTroughType.Peak]
    #     fill_data_array = [self.broken_trough_data, self.broken_peak_data]  # 目标填充列表
    #
    #     # 遍历底(0)和顶(1)
    #     for j in range(len(broken_data_array)):
    #         broken_data = broken_data_array[j]  # ID列表
    #         pt_type = pt_type_array[j]  # 类型
    #
    #         for k in range(len(broken_data)):
    #             center_line_id = broken_data[k]
    #
    #             # 反查坐标信息
    #             center_line_index = self._index_of_line_id(center_line_id)
    #             if center_line_index is not None:
    #                 h = self.data.high[center_line_index]
    #                 l = self.data.low[center_line_index]
    #
    #                 # 填充详细数据供前端画图（通常是画一个小箭头或叉号）
    #                 fill_data_array[j].append({
    #                     "kLineId": int(center_line_id),
    #                     "timestamp": LZSDTimeUtils.fmt(self.data.datetime.datetime(center_line_index)),
    #                     "price": l if pt_type == PeakTroughType.Trough else h,
    #                 })
    def stop(self):
        """
        回测结束后调用一次。
        主要逻辑：遍历整个历史数据，整理最终的绘图数据。
        """
        line_count = len(self.data)
        index = 0  # 用于标记是第几个顶/底

        broken_ids = set(self.broken_peak + self.broken_trough)

        # 第一部分：生成连线数据 (line_data) 和 文字注释
        for i in range(0 - line_count - 1, 1, 1):
            pt_type_val = self.peak_trough.lines.pt_r[i]
            # 找到确认为顶或底的K线
            if not math.isnan(pt_type_val):
                center_line_id = self.peak_trough.lines.pt_center[i]
                # 如果这个ID属于失效的顶/底，直接跳过。
                if center_line_id in broken_ids:
                    continue

                # 确定类型
                pt_type = PeakTroughType.Peak if pt_type_val > 0 else PeakTroughType.Trough

                # 反查该ID在数据中的索引
                center_line_index = self._index_of_line_id(center_line_id)

                if center_line_index:
                    # 获取价格（顶取High，底取Low）
                    h = self.data.high[center_line_index]
                    l = self.data.low[center_line_index]
                    price = h if pt_type == PeakTroughType.Peak else l

                    # 格式化时间戳
                    timestamp_str = LZSDTimeUtils.fmt(self.data.datetime.datetime(center_line_index))

                    # 构造基础数据点 -> 加入 line_data
                    current_point = {
                        "kLineId": int(center_line_id),
                        "timestamp": timestamp_str,
                        "price": price,
                        "index": index
                    }
                    self.line_data.append(current_point)

                    # --- 计算波段差值（文字注释逻辑） ---
                    # 这里的逻辑是自动适配的：因为 broken 点被上面 continue 过滤了，
                    # 所以 self.line_data[-2] 拿到的就是“上一个有效点”，差值计算完全正确。
                    if len(self.line_data) > 1:
                        prev_point = self.line_data[-2]  # 上一个点

                        # 构造显示文本
                        type_desc_str = str(pt_type) + str(index)
                        price_str = str(round(abs(price - prev_point["price"]), 2))
                        k_interval_str = "K" + str(index - prev_point["index"])  # 这里的间隔也是相对于上一个有效点的

                        text = f"{type_desc_str} {price_str} {k_interval_str}\n{timestamp_str}"

                        entity = {
                            "kLineId": int(center_line_id),
                            "timestamp": timestamp_str,
                            "price": price,
                            "value": text
                        }

                        if pt_type == PeakTroughType.Peak:
                            self.peak_text_data.append(entity)
                        else:
                            self.trough_text_data.append(entity)

                    # 只有有效点被记录了，索引才增加
                    index += 1

        # 第二部分：生成失效图标数据 (broken_data) - 【保持原样】
        broken_data_array = [self.broken_trough, self.broken_peak]
        pt_type_array = [PeakTroughType.Trough, PeakTroughType.Peak]
        fill_data_array = [self.broken_trough_data, self.broken_peak_data]

        for j in range(len(broken_data_array)):
            broken_data = broken_data_array[j]
            pt_type = pt_type_array[j]

            for k in range(len(broken_data)):
                center_line_id = broken_data[k]

                # 依然需要反查坐标来画“X”或图标
                center_line_index = self._index_of_line_id(center_line_id)
                if center_line_index is not None:
                    h = self.data.high[center_line_index]
                    l = self.data.low[center_line_index]

                    # 将失效点的数据填充进去，供前端画图
                    fill_data_array[j].append({
                        "kLineId": int(center_line_id),
                        "timestamp": LZSDTimeUtils.fmt(self.data.datetime.datetime(center_line_index)),
                        "price": l if pt_type == PeakTroughType.Trough else h,
                    })

    def get_analysis(self):
        """
        获取分析结果
        返回：符合前端渲染协议的字典列表。
        """
        result_data_dict = {}
        result_data_dict["lines"] = [
            # 1. 折线图数据 (ZigZag Line)
            {
                "type": "brokenline",
                "color": self.indicator_params.get("TrendPackconnectionColor", "#00FF00"),
                "data": self.line_data
            },
            # 2. 失效底部的图标标记 (Bitmap)
            {
                "type": "bmp",
                "arrow": self.indicator_params.get("peakBmp", 1),  # 这里命名可能是 peakBmp 对应 broken_trough，需确认业务逻辑
                "data": self.broken_trough_data
            },
            # 3. 失效顶部的图标标记 (Bitmap)
            {
                "type": "bmp",
                "arrow": self.indicator_params.get("bottolBmp", 2),
                "data": self.broken_peak_data
            },
            # 4. 顶部文本注释 (Text)
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'top',
                "data": self.peak_text_data
            },
            # 5. 底部文本注释 (Text)
            {
                "type": "text",
                "TextColor": self.indicator_params.get("TextColor", "#000000"),
                "BackgroundColor": self.indicator_params.get("BackgroundColor", "#FFF000"),
                "position": 'bottom',
                "data": self.trough_text_data
            },
        ]

        startime = None
        endtime = None
        # 返回格式：[数据行, 开始时间, 结束时间, 其他]
        return [result_data_dict["lines"], startime, endtime, None]