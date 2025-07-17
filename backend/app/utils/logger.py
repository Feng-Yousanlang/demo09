import logging
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path


def setup_logging():
    """设置日志配置"""
    
    # 创建logs目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 配置日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 创建formatter
    formatter = logging.Formatter(log_format, date_format)
    
    # 配置根logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除现有handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 文件handler - 应用日志
    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(
        log_dir / f"app_{today}.log",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 错误日志handler
    error_handler = logging.FileHandler(
        log_dir / f"error_{today}.log",
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的logger"""
    return logging.getLogger(name)


class DatabaseLogger:
    """数据库日志记录器"""
    
    def __init__(self):
        self.logger = get_logger("database_logger")
    
    async def log_to_database(
        self,
        level: str,
        message: str,
        module: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """记录日志到数据库"""
        try:
            # 这里需要导入相关模块，避免循环导入
            from app.services.database import AsyncSessionLocal
            from app.models.database import SystemLog
            
            async with AsyncSessionLocal() as session:
                log_entry = SystemLog(
                    level=level,
                    module=module,
                    message=message,
                    metadata=metadata
                )
                session.add(log_entry)
                await session.commit()
                
        except Exception as e:
            self.logger.error(f"记录数据库日志失败: {e}")


# 初始化日志
setup_logging()

# 全局数据库日志记录器
db_logger = DatabaseLogger() 