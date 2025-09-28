import pymysql
import json
from datetime import datetime

# -------------------------- 1. 配置参数 --------------------------
# 数据库连接配置（请替换为你的实际配置）
DB_CONFIG = {
    "host": "192.168.1.126",       # 数据库地址（如本地为 localhost）
    "port": 3306,              # 端口（默认3306）
    "user": "cmdb",            # 用户名
    "password": "cmdb123456",# 密码
    "db": "dql",     # 数据库名（需提前创建）
    "charset": "utf8mb4"       # 字符集（与表结构一致）
}
import pickle
import json
# 文档中的原始数据（注意：将单引号转为双引号，符合JSON标准）
with open('./dataset/all_wm_pattern_kline.pkl', 'rb') as file:
    all_wm_pattern = pickle.load(file)

print('这里')
# print(len(all_wm_pattern))
# print(all_wm_pattern[-1])


all_wm_pattern = [json.dumps(i, ensure_ascii=False, indent=4) for i in all_wm_pattern]

# -------------------------- 2. 核心插入逻辑 --------------------------


for i in all_wm_pattern:
    data = json.loads(i)

    # 2. 提取表所需字段（仅插入kline_pattern表的核心字段，points/target_klines如需存储可单独设计表）
    pattern_data = {
        "pattern_type": data.get("pattern_type"),
        "points": data.get("points"),
        "start_timestamp": data.get("start_timestamp"),
        "end_timestamp": data.get("end_timestamp"),
        "target_klines": data.get("target_klines"),
        "period": data.get("period")
    }

    # 3. 连接数据库并循环插入（此处虽为单条数据，按"循环"逻辑设计，支持批量扩展）
    conn = None
    cursor = None

    # 建立数据库连接
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # 定义SQL插入语句（使用占位符%s，避免SQL注入）
    insert_sql = """
        INSERT INTO kline_pattern (
            pattern_type, 
            points, 
            start_timestamp, 
            end_timestamp,
            target_klines, 
            period
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """

    values = (
        pattern_data["pattern_type"],
        json.dumps(pattern_data["points"], ensure_ascii=False),  # 保留中文
        datetime.strptime(pattern_data["start_timestamp"], "%Y-%m-%d %H:%M:%S"),
        datetime.strptime(pattern_data["end_timestamp"], "%Y-%m-%d %H:%M:%S"),
        json.dumps(pattern_data["target_klines"], ensure_ascii=False),  # 保留中文
        pattern_data["period"]  # 应为字符串如"M5"
    )

    # 执行插入
    cursor.execute(insert_sql, values)
    # 提交事务（MySQL默认需要手动提交）
    conn.commit()
    print(f"数据插入成功！pattern_id: {cursor.lastrowid}")  # 打印自增的pattern_id
