from enum import IntEnum, Enum


class PeriodEnum(IntEnum):
    M1 = 1
    M5 = 5
    M15 = 15
    M30 = 30
    H1 = 60
    H4 = 240
    D1 = 1440
    W1 = 10080
    MN = 43800

    @staticmethod
    def parse_string(period_str):
        try:
            return getattr(PeriodEnum, period_str)
        except AttributeError:
            return None

    def is_higher_than_hour(self) -> bool:
        """判断是否是日线/周线/月线"""
        return self in {PeriodEnum.D1, PeriodEnum.W1, PeriodEnum.MN}

    def is_hour_based(self) -> bool:
        """判断是否是小时线"""
        return self in {PeriodEnum.H1, PeriodEnum.H4}


if __name__ == '__main__':
    # 访问 MN 成员
    mn_member = PeriodEnum.MN.name

    print(mn_member)