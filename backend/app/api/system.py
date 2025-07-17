from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any
import psutil
import asyncio
from datetime import datetime

from app.models.schemas import ResponseModel
from app.services.database import get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/status", response_model=ResponseModel)
async def get_system_status(request: Request, db: AsyncSession = Depends(get_db)):
    """获取系统整体状态"""
    try:
        # 获取服务实例
        video_service = getattr(request.app.state, 'video_service', None)
        ai_service = getattr(request.app.state, 'ai_service', None)
        
        # 视频服务状态
        video_status = {
            "running": getattr(video_service, 'is_running', False) if video_service else False,
            "camera_connected": False,
            "fps": 0
        }
        
        if video_service and hasattr(video_service, 'is_running') and video_service.is_running:
            video_status["camera_connected"] = True
            video_status["fps"] = getattr(video_service, 'current_fps', 0)
        
        # AI分析服务状态
        ai_status = {
            "running": getattr(ai_service, 'is_running', False) if ai_service else False,
            "analysis_queue_size": 0,
            "last_analysis": None
        }
        
        if ai_service and hasattr(ai_service, 'is_running') and ai_service.is_running:
            ai_status["analysis_queue_size"] = getattr(ai_service, 'queue_size', 0)
        
        # 数据库连接状态
        db_status = {"connected": True}
        try:
            await db.execute(text("SELECT 1"))
        except Exception as e:
            db_status = {"connected": False, "error": str(e)}
            logger.error(f"数据库连接检查失败: {e}")
        
        # 系统资源状态
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            system_resources = {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "memory_total": memory.total // (1024**3),  # GB
                "memory_available": memory.available // (1024**3),  # GB
                "disk_usage": disk.percent,
                "disk_total": disk.total // (1024**3),  # GB
                "disk_free": disk.free // (1024**3)  # GB
            }
        except Exception as e:
            logger.warning(f"获取系统资源信息失败: {e}")
            system_resources = {"error": "无法获取系统资源信息"}
        
        status_data = {
            "timestamp": datetime.now().isoformat(),
            "services": {
                "video": video_status,
                "ai_analysis": ai_status,
                "database": db_status
            },
            "system": system_resources,
            "uptime": getattr(request.app.state, 'start_time', datetime.now()).isoformat()
        }
        
        return ResponseModel(
            success=True,
            message="获取系统状态成功",
            data=status_data
        )
        
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取系统状态失败: {str(e)}"
        )


@router.get("/health", response_model=ResponseModel)
async def health_check():
    """系统健康检查"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "api": "ok",
                "memory": "ok",
                "disk": "ok"
            }
        }
        
        # 内存检查
        try:
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                health_status["checks"]["memory"] = "warning"
                health_status["status"] = "warning"
        except:
            health_status["checks"]["memory"] = "unknown"
        
        # 磁盘检查
        try:
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                health_status["checks"]["disk"] = "warning"
                health_status["status"] = "warning"
        except:
            health_status["checks"]["disk"] = "unknown"
        
        return ResponseModel(
            success=True,
            message="健康检查完成",
            data=health_status
        )
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return ResponseModel(
            success=False,
            message=f"健康检查失败: {str(e)}"
        )


@router.get("/info", response_model=ResponseModel)
async def get_system_info():
    """获取系统基本信息"""
    try:
        import platform
        import sys
        
        system_info = {
            "platform": platform.platform(),
            "system": platform.system(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "api_version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }
        
        return ResponseModel(
            success=True,
            message="获取系统信息成功",
            data=system_info
        )
        
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取系统信息失败: {str(e)}"
        )


@router.get("/settings", response_model=ResponseModel)
async def get_system_settings():
    """获取系统设置"""
    try:
        from app.config import settings
        
        # 返回系统配置信息
        config_data = {
            "basic": {
                "system_name": "家庭视频监控系统",
                "timezone": "Asia/Shanghai",
                "language": "zh-CN"
            },
            "video": {
                "camera_index": settings.CAMERA_INDEX,
                "width": settings.VIDEO_WIDTH,
                "height": settings.VIDEO_HEIGHT,
                "fps": settings.VIDEO_FPS
            },
            "ai": {
                "screenshot_interval": settings.SCREENSHOT_INTERVAL,
                "face_recognition_threshold": settings.FACE_RECOGNITION_THRESHOLD,
                "danger_zone_stay_threshold": settings.DANGER_ZONE_STAY_THRESHOLD
            },
            "alert": {
                "enable_email": False,
                "enable_websocket": True,
                "recipient_emails": []
            }
        }
        
        return ResponseModel(
            success=True,
            message="获取系统设置成功",
            data=config_data
        )
        
    except Exception as e:
        logger.error(f"获取系统设置失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取系统设置失败: {str(e)}"
        )


@router.post("/settings", response_model=ResponseModel)
async def save_system_settings(settings_data: dict):
    """保存系统设置"""
    try:
        # 这里可以实现设置保存逻辑
        # 目前仅返回成功状态
        logger.info(f"保存系统设置: {settings_data}")
        
        return ResponseModel(
            success=True,
            message="系统设置保存成功",
            data={"saved": True}
        )
        
    except Exception as e:
        logger.error(f"保存系统设置失败: {e}")
        return ResponseModel(
            success=False,
            message=f"保存系统设置失败: {str(e)}"
        )


@router.get("/storage", response_model=ResponseModel)
async def get_storage_info():
    """获取存储信息"""
    try:
        import psutil
        from pathlib import Path
        
        # 获取媒体目录信息
        media_path = Path("media")
        if media_path.exists():
            total_size = sum(f.stat().st_size for f in media_path.rglob('*') if f.is_file())
            file_count = len(list(media_path.rglob('*')))
        else:
            total_size = 0
            file_count = 0
        
        # 获取磁盘使用情况
        disk_usage = psutil.disk_usage('/')
        
        storage_info = {
            "media_storage": {
                "total_files": file_count,
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            },
            "disk_usage": {
                "total": disk_usage.total,
                "used": disk_usage.used,
                "free": disk_usage.free,
                "percent": disk_usage.percent
            }
        }
        
        return ResponseModel(
            success=True,
            message="获取存储信息成功",
            data=storage_info
        )
        
    except Exception as e:
        logger.error(f"获取存储信息失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取存储信息失败: {str(e)}"
        ) 