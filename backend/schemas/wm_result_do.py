from schemas.base import Base
from sqlalchemy import Column, String, Integer, DateTime, JSON
import datetime

class WMPatternResult(Base):
    """
    用于存储计算出的 WM 形态结果
    """
    __tablename__ = 'dql_wm_patterns_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    goods = Column(String(50), index=True, nullable=False)
    period = Column(String(20), index=True, nullable=False)

    # 形态的关键时间点
    start_timestamp = Column(String(30))
    end_timestamp = Column(String(30), index=True)

    # 形态名称 (如: M形态, W1形态)
    pattern_title = Column(String(100))

    # 使用 JSON 类型存储完整的形态数据 (包含 points, target_klines 等)
    # MySQL 5.7+ 的 JSON 类型会自动处理序列化/反序列化
    detail_data = Column(JSON)

    created_at = Column(DateTime, default=datetime.datetime.now)