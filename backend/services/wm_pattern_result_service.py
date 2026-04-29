from dataclasses import fields
from typing import List, Optional

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.bt.tools.wm_pattern_recognizer import MaybeWPattern, MaybeMPattern, StandardWPattern
from schemas.wm_result_do import WMPatternResult

from loguru import logger

class WMPatternResultService:
    @classmethod
    async def get_data(cls, db: AsyncSession, goods: str, periods: str, end_time: str) -> List[WMPatternResult]:
        """
        根据商品、周期和时间上限获取形态记录
        :param db: 异步数据库 Session
        :param end_time: 筛选 end_timestamp <= 该值的数据
        """
        stmt = (
            select(WMPatternResult)
            .where(
                and_(
                    WMPatternResult.goods == goods,
                    WMPatternResult.period == periods,
                    WMPatternResult.end_timestamp <= end_time
                )
            )
            .order_by(WMPatternResult.end_timestamp.asc())
        )

        result = await db.execute(stmt)
        # scalars() 将结果集转换为模型对象列表
        return list(result.scalars().all())

    @classmethod
    async def get_latest_pattern(cls, db: AsyncSession, goods: str, periods: str) -> Optional[WMPatternResult]:
        """
        获取最后一条形态记录，用于确定增量计算的起始点
        """
        stmt = (
            select(WMPatternResult)
            .where(
                and_(
                    WMPatternResult.goods == goods,
                    WMPatternResult.period == periods
                )
            )
            .order_by(WMPatternResult.end_timestamp.desc())
            .limit(1)
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def clean_range(cls, db: AsyncSession, goods: str, periods: str, start_time: str, end_time: str):
        """
        清理特定时间段的数据（防止重叠计算导致数据重复）
        """
        stmt = (
            delete(WMPatternResult)
            .where(
                and_(
                    WMPatternResult.goods == goods,
                    WMPatternResult.period == periods,
                    WMPatternResult.end_timestamp >= start_time,
                    WMPatternResult.end_timestamp <= end_time
                )
            )
        )
        await db.execute(stmt)
        await db.flush()

    from dataclasses import fields, is_dataclass
    from typing import Optional, List, Type, Any

    @classmethod
    def _deserialize_pattern(cls, db_row: WMPatternResult) -> Optional[StandardPattern]:
        """
        修正版：修复变量名冲突，增强类型推导
        """
        data = db_row.detail_data or {}
        pattern_title = db_row.pattern_title or data.get('value', '')

        # 1. 映射配置 (使用不同名变量 _cls 避免覆盖类参数 cls)
        mapping: List[tuple[str, Type[StandardPattern]]] = [
            ('W3', MaybeWPattern),
            ('M3', MaybeMPattern),
            ('可能W', StandardWPattern),
            ('可能M', StandardMPattern),
            ('W', StandardWPattern),
            ('M', StandardMPattern),
        ]

        # 修改变量名为 _target_cls
        _target_cls = next((target for key, target in mapping if key in pattern_title), None)

        if not _target_cls or not is_dataclass(_target_cls):
            return None

        # 2. 字段提取 (使用显式的 fields 检查)
        target_fields = {f.name for f in fields(_target_cls)}
        init_kwargs = {k: v for k, v in data.items() if k in target_fields}

        # 3. 特殊字段处理：target_klines
        if 'target_klines' in target_fields:
            # 确保如果是从 JSON 加载出来的 None，转为空列表
            if init_kwargs.get('target_klines') is None:
                init_kwargs['target_klines'] = []

        # 4. 实例化
        try:
            # 显式返回，确保符合 Optional[StandardPattern]
            instance: StandardPattern = _target_cls(**init_kwargs)
            return instance
        except (TypeError, Exception) as e:
            # 可能是字段不匹配或数据格式错误
            logger.error(f"ID {getattr(db_row, 'id', 'New')} 反序列化失败: {e}")
            return None

    @classmethod
    async def add_bulk_data(cls, db: AsyncSession, patterns: List[WMPatternResult]):
        """
        批量保存形态数据
        """
        if not patterns:
            return

        # 批量添加对象
        db.add_all(patterns)
        # 注意：这里不执行 commit，建议由调用方统一 commit，或根据需求在此 commit
        await db.flush()

    @classmethod
    async def save_bulks(cls, db: AsyncSession, goods: str, periods: str, patterns: List[StandardPattern]):
        """
        将识别到的形态对象批量序列化并异步保存至数据库
        """
        if not patterns:
            return

        try:
            # 1. 使用列表推导式快速构建 ORM 对象列表
            orm_objects = [
                WMPatternResult(
                    goods=goods,
                    period=periods,
                    start_timestamp=p.start_timestamp,
                    end_timestamp=p.end_timestamp,
                    pattern_title=getattr(p, 'value', 'Unknown'),
                    # 将对象转为字典存入 JSON 字段，过滤掉不需要持久化的属性
                    detail_data=cls._serialize_obj(p)
                )
                for p in patterns
            ]

            # 2. 利用之前定义的 add_bulk_data 逻辑
            db.add_all(orm_objects)

            # 3. 异步提交
            await db.commit()
            logger.info(f"WM形态结构数据成功写入 {len(orm_objects)} 条记录 ({goods}/{periods})")

        except Exception as e:
            await db.rollback()
            logger.error(f"WM形态结构数据失败: {e}")
            # 这里建议重新抛出异常，让上层 run_strategy_incremental 知道保存失败
            raise e

    @staticmethod
    def _serialize_obj(p: StandardPattern) -> dict:
        """
        辅助方法：将 DataClass 对象转为可存入 JSON 的字典
        """
        from dataclasses import asdict
        d = asdict(p)
        # 如果 target_klines 数据量太大，可以选择不存入 detail_data 字段，
        # 或者根据你的需要保留
        return d


