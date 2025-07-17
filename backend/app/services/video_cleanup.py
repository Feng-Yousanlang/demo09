import asyncio
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import threading
import time

from app.config import settings
from app.utils.logger import get_logger
from app.services.database import AsyncSessionLocal
from app.models.database import Event
from sqlalchemy import select, and_

logger = get_logger(__name__)


class VideoCleanupService:
    """视频清理服务 - 自动清理旧视频文件和管理磁盘空间"""
    
    def __init__(self):
        self.is_running = False
        self.cleanup_thread: Optional[threading.Thread] = None
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # 清理配置
        self.video_retention_days = 7  # 视频保留天数
        self.disk_usage_threshold = 80  # 磁盘使用率阈值（百分比）
        self.cleanup_interval = 3600  # 清理检查间隔（秒，1小时）
        self.batch_size = 50  # 批量处理大小
        
        # 视频存储路径
        self.video_dir = Path("C:/Users/86195/Desktop/homevideo/backend/app/app/media/videos")

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """由应用在启动时注入主事件循环"""
        self.main_loop = loop
        
    async def start(self):
        """启动视频清理服务"""
        if self.is_running:
            return
            
        logger.info("启动视频清理服务...")
        self.is_running = True
        
        # 启动后台清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger.info("视频清理服务启动成功")
    
    async def stop(self):
        """停止视频清理服务"""
        logger.info("停止视频清理服务...")
        self.is_running = False
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5.0)
        
        logger.info("视频清理服务已停止")
    
    def _cleanup_loop(self):
        """清理循环（在后台线程运行）"""
        logger.info("视频清理循环启动")
        
        while self.is_running:
            try:
                if self.main_loop:
                    logger.info("计划执行清理任务...")
                    future = asyncio.run_coroutine_threadsafe(self._perform_cleanup(), self.main_loop)
                    # 设置超时以防任务卡住，例如比间隔少60秒
                    future.result(timeout=self.cleanup_interval - 60) 
                else:
                    logger.warning("视频清理服务缺少主事件循环，无法执行任务")

                # 等待下一次清理
                for _ in range(self.cleanup_interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"视频清理循环错误: {e}")
                time.sleep(300)  # 出错后等待5分钟再重试
        
        logger.info("视频清理循环结束")
    
    async def _perform_cleanup(self):
        """执行清理任务"""
        try:
            logger.info("开始执行视频清理任务")
            
            # 1. 按时间清理旧视频
            cleaned_by_time = await self._cleanup_old_videos()
            
            # 2. 检查磁盘使用率
            disk_usage = self._get_disk_usage()
            logger.info(f"当前磁盘使用率: {disk_usage:.1f}%")
            
            # 3. 如果磁盘使用率过高，进行额外清理
            cleaned_by_disk = 0
            if disk_usage > self.disk_usage_threshold:
                logger.warning(f"磁盘使用率过高 ({disk_usage:.1f}%)，开始额外清理")
                cleaned_by_disk = await self._cleanup_by_disk_usage()
            
            # 4. 清理数据库中已删除视频文件的记录
            cleaned_orphaned = await self._cleanup_orphaned_records()
            
            logger.info(f"清理任务完成 - 按时间清理: {cleaned_by_time}, 按磁盘清理: {cleaned_by_disk}, 孤立记录: {cleaned_orphaned}")
            
        except Exception as e:
            logger.error(f"执行清理任务失败: {e}")
    
    async def _cleanup_old_videos(self) -> int:
        """清理超过保留期的旧视频文件"""
        try:
            cutoff_time = datetime.now() - timedelta(days=self.video_retention_days)
            cleaned_count = 0
            
            # 查询需要清理的事件
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Event).where(
                        and_(
                            Event.created_at < cutoff_time,
                            Event.video_clip_path.isnot(None)
                        )
                    ).limit(self.batch_size)
                )
                old_events = result.scalars().all()
                
                for event in old_events:
                    try:
                        # 删除视频文件
                        video_path = Path(event.video_clip_path)
                        if video_path.exists():
                            video_path.unlink()
                            logger.debug(f"删除旧视频文件: {video_path}")
                        
                        # 清空数据库中的视频路径
                        event.video_clip_path = None
                        event.video_duration = None
                        event.video_size = None
                        
                        cleaned_count += 1
                        
                    except Exception as e:
                        logger.warning(f"清理事件 {event.id} 视频失败: {e}")
                
                await session.commit()
            
            if cleaned_count > 0:
                logger.info(f"按时间清理完成，删除 {cleaned_count} 个旧视频文件")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"按时间清理视频失败: {e}")
            return 0
    
    async def _cleanup_by_disk_usage(self) -> int:
        """根据磁盘使用率清理视频文件"""
        try:
            cleaned_count = 0
            target_free_space = 20  # 目标释放空间百分比
            
            # 查询最老的带视频的事件
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Event).where(
                        Event.video_clip_path.isnot(None)
                    ).order_by(Event.created_at.asc()).limit(self.batch_size)
                )
                oldest_events = result.scalars().all()
                
                for event in oldest_events:
                    try:
                        # 删除视频文件
                        video_path = Path(event.video_clip_path)
                        if video_path.exists():
                            file_size = video_path.stat().st_size
                            video_path.unlink()
                            logger.debug(f"磁盘清理删除视频: {video_path} ({file_size} bytes)")
                        
                        # 清空数据库中的视频路径
                        event.video_clip_path = None
                        event.video_duration = None
                        event.video_size = None
                        
                        cleaned_count += 1
                        
                        # 检查是否达到目标
                        current_usage = self._get_disk_usage()
                        if current_usage <= (self.disk_usage_threshold - target_free_space):
                            break
                            
                    except Exception as e:
                        logger.warning(f"磁盘清理事件 {event.id} 视频失败: {e}")
                
                await session.commit()
            
            if cleaned_count > 0:
                logger.info(f"磁盘清理完成，删除 {cleaned_count} 个视频文件")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"磁盘清理失败: {e}")
            return 0
    
    async def _cleanup_orphaned_records(self) -> int:
        """清理数据库中指向不存在文件的记录"""
        try:
            cleaned_count = 0
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Event).where(
                        Event.video_clip_path.isnot(None)
                    ).limit(self.batch_size)
                )
                events = result.scalars().all()
                
                for event in events:
                    try:
                        video_path = Path(event.video_clip_path)
                        if not video_path.exists():
                            # 文件不存在，清空记录
                            event.video_clip_path = None
                            event.video_duration = None
                            event.video_size = None
                            cleaned_count += 1
                            logger.debug(f"清理孤立记录: 事件 {event.id}")
                            
                    except Exception as e:
                        logger.warning(f"检查事件 {event.id} 视频文件失败: {e}")
                
                await session.commit()
            
            if cleaned_count > 0:
                logger.info(f"清理孤立记录完成，处理 {cleaned_count} 条记录")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理孤立记录失败: {e}")
            return 0
    
    def _get_disk_usage(self) -> float:
        """获取磁盘使用率"""
        try:
            if self.video_dir.exists():
                # 获取磁盘使用情况
                disk_usage = shutil.disk_usage(self.video_dir)
                total = disk_usage.total
                used = disk_usage.used
                usage_percent = (used / total) * 100
                return usage_percent
            return 0.0
        except Exception as e:
            logger.error(f"获取磁盘使用率失败: {e}")
            return 0.0
    
    async def manual_cleanup(self, days: int = None) -> dict:
        """手动触发清理"""
        try:
            logger.info(f"手动触发视频清理，保留天数: {days or self.video_retention_days}")
            
            if days is not None:
                original_days = self.video_retention_days
                self.video_retention_days = days
            
            # 执行清理
            cleaned_by_time = await self._cleanup_old_videos()
            cleaned_orphaned = await self._cleanup_orphaned_records()
            
            # 恢复原设置
            if days is not None:
                self.video_retention_days = original_days
            
            # 获取清理后状态
            disk_usage = self._get_disk_usage()
            video_stats = self._get_video_storage_stats()
            
            result = {
                "cleaned_by_time": cleaned_by_time,
                "cleaned_orphaned": cleaned_orphaned,
                "disk_usage_percent": disk_usage,
                "remaining_videos": video_stats["file_count"],
                "remaining_size_mb": video_stats["total_size_mb"]
            }
            
            logger.info(f"手动清理完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"手动清理失败: {e}")
            return {"error": str(e)}
    
    def _get_video_storage_stats(self) -> dict:
        """获取视频存储统计"""
        try:
            total_size = 0
            file_count = 0
            
            if self.video_dir.exists():
                for video_file in self.video_dir.glob("*.mp4"):
                    try:
                        total_size += video_file.stat().st_size
                        file_count += 1
                    except:
                        continue
            
            return {
                "file_count": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
        except Exception as e:
            logger.error(f"获取视频存储统计失败: {e}")
            return {"file_count": 0, "total_size_bytes": 0, "total_size_mb": 0}
    
    def get_cleanup_status(self) -> dict:
        """获取清理服务状态"""
        return {
            "is_running": self.is_running,
            "retention_days": self.video_retention_days,
            "disk_threshold_percent": self.disk_usage_threshold,
            "cleanup_interval_hours": self.cleanup_interval / 3600,
            "current_disk_usage": self._get_disk_usage(),
            "video_stats": self._get_video_storage_stats()
        }


# 全局视频清理服务实例
video_cleanup_service = VideoCleanupService() 