from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import asyncio
from typing import AsyncGenerator

from app.config import settings
from app.models.database import Base
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # 生产环境设为False
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 创建异步会话
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"数据库会话错误: {e}")
            raise
        finally:
            await session.close()


async def init_database():
    """初始化数据库表"""
    try:
        logger.info("开始初始化数据库...")
        
        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("数据库初始化完成")
        
        # 确保媒体目录存在
        from app.config import ensure_media_dirs
        ensure_media_dirs()
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


async def check_database_connection():
    """检查数据库连接"""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"数据库连接检查失败: {e}")
        return False


class DatabaseService:
    """数据库服务类"""
    
    def __init__(self):
        self.engine = engine
        self.session_factory = AsyncSessionLocal
    
    async def get_session(self) -> AsyncSession:
        """获取数据库会话"""
        return AsyncSessionLocal()
    
    async def health_check(self) -> bool:
        """健康检查"""
        return await check_database_connection()
    
    async def close_connections(self):
        """关闭所有数据库连接"""
        await engine.dispose()


# 全局数据库服务实例
db_service = DatabaseService() 