from datetime import datetime, timedelta
from typing import Optional, List

import requests
from fastapi import APIRouter, Query
from sqlalchemy import select, and_
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.news_models import DqlJinshiEconomicNews, DqlJinshiMarketNews, DqlJinshiHoliday, DqlJinshiEvent
from schemas.lzhc_news import EconomicNewsResponse, MarketNewsResponse, JinshiEventBase, JinshiHolidayBase
from utils.enum.period_enum import PeriodEnum

router = APIRouter()

def get_event_by_date(date_value: str):
    """
    通过 dateValue (YYYY-MM-DD) 获取财经日历数据
    """
    # 解析日期
    dt = datetime.strptime(date_value, "%Y-%m-%d %H:%M")
    year = dt.year
    month = dt.month
    day = dt.day

    # 拼接 URL
    url = f"https://cdn-rili.jin10.com/web_data/{year}/daily/{month:02d}/{day:02d}/event.json"
    print(f"请求 URL: {url}")

    # 请求数据
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


@router.get("/economicNews", name="日历数据")
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

        # 查询事件|假期 数据
        jinshi_event = select(DqlJinshiEvent).where(DqlJinshiEvent.eventTime.like(f"{dateValue}%")).order_by(
                DqlJinshiEvent.eventTime.asc()).limit(pageSize)
        jinshi_event_result = await db.execute(jinshi_event)
        jinshi_event_rows = jinshi_event_result.scalars().all()
        # 直接返回 Pydantic ORM 模型列表，FastAPI 会自动序列化
        events_data = [JinshiEventBase.from_orm(event).dict() for event in jinshi_event_rows]

        # 假期
        jinshi_holiday = select(DqlJinshiHoliday).where(DqlJinshiHoliday.holidayDate.like(f"{dateValue}%")).order_by(
            DqlJinshiHoliday.holidayDate.asc()).limit(pageSize)
        jinshi_holiday_result = await db.execute(jinshi_holiday)
        jinshi_holiday_rows = jinshi_holiday_result.scalars().all()

        holiday_data = [JinshiHolidayBase.from_orm(holiday).dict() for holiday in jinshi_holiday_rows]

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
            star=row.star,
            createTime=row.createTime,
            updateTime=row.updateTime,
        )
        for row in rows
    ]
    print(result)

    data = {"economic": result, "event": events_data, "holiday": holiday_data}

    return await response_base.success(data=data)


@router.get("/marketNews", name="快讯")
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


@router.get("/periodMarketNews", name="时间段内的市场快讯")
async def period_market_news(goods: str = Query(..., title="交易平台-交易品种"),
                             period: str = Query(..., title="周期"),
                             beginTime: str = Query(..., title="开始时间"),
                             endTime: str = Query(..., title="结束时间"),):

    async with async_db_session() as db:

        stmt = (
            select(DqlJinshiMarketNews)
            .where(
                and_(
                    DqlJinshiMarketNews.time >= beginTime,
                    DqlJinshiMarketNews.time < endTime
                )
            )
            .order_by(DqlJinshiMarketNews.time.asc())
        )

        result = await db.execute(stmt)
        rows = result.scalars().all()

        # 返回Vo对象，响应时会自动解析json
        results = [
            MarketNewsResponse(
                pkId=row.pkId,
                time=row.time,
                content=row.content,
                createTime=row.createTime,
                updateTime=row.updateTime,
            )
            for row in rows
        ]

        #  统计在时间范围内，每个周期（如 M5）有数据的时间段起点。
        time_list = []

        # 转成 datetime
        start_time = datetime.strptime(beginTime, '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(endTime, '%Y-%m-%d %H:%M:%S')

        results_time = sorted(
            [datetime.strptime(r.time, '%Y-%m-%d %H:%M:%S') for r in results]
        )
        print(results_time)

        idx = 0
        n = len(results_time)

        period = PeriodEnum.parse_string(period)
        if period:
            # 加周期
            delta = timedelta(minutes=period.value)

        while start_time < end_time:
            time1 = start_time
            time2 = time1 + delta

            # 统计该区间内的数据条数
            count = 0
            while idx < n and results_time[idx] < time2:
                if results_time[idx] >= time1:
                    count += 1
                idx += 1

            if count > 0:
                time_list.append(time1.strftime("%Y-%m-%d %H:%M:%S"))

            start_time = time2

        return await response_base.success(data=time_list)


@router.get("/marketNewsByPeriod", name="特定时间段快讯")
async def get_market_news_by_period(
    goods: str = Query(..., title="交易平台-交易品种"),
    beginTime: str = Query(..., description="开始时间，例如 2025-09-11 12:00:00"),
    period: str = Query("M5", description="周期，例如 M5 / M15 / H1")
):
    start_time = datetime.strptime(beginTime, '%Y-%m-%d %H:%M:%S')

    async with async_db_session() as db:
        period = PeriodEnum.parse_string(period)
        if period:
            # 加周期
            delta = timedelta(minutes=period.value)

        # 结束时间范围
        end_time = start_time + delta

        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

        stmt = (
            select(DqlJinshiMarketNews)
            .where(
                and_(
                    DqlJinshiMarketNews.time >= beginTime,
                    DqlJinshiMarketNews.time < end_time_str
                )
            )
            .order_by(DqlJinshiMarketNews.time.asc())
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
