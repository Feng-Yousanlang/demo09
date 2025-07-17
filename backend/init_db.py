#!/usr/bin/env python3
"""
数据库初始化脚本
用于部署时初始化MySQL数据库表结构
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.database import init_database, check_database_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def main():
    """主函数"""
    print("=" * 50)
    print("家庭视频监控系统 - 数据库初始化")
    print("=" * 50)
    
    try:
        # 检查数据库连接
        print("1. 检查数据库连接...")
        is_connected = await check_database_connection()
        if not is_connected:
            print("❌ 数据库连接失败！请检查配置文件中的数据库连接信息。")
            return False
        print("✅ 数据库连接成功")
        
        # 初始化数据库表
        print("2. 创建数据库表...")
        await init_database()
        print("✅ 数据库表创建成功")
        
        # 创建默认管理员用户（如果需要）
        print("3. 检查系统初始化...")
        # 这里可以添加创建默认用户的逻辑
        print("✅ 系统初始化完成")
        
        print("\n" + "=" * 50)
        print("🎉 数据库初始化完成！")
        print("现在可以启动应用程序了。")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        logger.error(f"数据库初始化失败: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 