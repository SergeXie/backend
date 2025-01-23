import sys
import traceback
from typing import Annotated
from fastapi import Depends
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.log import log
from typing import Union
from core.conf import settings


def create_engine_and_session(url: Union[str, URL]):
    try:

        # u12VxHdAT38UEa67Kc
        # 数据库引擎
        # engine = create_async_engine("mysql+aiomysql://cmdb:cmdb123456@192.168.0.126:3306/dql?charset=utf8mb4",
        #                              echo=False, future=True, pool_pre_ping=True)

        engine = create_async_engine(
            "mysql+aiomysql://cmdb:cmdb123456@192.168.0.126:3306/dql?charset=utf8mb4",
            echo=False,
            future=True,
            pool_pre_ping=True,  # 连接获取前检测是否可用，防止失效连接
            pool_recycle=1800,  # 30 分钟后回收连接，防止 MySQL 连接超时
            pool_size=10,  # 连接池最大连接数，适用于高并发
            max_overflow=5,  # 连接池最大溢出数，可创建额外连接数
            pool_timeout=30,  # 获取连接的超时时间，防止阻塞
        )
        log.success('数据库连接成功')

    except Exception as e:
        info = traceback.format_exc()
        print("bug:{}".format(info))
        log.error('❌ 数据库链接失败 {}', e)

        sys.exit()
    else:
        db_session = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        return engine, db_session


SQLALCHEMY_DATABASE_URL = (
    'mysql+asyncmy://root:python@127.0.0.1:3306/dql_test?charset=utf8mb4'
)


async_engine, async_db_session = create_engine_and_session(SQLALCHEMY_DATABASE_URL)


async def get_db() -> AsyncSession:
    """session 生成器"""
    session = async_db_session()
    try:
        yield session
    except Exception as se:
        await session.rollback()
        raise se
    finally:
        await session.close()

# Session Annotated
CurrentSession = Annotated[AsyncSession, Depends(get_db)]


