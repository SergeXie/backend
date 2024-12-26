import datetime
from collections import defaultdict
import json
from typing import Optional

import pandas as pd
import pymysql
from fastapi import APIRouter
from starlette.requests import Request

from common.response.response_schema import response_base

router = APIRouter()

# 配置数据库连接信息
DB_CONFIG = {
    'host': '8.138.95.62',
    'user': 'dqldb',
    'password': 'u12VxHdAT38UEa67Kc',
    'database': 'game',
    'port': 3306,
    'charset': 'utf8mb4'
}


# SQL 查询语句
base_query = """
    SELECT
        t1.pkId,
        t1.heroId,
        t1.photo,
        t1.heroName,
        t1.heroCareer,
        t1.firstPlaceScore,
        t1.fiftyScores,
        t1.tenthPlaceScore,
        t1.eightyScores,
        t1.lastPlaceScore,
        t1.peakHeroWinRate,
        t1.peakHeroShowRate,
        t1.peakHeroBanRate,
        t1.topHeroWinRate,
        t1.topHeroShowRate,
        t1.topHeroBanRate,
        t1.kzInfo,
        t1.bkzInfo,
        t1.tfInfo,
        t1.dfInfo,
        t1.province,
        t1.provincePower,
        t1.updatetime,
        t1.createTime, 
        h.heroType, -- 选择 lz_hero 表中的 heroType 字段
        d.remark,   -- 选择 lz_hero_details 表中的 remark 字段
        d.position  -- 选择 lz_hero_details 表中的 position 字段
    FROM 
        lz_hero_rank t1
    INNER JOIN 
        lz_hero h ON t1.heroId = h.id  -- 连接 lz_hero 表，heroId 对应 id
    INNER JOIN 
        lz_hero_details d ON t1.heroId = d.heroId -- 连接 lz_hero_details 表，heroId 对应 heroId
    WHERE 
        DATE(t1.createTime) = %s;  -- 筛选 lz_hero_rank 中 createTime 为指定日期的数据
"""


async def get_hero_detail(heroId, remark=None, position=None):
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 构建 SQL 语句
            query = f"""
                        UPDATE lz_hero_details SET remark = %s, position = %s WHERE heroId = %s;
                    """
            cursor.execute(query, (remark, position, heroId))
            # 提交事务
            connection.commit()

            return True
    except Exception as e:
        # 如果发生异常，打印错误信息并回滚
        print(f"Error occurred: {e}")
        connection.rollback()
        return False
    finally:
        # 关闭数据库连接
        connection.close()


# 查询英雄的基本信息
def get_hero_data(heroName=None, heroCareer=None, remark=None,
                  position=None, screens=[], filterCriteria=None, dataView=None):
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 基础查询语句
            base_query = """
                SELECT
                    t1.pkId,
                    t1.heroId,
                    t1.photo,
                    t1.heroName,
                    t1.heroCareer,
                    t1.firstPlaceScore,
                    t1.fiftyScores,
                    t1.tenthPlaceScore,
                    t1.eightyScores,
                    t1.lastPlaceScore,
                    t1.peakHeroWinRate,
                    t1.peakHeroShowRate,
                    t1.peakHeroBanRate,
                    t1.topHeroWinRate,
                    t1.topHeroShowRate,
                    t1.topHeroBanRate,
                    t1.kzInfo,
                    t1.bkzInfo,
                    t1.tfInfo,
                    t1.dfInfo,
                    t1.province,
                    t1.provincePower,
                    t1.updatetime,
                    t1.createTime,
                    t4.remark,
                    t4.position,
                    t3.heroType
                FROM
                    lz_hero_rank t1
                INNER JOIN (
                    SELECT MAX(pkId) AS pkId FROM lz_hero_rank GROUP BY heroName
                ) t2 ON t1.pkId = t2.pkId
                INNER JOIN lz_hero t3 ON t1.heroId = t3.id
                INNER JOIN lz_hero_details t4 ON t1.heroId = t4.heroId
            """

            # 动态条件
            conditions = []
            params = []

            # 添加动态过滤条件
            if heroName:
                conditions.append("t1.heroName LIKE %s")
                params.append(f"%{heroName}%")
            if heroCareer:
                conditions.append("t1.heroCareer LIKE %s")
                params.append(f"%{heroCareer}%")
            if remark:
                conditions.append("t4.remark LIKE %s")
                params.append(f"%{remark}%")
            if position:
                conditions.append("t4.position LIKE %s")
                params.append(f"%{position}%")

            # 处理 screens 条件
            if screens:
                for screen in screens:
                    name = screen.get("name")
                    name_value = screen.get("nameValue")  # 运算符
                    value = screen.get("value")          # 筛选值
                    check_value = screen.get("checkValue")  # 是否启用此筛选

                    if name and name_value and check_value:
                        conditions.append(f"t1.{name} {name_value} %s")
                        params.append(value)

            # 拼接条件
            if conditions:
                base_query += " WHERE " + f" {filterCriteria} ".join(conditions)

            # 添加排序
            base_query += " ORDER BY t3.heroType, t1.heroId;"

            # 执行查询
            cursor.execute(base_query, params)
            result = cursor.fetchall()

        return result
    finally:
        connection.close()


def get_hero_data_by_date(date):
    """
    查询指定日期的英雄数据，连接 lz_hero 和 lz_hero_details 表
    :param date: 日期字符串，例如 '2024-12-11'
    :return: 查询结果（字典列表）
    """
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 执行查询，防止 SQL 注入
            cursor.execute(base_query, (date,))
            result = cursor.fetchall()

        return result

    except Exception as e:
        print(f"查询失败: {e}")
    finally:
        if connection:
            connection.close()


# 批量查询所有英雄的装备信息
def get_all_hero_equips():
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            query = """
                SELECT t5.heroId, t5.szTitle, t5.szIcon, t5.equipwinRate, t5.equipShowRate
                FROM lz_hero_equip t5
                INNER JOIN (
                    SELECT heroId, szTitle, MAX(createTime) AS latestTime
                    FROM lz_hero_equip
                    GROUP BY heroId, szTitle
                ) latestEquip ON t5.heroId = latestEquip.heroId 
                AND t5.szTitle = latestEquip.szTitle 
                AND t5.createTime = latestEquip.latestTime
                ORDER BY t5.heroId, t5.szTitle;
            """
            cursor.execute(query)
            result = cursor.fetchall()
        return result
    finally:
        connection.close()

def get_all_hero_equips2():

    return []


def get_all_hero_runes2():

    return []


def get_hero_gold_play2():
    return []

# 批量查询所有英雄的符文信息
def get_all_hero_runes():
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            query = """
                SELECT t5.heroId, t5.runeDetail, t5.runeWinRate, t5.runeshowRate
                FROM lz_hero_rune t5
                INNER JOIN (
                    SELECT heroId, runeDetail, MAX(createTime) AS latestTime
                    FROM lz_hero_rune
                    GROUP BY heroId, runeDetail
                ) latestRune ON t5.heroId = latestRune.heroId 
                AND t5.runeDetail = latestRune.runeDetail 
                AND t5.createTime = latestRune.latestTime
                ORDER BY t5.heroId, t5.runeDetail;
            """
            cursor.execute(query)
            result = cursor.fetchall()
        return result
    finally:
        connection.close()


def get_hero_gold_play():
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            query = """
                SELECT t1.heroId, t1.goldPlay
                FROM lz_hero_gold_medal AS t1
                INNER JOIN (
                    SELECT heroId, MAX(createTime) AS maxCreateTime
                    FROM lz_hero_gold_medal
                    GROUP BY heroId
                ) AS t2
                ON t1.heroId = t2.heroId AND t1.createTime = t2.maxCreateTime
            """
            cursor.execute(query)
            result = cursor.fetchall()
            if result:
                return {item['heroId']: item['goldPlay'] for item in result}
            else:
                return {}
    finally:
        connection.close()


def get_hero_data_with_gold_play():
    hero_data = get_hero_data()  # 获取英雄数据
    gold_play_data = get_hero_gold_play()  # 获取 goldPlay 数据

    # 将 goldPlay 数据合并到 hero_data 中
    for hero in hero_data:
        hero['goldPlay'] = gold_play_data.get(hero['heroId'], 0)  # 默认为 0

    return hero_data


def get_previous_business_day():
    """
    获取前一天的日期，如果是周末则返回最近的周五日期。
    """
    today = datetime.date.today()
    # 获取前一天
    previous_day = today - datetime.timedelta(days=1)

    # 如果是周六 (5) 或周日 (6)，调整到周五
    if previous_day.weekday() == 5:  # 周六
        previous_day -= datetime.timedelta(days=1)
    elif previous_day.weekday() == 6:  # 周日
        previous_day -= datetime.timedelta(days=2)

    return previous_day.strftime('%Y-%m-%d')


# 定义 API 路由，返回英雄信息及装备信息
@router.post("/heroList")
async def read_hero_data(request: Request):
    """
    :param heroName: 英雄筛选
    :param heroCareer: 职位筛选
    :param remark: 备注
    :param position: 位置
    :param screens: 动态条件数组，格式为：
        [
            {"title": "巅峰胜率", "name": "peakHeroWinRate", "nameValue": ">=", "value": 3, "checkValue": true},
            {"title": "顶端胜率", "name": "topHeroWinRate", "nameValue": "<", "value": 2, "checkValue": true}
        ]
    :return:
    """
    data_request = await request.json()
    heroName = data_request.get("heroName", None)
    heroCareer = data_request.get("heroCareer", None)
    remark = data_request.get("remark", None)
    position = data_request.get("position", None)
    screens = data_request.get("screens", [])  # 筛选
    filterCriteria = data_request.get("filterCriteria", "AND")  # AND|OR
    dataView = data_request.get("dataValue", 1)  # 1 最新  0 旧数据

    if dataView:
        hero_data = get_hero_data(heroName=heroName, heroCareer=heroCareer,
                                  remark=remark, position=position, screens=screens,
                                  filterCriteria=filterCriteria, dataView=dataView)

        all_equips = get_all_hero_equips()
        all_runes = get_all_hero_runes()
        gold_play_data = get_hero_gold_play()  # 获取 goldPlay 数据

        # 将 goldPlay 数据合并到 hero_data 中
        for hero in hero_data:
            hero['goldPlay'] = gold_play_data.get(hero['heroId'], 0)  # 默认为 0

        # # 将 goldPlay 数据合并到 hero_data 中
        # for hero in hero_data:
        #     hero['goldPlay'] = 0

        # 将装备信息按 heroId 分组
        equip_dict = defaultdict(list)
        for equip in all_equips:
            equip_dict[equip['heroId']].append({
                "szTitle": equip["szTitle"],
                "szIcon": equip["szIcon"],
                "equipwinRate": equip["equipwinRate"],
                "equipShowRate": equip["equipShowRate"]
            })

        # 将符文信息按 heroId 分组
        rune_dict = defaultdict(list)
        for rune in all_runes:
            rune_detail = json.loads(rune['runeDetail'])  # 解析 runeDetail JSON 字符串
            rune_dict[rune['heroId']].append({
                "runeDetail": rune_detail,  # 解析后的符文列表
                "runeWinRate": rune["runeWinRate"],
                "runeshowRate": rune["runeshowRate"]
            })

        # 为每个英雄附加装备信息和符文信息
        for hero in hero_data:
            hero["updatetime"] = hero["updatetime"].strftime("%Y-%m-%d %H:%M:%S")
            hero['equips'] = equip_dict[hero['heroId']]
            hero['runes'] = rune_dict[hero['heroId']]

            if hero.get("kzInfo"):
                hero["kzInfo"] = json.loads(hero.get("kzInfo", []))
                hero["bkzInfo"] = json.loads(hero.get("bkzInfo", []))
                hero["tfInfo"] = json.loads(hero.get("tfInfo", []))
                hero["dfInfo"] = json.loads(hero.get("dfInfo", []))
            else:
                hero["kzInfo"] = []
                hero["bkzInfo"] = []
                hero["tfInfo"] = []
                hero["dfInfo"] = []

        return await response_base.success(data=hero_data)

    else:
        # 示例调用
        date_to_query = get_previous_business_day()
        print("查询的日期是:", date_to_query)

        hero_data = get_hero_data_by_date(date_to_query)
        all_equips = get_all_hero_equips()
        all_runes = get_all_hero_runes()
        gold_play_data = get_hero_gold_play()  # 获取 goldPlay 数据

        # 将 goldPlay 数据合并到 hero_data 中
        for hero in hero_data:
            hero['goldPlay'] = gold_play_data.get(hero['heroId'], 0)  # 默认为 0

        # 将装备信息按 heroId 分组
        equip_dict = defaultdict(list)
        for equip in all_equips:
            equip_dict[equip['heroId']].append({
                "szTitle": equip["szTitle"],
                "szIcon": equip["szIcon"],
                "equipwinRate": equip["equipwinRate"],
                "equipShowRate": equip["equipShowRate"]
            })

        # 将符文信息按 heroId 分组
        rune_dict = defaultdict(list)
        for rune in all_runes:
            rune_detail = json.loads(rune['runeDetail'])  # 解析 runeDetail JSON 字符串
            rune_dict[rune['heroId']].append({
                "runeDetail": rune_detail,  # 解析后的符文列表
                "runeWinRate": rune["runeWinRate"],
                "runeshowRate": rune["runeshowRate"]
            })

        # 为每个英雄附加装备信息和符文信息
        for hero in hero_data:
            hero["updatetime"] = hero["updatetime"].strftime("%Y-%m-%d %H:%M:%S")
            hero['equips'] = equip_dict[hero['heroId']]
            hero['runes'] = rune_dict[hero['heroId']]

            if hero.get("kzInfo"):
                hero["kzInfo"] = json.loads(hero.get("kzInfo", []))
                hero["bkzInfo"] = json.loads(hero.get("bkzInfo", []))
                hero["tfInfo"] = json.loads(hero.get("tfInfo", []))
                hero["dfInfo"] = json.loads(hero.get("dfInfo", []))
            else:
                hero["kzInfo"] = []
                hero["bkzInfo"] = []
                hero["tfInfo"] = []
                hero["dfInfo"] = []

        return await response_base.success(data=hero_data)


@router.post("/heroDetailOperate", name="添加修改英雄详情")
async def hero_detail_operate(request: Request):

    """
    heroId：英雄ID
    remark: 备注
    position：位置
    添加或修改英雄详细信息
    :return:
    """
    data = await request.json()

    # 1 根据传递的heroId进行数据库查询该条字段, 如果存在！则根据请求的参数进行插入数据库
    result = await get_hero_detail(data.get("heroId", None),
                                   data.get("remark", None), data.get("position", None))
    # 响应
    if result:
        return await response_base.success()
    else:
        return await response_base.fail(msg="添加或修改失败！")







