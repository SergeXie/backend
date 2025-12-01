
class Jin10CalendarUtils:

    @staticmethod
    def summarize_period(values: list[str]):
        """
        汇总周期数据
        values: ['open,high,low,close', ...]
        """
        records = []
        for v in values:
            if v and "," in v:
                try:
                    o, h, l, c = map(float, v.split(","))
                    records.append((o, h, l, c))
                except:
                    continue

        total = len(records)
        if total == 0:
            return None

        up = down = flat = 0
        up_changes = []
        down_changes = []
        ranges = []

        for o, h, l, c in records:
            change = c - o
            ranges.append(h - l)

            if change > 0:
                up += 1
                up_changes.append(change)
            elif change < 0:
                down += 1
                down_changes.append(change)
            else:
                flat += 1

        return {
            "total": total,            # 总次数
            "upCount": up,             # 涨次数
            "downCount": down,         # 跌次数
            "flatCount": flat,         # 持平次数
            "upProb": round(up / total, 3),
            "downProb": round(down / total, 3),
            "flatProb": round(flat / total, 3),
            "avgUpPoints": round(sum(up_changes) / len(up_changes), 3) if up_changes else 0,
            "avgDownPoints": round(sum(down_changes) / len(down_changes), 3) if down_changes else 0,
            "avgRange": round(sum(ranges) / len(ranges), 3),
        }
