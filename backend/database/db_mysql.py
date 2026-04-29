import sys
from typing import AsyncGenerator
from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.conf import settings

def initialize_database():
    """
    初始化唯一的数据库引擎和会话工厂。
    这种方式确保了全局只有一个 Engine 和 SessionMaker。
    """
    try:
        engine = create_async_engine(
            url=settings.DATABASE_URL,
            echo=False,
            future=True,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=20,       # 既然是唯一库，可以适当调大连接池
            max_overflow=10,
            pool_timeout=30,
        )
        # 创建会话工厂
        session_factory = async_sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession  # 显式指定类
        )
        return engine, session_factory
    except Exception as e:
        logger.error('数据库链接失败 {}', e)
        sys.exit()

# 全局单例对象
async_engine, async_db_session = initialize_database()

# --- 2. Session 生成器 ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入使用的 Session 生成器。
    yield 确保了请求结束后自动关闭连接。
    """
    async with async_db_session() as session:
        try:
            yield session
            # 如果你想在每个请求结束时自动 commit，可以在这里写
            # await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # async with 会自动调用 session.close()
            pass


