from typing import Optional, List
from fastapi import APIRouter, Query
from sqlalchemy import select
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.news_models import DqlJinshiEconomicNews
from schemas.lzhc_news import EconomicNewsResponse

router = APIRouter()


@router.get("/economicNews")
async def get_economic_news(
    lastId: Optional[int] = Query(None, description="上次请求的最后ID")):
    """
    获取经济数据：
    - 第一次请求：不传 last_id，返回最新 100 条
    - 后续请求：传 last_id，返回 id > last_id 的 100 条
    """
    async with async_db_session() as db:
        if lastId is None:
            # 第一次请求：最新 100 条（按 id DESC）
            stmt = select(DqlJinshiEconomicNews).order_by(DqlJinshiEconomicNews.pkId.desc()).limit(100)
            result = await db.execute(stmt)
            rows = result.scalars().all()
            rows = list(reversed(rows))  # 翻转成正序返回
        else:
            # 后续请求：id > last_id
            stmt = (
                select(DqlJinshiEconomicNews)
                .where(DqlJinshiEconomicNews.pkId > lastId)
                .order_by(DqlJinshiEconomicNews.pkId.asc())
                .limit(100)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()

    # 返回Vo对象，响应时会自动解析json
    result = [
        EconomicNewsResponse(
            pkId=row.pkId,
            time=row.time,
            name=row.name,
            affects=row.affects,
            prevValue=row.prevValue,
            expectValue=row.expectValue,
            publishValue=row.publishValue,
            createTime=row.createTime,
            updateTime=row.updateTime,
        )
        for row in rows
    ]

    return await response_base.success(data=result)

