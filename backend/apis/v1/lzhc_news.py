from datetime import datetime, timedelta
from typing import Optional
import requests
from fastapi import APIRouter, Query
from pydantic import Field
from sqlalchemy import select, and_, outerjoin, func
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.news_models import DqlJinshiEconomicNews, DqlJinshiMarketNews, DqlJinshiHoliday, DqlJinshiEvent, \
    MarketStatistics, DqlJinshiNewsClass
from schemas.lzhc_news import EconomicNewsResponse, MarketNewsResponse, JinshiEventBase, JinshiHolidayBase, \
    MarketStatisticsOut
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
    startTime: Optional[str] = Query(None, description="开始时间，例如 2025-09-26 00:00:00"),
    endTime: Optional[str] = Query(None, description="结束时间，例如 2025-09-26 23:59:59"),
    pageNo: Optional[int] = Query(1, description="当前页码，从1开始"),
    pageSize: Optional[int] = Query(100, description="每页条数"),
    keyword: Optional[str] = Query(None, description="日历搜索关键字")

):
    """
    获取经济数据：
    - 如果传 dateValue：返回该日期的全部数据（可结合 lastId 翻页）
    - 如果不传 dateValue 且不传 lastId：返回最新 pageSize 条
    - 支持按 startTime ~ endTime 查询时间段
    - 如果不传 dateValue 但传 lastId：返回 id > lastId 的 pageSize 条
    """
    async with async_db_session() as db:
        # ===== 1️⃣ 参数校验 =====
        if (startTime or endTime) and not keyword:
            return await response_base.fail(msg="时间段查询必须提供关键字搜索")

        stmt = select(DqlJinshiEconomicNews)
        # ===== 1️ 构建查询条件 =====
        conditions = []

        # 日期筛选优先级：时间段 > 单日
        if startTime and endTime:
            conditions.append(
                and_(
                    DqlJinshiEconomicNews.time >= startTime,
                    DqlJinshiEconomicNews.time < endTime,
                )
            )

        # 日期过滤
        elif dateValue:
            conditions.append(DqlJinshiEconomicNews.time.like(f"{dateValue}%"))

        # 关键字搜索
        if keyword:
            conditions.append(DqlJinshiEconomicNews.name.like(f"%{keyword}%"))

        # 应用查询条件
        if conditions:
            stmt = stmt.where(*conditions)

        # ===== 2️ 分页逻辑 =====
        # 计算 offset
        offset = (pageNo - 1) * pageSize
        stmt = stmt.order_by(DqlJinshiEconomicNews.time.desc()).offset(offset).limit(pageSize)

        # ===== 3️ 执行查询 =====
        result = await db.execute(stmt)
        rows = result.scalars().all()

        # ===== 4️ 统计总数（用于前端分页） =====
        count_stmt = select(func.count()).select_from(DqlJinshiEconomicNews)
        if conditions:
            count_stmt = count_stmt.where(*conditions)

        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        # ===== 查询哪些经济数据有周期统计 =====
        pk_ids = [r.pkId for r in rows]
        if pk_ids:
            stat_stmt = select(MarketStatistics.economicNewsUid).where(
                MarketStatistics.economicNewsUid.in_(pk_ids)
            )
            stat_result = await db.execute(stat_stmt)
            has_stats_ids = {r[0] for r in stat_result.fetchall()}  # 集合方便判断
        else:
            has_stats_ids = set()

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
            isPeriodicStatistics=1 if row.pkId in has_stats_ids else 0,

        )
        for row in rows

    ]

    data = {"economic": result, "event": events_data, "holiday": holiday_data,
            "pageNo": pageNo, "pageSize": pageSize, "total": total}

    return await response_base.success(data=data)


@router.get("/marketNews", name="快讯")
async def get_market_news(
        lastId: Optional[int] = Query(None, description="上次请求的最后ID"),
        pageSize: Optional[int] = 100,
        keyword: Optional[str] = Query(None, description="快讯内容搜索关键字"),
        isPredict: Optional[int] = Query(0, description="是否经过预测过的快讯，0=全部快讯，1=预测快讯")
        ):
    """
    获取市场快讯数据 （带预测信息）：
    - 第一次请求：不传 last_id，返回最新 100 条
    - 后续请求：传 last_id，返回 id > last_id 的 100 条
    - 支持关键字搜索 (keyword)
    - 每条快讯包含 preds（利多/利空标识）

    """
    async with async_db_session() as db:
        # ===== 1️ 查询快讯主表 =====
        market = DqlJinshiMarketNews
        news_class = DqlJinshiNewsClass
        model = news_class if isPredict else market
        # ===== 1️ 构建基础查询条件 =====
        conditions = []
        if keyword:
            # 模糊匹配 content（可加更多字段）
            conditions.append(model.content.like(f"%{keyword}%"))

        if isPredict:
            # 预测快讯表
            # ===== 2️ 主表查询 =====
            if lastId is None:
                # 初次查询
                if conditions:
                    stmt = (
                        select(news_class)
                        .where(and_(*conditions, news_class.preds.in_([1, -1])))
                        .order_by(news_class.pkId.desc())
                        .limit(pageSize)
                    )
                else:
                    stmt = (
                        select(news_class)
                        .where(news_class.preds.in_([1, -1]))
                        .order_by(news_class.pkId.desc())
                        .limit(pageSize)
                    )

            else:
                # 翻页查询
                stmt = (
                    select(news_class)
                    .where(and_(news_class.pkId > lastId, news_class.preds == 100))
                    .order_by(news_class.pkId.asc())
                    .limit(pageSize)
                )
                if conditions:
                    stmt = stmt.where(and_(*conditions))

            result = await db.execute(stmt)
            market_rows = result.scalars().all()
        else:
            # ===== 2️ 主表查询 =====
            if lastId is None:
                stmt = (
                    select(market)
                    .where(*conditions) if conditions else select(market)
                )
                stmt = stmt.order_by(market.pkId.desc()).limit(pageSize)
            else:
                stmt = (
                    select(market)
                    .where(market.pkId > lastId)
                    .order_by(market.pkId.asc())
                    .limit(pageSize)
                )
                if conditions:
                    stmt = stmt.where(*conditions)

            result = await db.execute(stmt)
            market_rows = result.scalars().all()

            if not market_rows:
                return await response_base.success(data=[])

            # 提取快讯ID
            market_ids = [row.pkId for row in market_rows]

            # ===== 3 查询预测表 =====
            stmt2 = select(news_class.newsId, news_class.preds).where(news_class.newsId.in_(market_ids))
            result2 = await db.execute(stmt2)
            preds_map = {r.newsId: r.preds for r in result2.all()}

        # ===== 4 拼接结果 =====
        result = [
            MarketNewsResponse(
                pkId=row.pkId,
                time=row.time,
                content=row.content,
                createTime=row.createTime,
                updateTime=row.updateTime,
                preds=row.preds if isPredict else preds_map.get(row.pkId, 0) # 默认0表示未预测
            )
            for row in market_rows
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


def summarize_period(values: list[str]):
    """ values: ['open,high,low,close', ...] """

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
        "total": total,  # 总次数
        "upCount": up,  # 涨次数
        "downCount": down,  # 跌次数
        "flatCount": flat,  # 持平次数
        "upProb": round(up / total, 3),   # 涨概率 = up/total
        "downProb": round(down / total, 3),  # 跌概率 = 16/40
        "flatProb": round(flat / total, 3),  # 持平概率
        "avgUpPoints": round(sum(up_changes) / len(up_changes), 3) if up_changes else 0, # 平均上涨点数（美元）
        "avgDownPoints": round(sum(down_changes) / len(down_changes), 3) if down_changes else 0, # 平均下跌点数（美元）
        "avgRange": round(sum(ranges) / len(ranges), 3),  # 平均波动 high-low
    }


@router.get("/marketStatistics/", name="经济数据统计")
async def get_market_statistics(economicNewsUid: int = Query(..., description="金十经济数据日历pkId")):
    async with async_db_session() as db:
        result = await db.execute(
            select(MarketStatistics).where(MarketStatistics.economicNewsUid == economicNewsUid)
        )
        record = result.scalars().first()
        if not record:
            return await response_base.fail(msg="数据未找到！", data=[])

        # 根据 newsType 查询全表数据
        result2 = await db.execute(
            select(MarketStatistics).where(MarketStatistics.newsType == record.newsType)
        )
        all_same_type = result2.scalars().all()

        # 取出各周期字段列表
        def extract(field):
            return [getattr(r, field) for r in all_same_type if getattr(r, field)]

        m5_values = extract("m5")
        m30_values = extract("m30")
        h1_values = extract("h1")
        d1_values = extract("d1")
        w1_values = extract("w1")

        # ④ 计算统计
        summary = {
            "m5": summarize_period(m5_values),
            "m30": summarize_period(m30_values),
            "h1": summarize_period(h1_values),
            "d1": summarize_period(d1_values),
            "w1": summarize_period(w1_values),
        }

        # 返回Vo对象，响应时会自动解析json
        result = MarketStatisticsOut(
            pkId=record.pkId,
            economicNewsUid=record.economicNewsUid,
            time=record.time,
            name=record.name,
            newsType=record.newsType,
            m5=record.m5,
            m30=record.m30,
            h1=record.h1,
            d1=record.d1,
            w1=record.w1,
            createTime=record.createTime,
            summary=summary,  # 新增：周期统计结果

        )

        return await response_base.success(data=result)
