from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Query
from sqlalchemy import select, and_, func
from common.response.response_schema import response_base
from database.db_mysql import async_db_session
from models.news_models import DqlJinshiEconomicNews, DqlJinshiMarketNews, DqlJinshiHoliday, DqlJinshiEvent, \
    MarketStatistics, DqlJinshiNewsClass, DqlCalendarTag, DqlNewsTagRelation
from schemas.lzhc_news import EconomicNewsResponse, MarketNewsResponse, JinshiEventBase, JinshiHolidayBase, \
    MarketStatisticsOut
from utils.Jinshi_calendar_utils import Jin10CalendarUtils
from utils.calendar_market_statistics import MarketStatisticsObject
from utils.economic_data_analyzer import EconomicDataAnalyzer
from utils.enum.period_enum import PeriodEnum

router = APIRouter()


@router.get("/economicNews", name="日历数据")
async def get_economic_news(
    lastId: Optional[int] = Query(None, description="上次请求的最后ID"),
    dateValue: Optional[str] = Query(None, description="查询日期，例如 2025-09-26"),
    startTime: Optional[str] = Query(None, description="开始时间，例如 2025-09-26 00:00:00"),
    endTime: Optional[str] = Query(None, description="结束时间，例如 2025-09-26 23:59:59"),
    pageNo: Optional[int] = Query(1, description="当前页码，从1开始"),
    pageSize: Optional[int] = Query(100, description="每页条数"),
    keyword: Optional[str] = Query(None, description="日历搜索关键字"),
    tag: Optional[str] = Query(None, description="日历标签"),
):
    """
    获取经济数据：
    - 如果传 dateValue：返回该日期的全部数据（可结合 lastId 翻页）
    - 如果不传 dateValue 且不传 lastId：返回最新 pageSize 条
    - 支持按 startTime ~ endTime 查询时间段
    - 如果不传 dateValue 但传 lastId：返回 id > lastId 的 pageSize 条
    """
    async with async_db_session() as db:
        # ===== 1️ 参数校验 =====
        if (startTime or endTime) and not keyword:
            return await response_base.fail(msg="时间段查询必须提供关键字搜索")

        stmt = select(DqlJinshiEconomicNews)
        # ===== 1️ 构建查询条件 =====
        conditions = []
        newsIds = []

        # 日历标签
        if tag:
            dql_calendar_tag = await db.execute(select(DqlCalendarTag).where(DqlCalendarTag.tagName == tag))
            tag_result = dql_calendar_tag.scalars().first()
            # 查询关联表
            news_tag_relation = await db.execute(select(DqlNewsTagRelation.newsId).where(
                DqlNewsTagRelation.tagId == tag_result.pkId))

            news_tag_relation_results = news_tag_relation.scalars().all()

            newsIds = [x for x in news_tag_relation_results]
            conditions.append(DqlJinshiEconomicNews.pkId.in_(newsIds))

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

        pk_ids = [r.pkId for r in rows]

        if not tag:
            # ====查询标签日历关联表的标签名称 根据经济日历id来查====
            news_tag_relation = await db.execute(select(DqlNewsTagRelation.tagName,
                                                        DqlNewsTagRelation.newsId).where(
                DqlNewsTagRelation.newsId.in_(pk_ids)))
            # key 是 newsId value 是标签名
            news_tag_list = [{r[1]:r[0]} for r in news_tag_relation.fetchall()]  # 集合方便判断
        else:
            news_tag_list = list

        # ===== 查询哪些经济数据有周期统计 =====
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
    result_data = []
    tagName = None
    for row in rows:
        prior = EconomicDataAnalyzer.safe_float(row.prevValue)  # 前值
        forecast = EconomicDataAnalyzer.safe_float(row.expectValue)  # 预期值
        actual = EconomicDataAnalyzer.safe_float(row.publishValue)  # 公布值
        impactLevel = None
        description = None

        # 针对统计表中的日历进行计算
        if row.pkId in has_stats_ids:
            if prior is not None and forecast is not None and actual is not None:
                # 强弱等级
                impactLevel = EconomicDataAnalyzer.calculate_impact_score(
                    prior, forecast, actual
                )  # :contentReference[oaicite:1]{index=1}

                # 方向一致性
                description = EconomicDataAnalyzer.evaluate_strength(
                    prior, forecast, actual
                )  # :contentReference[oaicite:2]{index=2}

        # 如果经济日历ID，存在关联表中的newsIds，那么显示标签名
        if row.pkId in newsIds:
            tagName = tag
        else:
            for data in news_tag_list:
                tagName = data.get(row.pkId)

        result_data.append(
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
                tag=tagName,
                impactLevel=impactLevel,
                description=description,
            )
        )

    data = {"economic": result_data, "event": events_data, "holiday": holiday_data,
            "pageNo": pageNo, "pageSize": pageSize, "total": total}

    return await response_base.success(data=data)


@router.get("/marketNews", name="快讯")
async def get_market_news(
        lastId: Optional[int] = Query(None, description="上次请求的最后ID"),
        historyId: Optional[int] = Query(None, description="往后翻查看历史的最后ID"),
        pageNo: Optional[int] = Query(1, description="当前页码，从1开始"),
        pageSize: Optional[int] = 100,
        keyword: Optional[str] = Query(None, description="快讯内容搜索关键字"),
        isPredict: Optional[int] = Query(0, description="是否经过预测过的快讯，0=全部快讯，1=预测快讯"),
        startTime: Optional[str] = Query(None, title="开始时间"),
        endTime: Optional[str] = Query(None, title="结束时间")
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

        offset = (pageNo - 1) * pageSize

        # ===== 1️ 构建基础查询条件 =====
        conditions = []
        if keyword:
            # 模糊匹配 content（可加更多字段）
            conditions.append(model.content.like(f"%{keyword}%"))

        if startTime and endTime:
            conditions.append(
                and_(
                    model.time >= startTime,
                    model.time < endTime
                )
            )

        if isPredict:
            # 预测快讯表
            # ===== 2️ 主表查询 =====
            if lastId is None and historyId is None:
                # 初次查询
                if conditions:
                    stmt = (
                        select(news_class)
                        .where(and_(*conditions, news_class.preds.in_([1, -1])))
                        .order_by(news_class.time.desc()).offset(offset).limit(pageSize)
                    )

                    count_stmt = select(func.count()).select_from(news_class).where(
                        and_(*conditions, news_class.preds.in_([1, -1])))

                else:
                    stmt = (
                        select(news_class)
                        .where(news_class.preds.in_([1, -1]))
                        .order_by(news_class.time.desc()).offset(offset).limit(pageSize)
                    )

                    count_stmt = select(func.count()).select_from(news_class).where(
                        news_class.preds.in_([1, -1]))

            elif historyId:
                # 查历史数据
                first_market_news_row = (
                    select(news_class.time)
                    .where(news_class.pkId == historyId)
                )
                result = await db.execute(first_market_news_row)
                first_market_news_time = result.scalars().first()

                # 翻页查询
                stmt = (
                    select(news_class)
                    .where(and_(news_class.time < first_market_news_time, news_class.preds.in_([1, -1])))
                    .order_by(news_class.time.desc()).offset(offset).limit(pageSize)
                )

                count_stmt = select(func.count()).select_from(news_class).where(
                    and_(news_class.time < first_market_news_time, news_class.preds.in_([1, -1])))

                if conditions:
                    stmt = stmt.where(and_(*conditions))
                    count_stmt = count_stmt.where(and_(*conditions))

            else:
                # 翻页查询
                stmt = (
                    select(news_class)
                    .where(and_(news_class.pkId > lastId, news_class.preds.in_([1, -1])))
                    .order_by(news_class.time.desc()).offset(offset).limit(pageSize)
                )

                count_stmt = select(func.count()).select_from(news_class).where(
                    and_(news_class.pkId > lastId, news_class.preds.in_([1, -1])))

                if conditions:
                    stmt = stmt.where(and_(*conditions))
                    count_stmt = count_stmt.where(and_(*conditions))

            total_result = await db.execute(count_stmt)
            total = total_result.scalar() or 0

            result = await db.execute(stmt)
            market_rows = result.scalars().all()

        else:
            # ===== 2️ 主表查询 =====
            if lastId is None and historyId is None:
                stmt = (
                    select(market)
                    .where(*conditions) if conditions else select(market)
                )
                stmt = stmt.order_by(market.time.desc()).offset(offset).limit(pageSize)

                count_stmt = select(func.count()).select_from(market).where(*conditions)

            elif historyId:
                # 查历史数据
                first_market_news_row =(
                    select(market.time)
                    .where(market.pkId == historyId)
                )
                result = await db.execute(first_market_news_row)
                first_market_news_time = result.scalars().first()

                stmt = (
                    select(market)
                    .where(market.time < first_market_news_time).order_by(
                        market.time.desc()).offset(offset).limit(pageSize)
                )

                count_stmt = select(func.count()).select_from(market).where(market.time <= first_market_news_time)

                if conditions:
                    stmt = stmt.where(*conditions)
                    count_stmt = count_stmt.where(and_(*conditions))

            else:
                # 翻译
                stmt = (
                    select(market)
                    .where(market.pkId > lastId)
                    .order_by(market.time.desc()).offset(offset).limit(pageSize)
                )

                count_stmt = select(func.count()).select_from(market).where(market.pkId > lastId)

                if conditions:
                    stmt = stmt.where(*conditions)
                    count_stmt = count_stmt.where(and_(*conditions))

            if startTime and endTime:
                total_result = await db.execute(count_stmt)
                total = total_result.scalar() or 0
            else: total = 0

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

        return {"code": 200,"message": "Success","pageNo": pageNo,"pageSize": pageSize,
                "data": result, "total": total}


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


@router.get("/marketStatistics/", name="经济数据统计")
async def get_market_statistics(economicNewsUid: int = Query(..., description="金十经济数据日历pkId")):
    async with async_db_session() as db:
        # 查询 dql_jinshi_economic_news 表
        economic_news = await db.execute(
            select(MarketStatistics).where(MarketStatistics.economicNewsUid == economicNewsUid)
        )
        record = economic_news.scalars().first()
        if not record:
            return await response_base.fail(msg="日历数据未找到！", data=[])

        # 根据 record 拿到日历发布时间time
        time_str = record.time
        name = record.name

        data_period, periodRange = await MarketStatisticsObject.get_statistics(db, name, time_str)

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
        #
        # # ④ 计算统计
        summary = {
            "m5": Jin10CalendarUtils.summarize_period(m5_values),
            "m30": Jin10CalendarUtils.summarize_period(m30_values),
            "h1": Jin10CalendarUtils.summarize_period(h1_values),
            "d1": Jin10CalendarUtils.summarize_period(d1_values),
            "w1": Jin10CalendarUtils.summarize_period(w1_values),
        }

        # # 返回Vo对象，响应时会自动解析json
        result = MarketStatisticsOut(
            pkId=record.pkId,
            economicNewsUid=record.economicNewsUid,
            time=record.time,
            name=record.name,
            newsType=record.newsType,
            m5=data_period.get("m5"),
            m30=data_period.get("m30"),
            h1=data_period.get("h1"),
            d1=data_period.get("d1"),
            w1=data_period.get("w1"),
            createTime=record.createTime,
            summary=summary,  # 新增：周期统计结果
            periodRange=periodRange, # 合成周期范围

        )

        return await response_base.success(data=result)


@router.get("/calendarTags/", name="日历标签")
async def get_tag_list():
    async with async_db_session() as db:

        stmt = select(DqlCalendarTag.tagName)
        result = await db.execute(stmt)
        tags = [row[0] for row in result.fetchall()]

        return await response_base.success(data=tags)
