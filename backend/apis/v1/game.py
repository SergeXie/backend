import datetime
import traceback
from collections import defaultdict
import json
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
    'charset': 'utf8mb4',
}

# SQL 查询语句
base_query = """
    SELECT
        t1.pkId,
        t1.heroId,
        t1.photo,
        t3.cname as heroName,
        t2.heroCareer,
        t1.firstPlaceScore,
        t1.fiftyScores,
        t1.tenthPlaceScore,
        t1.eightyScores,
        t1.lastPlaceScore,
        t1.province,
        t1.provincePower,
        t1.updatetime,
        t1.createTime,
        t3.heroType,   -- lz_hero 表中的 heroType 字段
        t4.remark,     -- lz_hero_details 表中的 remark 字段
        t4.position,   -- lz_hero_details 表中的 position 字段
        t4.proficiency,
        t2.peakHeroWinRate,
        t2.peakHeroShowRate,
        t2.peakHeroBanRate,
        t2.topHeroWinRate,
        t2.topHeroShowRate,
        t2.topHeroBanRate,
        t2.kzInfo,
        t2.bkzInfo,
        t2.tfInfo,
        t2.dfInfo,
        t2.appleHonor,
        t2.androidHonor,
    FROM 
        lz_hero_rank t1
    INNER JOIN 
        lz_hero_stats t2 ON t1.heroId = t2.heroId -- 关联 lz_hero_stats 表，heroId 对应 heroId
    INNER JOIN 
        lz_hero t3 ON t1.heroId = t3.id          -- 关联 lz_hero 表，heroId 对应 id
    INNER JOIN 
        lz_hero_details t4 ON t1.heroId = t4.heroId -- 关联 lz_hero_details 表，heroId 对应 heroId
    WHERE 
        DATE(t1.createTime) = %s  -- 筛选指定日期的数据
    ORDER BY 
        t3.heroType, t1.heroId;
"""


async def get_hero_detail(heroId, remark=None, position=None, proficiency=None):
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 构建 SQL 语句
            query = f"""
                        UPDATE lz_hero_details SET remark = %s, position = %s, proficiency = %s WHERE heroId = %s;
                    """
            cursor.execute(query, (remark, position, proficiency, heroId))
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
def get_hero_data():
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
                    t2.heroCareer,
                    t1.firstPlaceScore,
                    t1.fiftyScores,
                    t1.tenthPlaceScore,
                    t1.eightyScores,
                    t1.lastPlaceScore,
                    t1.province,
                    t1.provincePower,
                    t1.updatetime,
                    t1.createTime,
                    t4.remark,
                    t4.position,
                    t4.proficiency,
                    t3.heroType,
                    t2.peakHeroWinRate,
                    t2.peakHeroShowRate,
                    t2.peakHeroBanRate,
                    t2.topHeroWinRate,
                    t2.topHeroShowRate,
                    t2.topHeroBanRate,
                    t2.kzInfo,
                    t2.bkzInfo,
                    t2.tfInfo,
                    t2.dfInfo,
                    t2.appleHonor,
                    t2.androidHonor
                FROM
                    lz_hero_rank t1
                INNER JOIN (
                    SELECT MAX(pkId) AS pkId FROM lz_hero_rank GROUP BY heroId
                ) t5 ON t1.pkId = t5.pkId
                INNER JOIN lz_hero t3 ON t1.heroId = t3.id
                INNER JOIN lz_hero_details t4 ON t1.heroId = t4.heroId
                LEFT JOIN lz_hero_stats t2 ON t1.heroId = t2.heroId
            """
            # 动态条件
            params = []

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
@router.post("/heroList", name="国内-王者营地")
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
    dataView = data_request.get("dataValue", 1)  # 1 最新  0 旧数据

    if dataView:
        hero_data = get_hero_data()
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
            hero["firstPlaceScore"] = int(hero["firstPlaceScore"]) if hero.get("firstPlaceScore", 0) else None
            hero["fiftyScores"] = int(hero["fiftyScores"]) if hero.get("fiftyScores", 0) else None
            hero["tenthPlaceScore"] = int(hero["tenthPlaceScore"]) if hero.get("tenthPlaceScore", 0) else None
            hero["eightyScores"] = int(hero["eightyScores"]) if hero.get("eightyScores", 0) else None
            hero["lastPlaceScore"] = int(hero["lastPlaceScore"]) if hero.get("lastPlaceScore", 0) else None
            hero["updatetime"] = hero["updatetime"].strftime("%Y-%m-%d %H:%M:%S")
            hero['equips'] = equip_dict[hero['heroId']]
            hero['runes'] = rune_dict[hero['heroId']]

            # json.loads
            hero["appleHonor"] = json.loads(hero["appleHonor"]) if hero["appleHonor"] else hero["appleHonor"]
            hero["androidHonor"] = json.loads(hero["androidHonor"]) if hero["androidHonor"] else hero["androidHonor"]

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
    dataView = data_request.get("dataValue", 1)  # 1 最新  0 旧数据

    if dataView:
        hero_data = get_hero_data()
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
                                   data.get("remark", None),
                                   data.get("position", None),
                                   data.get("proficiency", None))
    # 响应
    if result:
        return await response_base.success()
    else:
        return await response_base.fail(msg="添加或修改失败！")


@router.get("/abroadHeroList", name="国际服-王者荣耀")
async def abroad_hero_list():
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 基础查询语句
            base_query = """
                SELECT
                    t1.id,
                    t1.cname,
                    t1.heroCareer,
                    t1.icon,
                    t1.banRate,
                    t1.showRate,
                    t1.winRate,
                    t1.tfInfo,
                    t1.dfInfo,
                    t1.tfInfoCombinationValue,
                    t1.dfInfoCombinationValue,
                    t1.createTime,
                    t4.remark,
                    t4.position,
                    t4.proficiency
                FROM 
                    lz_hero_abroad t1
                INNER JOIN 
                    lz_hero_details t4 ON t1.id = t4.heroId
            """

            # 执行查询
            cursor.execute(base_query)
            result = cursor.fetchall()

            result_list = [
                {
                    "heroId": x["id"],
                    "heroName": x["cname"],
                    "heroCareer": x["heroCareer"],
                    "photo": x["icon"],
                    "banRate": x["banRate"],
                    "showRate": x["showRate"],
                    "winRate": x["winRate"],
                    "tfInfo": json.loads(x.get("tfInfo")) if x.get("tfInfo") else [],
                    "dfInfo": json.loads(x.get("dfInfo")) if x.get("dfInfo") else [],
                    "tfInfoCombinationValue": x.get("tfInfoCombinationValue", 0),
                    "dfInfoCombinationValue": x.get("dfInfoCombinationValue", 0),
                    "remark": x.get("remark"),  # 从 t4 表获取的字段
                    "position": x.get("position"),  # 从 t4 表获取的字段
                    "proficiency": x.get("proficiency"),  # 从 t4 表获取的字段
                    "updatetime": x["createTime"].strftime('%Y-%m-%d %H:%M:%S')
                }
                for x in result
            ]

        return await response_base.success(data=result_list)

    finally:
        connection.close()


@router.get("/heroRankings", name="英雄荣誉排行榜")
async def hero_rankings(heroId: str, osType: str, areaId: str):
    try:
        connection = pymysql.connect(**DB_CONFIG)

        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 修正 SQL 语句
            base_query = """
                SELECT 
                    t1.*, 
                    t2.userName, 
                    t2.avater, 
                    t2.roleName, 
                    t2.roleJobName
                FROM 
                    lz_player_rank_log t1
                LEFT JOIN 
                    lz_player t2 ON t1.userId = t2.userId
                WHERE 
                    t1.heroId = %s AND t1.os = %s and t1.areaId= %s
                ORDER BY 
                    t1.id DESC LIMIT 100;
            """

            # 执行 SQL 语句
            cursor.execute(base_query, (heroId, osType, areaId))

            # 获取查询结果
            results = cursor.fetchall()

            # 处理查询结果
            result_list = []
            user_ids = []
            for row in results:
                # print(row)
                data_dict = {}
                data_dict["id"] = row["id"]
                data_dict["userId"] = row["userId"]
                if int(row["userId"]) > 0:
                    user_ids.append(data_dict["userId"])
                data_dict["heroId"] = row["heroId"]
                if int(areaId) == 1:  # 全国
                    data_dict["power"] = row["power"]
                else:  # 区域
                    data_dict["power"] = row["power"]
                data_dict["areaId"] = row["areaId"]
                data_dict["os"] = row["os"]
                data_dict["userName"] = row["userName"]
                data_dict["avater"] = row["avater"]
                data_dict["roleName"] = row["roleName"]
                data_dict["roleJobName"] = row["roleJobName"]
                result_list.append(data_dict)

            user_hero_data = {}
            if user_ids:
                users_base_query = f"""
                    SELECT
                        t2.cname,
                        t2.icon,
                        t1.*
                    FROM
                        lz_player_rank t1
                    LEFT JOIN
                        lz_hero t2 ON t1.heroId = t2.id
                    LEFT JOIN
                        lz_player t3 ON t1.userId = t3.userId
                    WHERE t1.userId IN ({', '.join(map(str, user_ids))})
                    ORDER BY
                        t1.isInNationalTop DESC,
                        t1.isInHistoryNationalTop DESC,
                        t1.isInRegionalTop DESC,
                        t1.isInHistoryRegionalTop DESC,
                        t1.nationalPower DESC,
                        t1.regionalPower DESC,
                        t1.nationalHistoryPower DESC,
                        t1.regionalHistoryPower DESC;
                """

                # 执行 SQL 语句
                cursor.execute(users_base_query)

                # 获取查询结果
                users_results = cursor.fetchall()

                for data in users_results:
                    if (data["isInHistoryNationalTop"] <= 0 and
                            data["isInHistoryRegionalTop"] <= 0 and
                            data["isInNationalTop"] <= 0 and
                            data["isInRegionalTop"] <= 0):
                        continue

                    user_id = data["userId"]
                    data["lastNationalTopTime"] = data["lastNationalTopTime"].strftime('%Y-%m-%d %H:%M:%S')
                    data["lastRegionalTopTime"] = data["lastRegionalTopTime"].strftime('%Y-%m-%d %H:%M:%S')
                    data["lastHistoryNationalTopTime"] = data["lastHistoryNationalTopTime"].strftime(
                        '%Y-%m-%d %H:%M:%S')
                    data["lastHistoryRegionalTopTime"] = data["lastHistoryRegionalTopTime"].strftime(
                        '%Y-%m-%d %H:%M:%S')
                    data["updateTime"] = data["updateTime"].strftime('%Y-%m-%d %H:%M:%S')
                    data["createTime"] = data["createTime"].strftime('%Y-%m-%d %H:%M:%S')
                    user_hero_data_list = []
                    if user_id in user_hero_data:
                        user_hero_data_list = user_hero_data[user_id]
                    else:
                        user_hero_data[user_id] = user_hero_data_list

                    if len(user_hero_data_list) < 10:
                        user_hero_data_list.append(data)

            data_result = {"code": 200, "msg": "Success",
                           "data": result_list, "userHeroData": user_hero_data}

            return data_result

    except Exception as e:
        info = traceback.format_exc()
        print("error:{}".format(info))


@router.get("/rankingStatistics", name="玩家上榜英雄统计")
async def ranking_statistics(userId: str, osType: str, areaId: int):
    connection = pymysql.connect(**DB_CONFIG)

    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        # 查询所有排行统计
        base_query = """
            SELECT
                t2.cname,
                t2.icon,
                t1.*
            FROM
                lz_player_rank t1
            LEFT JOIN
                lz_hero t2 ON t1.heroId = t2.id
            LEFT JOIN
                lz_player t3 ON t1.userId = t3.userId
            WHERE
                t1.userId = %s
            ORDER BY
                t1.isInNationalTop DESC,
                t1.isInHistoryNationalTop DESC,
                t1.isInRegionalTop DESC,
                t1.isInHistoryRegionalTop DESC,
                t1.nationalPower DESC,
                t1.regionalPower DESC,
                t1.nationalHistoryPower DESC,
                t1.regionalHistoryPower DESC;
        """
        cursor.execute(base_query, (userId))

        # 获取所有数据
        results = cursor.fetchall()

        result_list = []
        # 输出查询结果
        for row in results:
            # Check if any of the power values are less than or equal to 0
            if (row["isInHistoryNationalTop"] <= 0 and
                    row["isInHistoryRegionalTop"] <= 0 and
                    row["isInNationalTop"] <= 0 and
                    row["isInRegionalTop"] <= 0):
                continue

            row["lastNationalTopTime"] = row["lastNationalTopTime"].strftime('%Y-%m-%d %H:%M:%S')
            row["lastRegionalTopTime"] = row["lastRegionalTopTime"].strftime('%Y-%m-%d %H:%M:%S')
            row["lastHistoryNationalTopTime"] = row["lastHistoryNationalTopTime"].strftime('%Y-%m-%d %H:%M:%S')
            row["lastHistoryRegionalTopTime"] = row["lastHistoryRegionalTopTime"].strftime('%Y-%m-%d %H:%M:%S')
            row["updateTime"] = row["updateTime"].strftime('%Y-%m-%d %H:%M:%S')
            row["createTime"] = row["createTime"].strftime('%Y-%m-%d %H:%M:%S')
            result_list.append(row)

        return await response_base.success(data=result_list)








