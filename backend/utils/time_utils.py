import datetime


def _fmt_time(src, fmt):
    try:
        return src.strftime(fmt)
    except Exception as _:
        return ""

class LZSDTimeUtils:
    @staticmethod
    def fmt(src:datetime):
        return _fmt_time(src=src, fmt='%Y-%m-%d %H:%M:%S')

    @staticmethod
    def fmt_iso(src:datetime):
        return _fmt_time(src=src, fmt='%Y-%m-%d %H:%M')

    @staticmethod
    def fmt_date(src:datetime):
        return _fmt_time(src=src, fmt='%Y-%m-%d')