from typing import Optional, List
from fastapi import APIRouter, Query
from sqlalchemy import select
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.news_models import DqlJinshiEconomicNews, DqlJinshiMarketNews
from schemas.lzhc_news import EconomicNewsResponse, MarketNewsResponse

router = APIRouter()


@router.get("/economicNews")
async def get_economic_news(
    lastId: Optional[int] = Query(None, description="上次请求的最后ID"),
    dateValue: Optional[str] = Query(None, description="查询日期，例如 2025-09-26"),
    pageSize: Optional[int] = 100,

):
    """
    获取经济数据：
    - 如果传 dateValue：返回该日期的全部数据（可结合 lastId 翻页）
    - 如果不传 dateValue 且不传 lastId：返回最新 pageSize 条
    - 如果不传 dateValue 但传 lastId：返回 id > lastId 的 pageSize 条
    """
    async with async_db_session() as db:
        stmt = select(DqlJinshiEconomicNews)

        if dateValue:
            stmt = stmt.where(DqlJinshiEconomicNews.time.like(f"{dateValue}%")).order_by(
                DqlJinshiEconomicNews.time.asc())

        if lastId is None:
            # 第一次请求：最新 100 条（按 id DESC）
            stmt = stmt.order_by(DqlJinshiEconomicNews.time.asc()).limit(pageSize)
            result = await db.execute(stmt)
            rows = result.scalars().all()
        else:
            # 后续请求：id > last_id
            stmt = (
                select(DqlJinshiEconomicNews)
                .where(DqlJinshiEconomicNews.pkId > lastId)
                .order_by(DqlJinshiEconomicNews.time.asc())
                .limit(pageSize)
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


@router.get("/marketNews")
async def get_market_news(
    lastId: Optional[int] = Query(None, description="上次请求的最后ID"), pageSize: Optional[int] = 100):
    """
    获取市场快讯数据：
    - 第一次请求：不传 last_id，返回最新 100 条
    - 后续请求：传 last_id，返回 id > last_id 的 100 条
    """
    async with async_db_session() as db:
        if lastId is None:
            stmt = select(DqlJinshiMarketNews).order_by(DqlJinshiMarketNews.time.desc()).limit(pageSize)
            result = await db.execute(stmt)
            rows = result.scalars().all()

        else:
            stmt = (
                select(DqlJinshiMarketNews)
                .where(DqlJinshiMarketNews.pkId > lastId)
                .order_by(DqlJinshiMarketNews.time.desc())
                .limit(pageSize)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()

        # 返回Vo对象，响应时会自动解析json
        result = [
            MarketNewsResponse(
                pkId=row.pkId,
                time=row.time,
                content=row.content,
                createTime=row.createTime,
                updateTime=row.updateTime,
            )
            for row in rows
        ]

        return await response_base.success(data=result)