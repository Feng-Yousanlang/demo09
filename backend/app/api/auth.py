from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ResponseModel, AdminLogin, AdminRegister, AdminResponse, Token
from app.services.database import get_db, check_database_connection
from app.services.websocket import websocket_manager
from app.services.auth_service import auth_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/system/health", response_model=ResponseModel)
async def system_health_check(request: Request):
    """系统健康检查"""
    try:
        # 检查数据库连接
        db_health = await check_database_connection()
        
        # 检查视频服务
        video_service = request.app.state.video_service
        video_health = video_service.health_check() if video_service else {}
        
        # 检查AI服务
        ai_service = request.app.state.ai_service
        ai_health = ai_service.get_statistics() if ai_service else {}
        
        # 检查WebSocket连接
        ws_health = {
            "active_connections": websocket_manager.get_connection_count(),
            "connection_info": len(websocket_manager.get_connection_info())
        }
        
        health_data = {
            "database": {
                "status": "healthy" if db_health else "unhealthy",
                "connected": db_health
            },
            "video_service": {
                "status": "healthy" if video_health.get("service_running", False) else "unhealthy",
                "details": video_health
            },
            "ai_service": {
                "status": "healthy" if ai_health.get("is_running", False) else "unhealthy",
                "details": ai_health
            },
            "websocket": {
                "status": "healthy",
                "details": ws_health
            },
            "overall_status": "healthy" if all([
                db_health,
                video_health.get("service_running", False),
                ai_health.get("is_running", False)
            ]) else "degraded"
        }
        
        return ResponseModel(
            success=True,
            message="系统健康检查完成",
            data=health_data
        )
    
    except Exception as e:
        logger.error(f"系统健康检查失败: {e}")
        return ResponseModel(
            success=False,
            message=f"系统健康检查失败: {str(e)}"
        )


@router.get("/system/info", response_model=ResponseModel)
async def get_system_info():
    """获取系统信息"""
    try:
        import platform
        import psutil
        import sys
        from datetime import datetime
        
        # 系统基本信息
        system_info = {
            "platform": platform.platform(),
            "python_version": sys.version,
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_usage": {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free,
                "used": psutil.disk_usage('/').used
            },
            "server_time": datetime.now().isoformat(),
            "uptime": "系统运行中"  # 可以后续增加更精确的启动时间统计
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


@router.get("/system/config", response_model=ResponseModel)
async def get_system_config():
    """获取系统配置信息"""
    try:
        from app.config import settings
        
        # 安全地暴露配置信息（隐藏敏感信息）
        config_info = {
            "video": {
                "width": settings.VIDEO_WIDTH,
                "height": settings.VIDEO_HEIGHT,
                "fps": settings.VIDEO_FPS,
                "camera_index": settings.CAMERA_INDEX
            },
            "ai": {
                "screenshot_interval": settings.SCREENSHOT_INTERVAL,
                "danger_zone_stay_threshold": settings.DANGER_ZONE_STAY_THRESHOLD,
                "face_recognition_threshold": settings.FACE_RECOGNITION_THRESHOLD
            },
            "websocket": {
                "heartbeat_interval": settings.WS_HEARTBEAT_INTERVAL
            },
            "storage": {
                "media_path": settings.MEDIA_PATH,
                "face_images_path": settings.FACE_IMAGES_PATH,
                "screenshots_path": settings.SCREENSHOTS_PATH,
                "video_clips_path": settings.VIDEO_CLIPS_PATH
            }
        }
        
        return ResponseModel(
            success=True,
            message="获取系统配置成功",
            data=config_info
        )
    
    except Exception as e:
        logger.error(f"获取系统配置失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取系统配置失败: {str(e)}"
        )


@router.post("/system/reload", response_model=ResponseModel)
async def reload_system_data():
    """重新加载系统数据"""
    try:
        # 重新加载人脸数据
        from app.services.face_recognition import face_service
        await face_service.load_known_faces()
        
        # 重新加载危险区域数据
        from app.services.zone_detection import zone_service
        await zone_service.load_danger_zones()
        
        return ResponseModel(
            success=True,
            message="系统数据重新加载成功",
            data={
                "known_faces_count": face_service.get_known_faces_count(),
                "danger_zones_count": len(zone_service.danger_zones)
            }
        )
    
    except Exception as e:
        logger.error(f"重新加载系统数据失败: {e}")
        return ResponseModel(
            success=False,
            message=f"重新加载系统数据失败: {str(e)}"
        )


@router.get("/websocket/status", response_model=ResponseModel)
async def get_websocket_status():
    """获取WebSocket连接状态"""
    try:
        status_info = {
            "active_connections": websocket_manager.get_connection_count(),
            "connection_details": websocket_manager.get_connection_info()
        }
        
        return ResponseModel(
            success=True,
            message="获取WebSocket状态成功",
            data=status_info
        )
    
    except Exception as e:
        logger.error(f"获取WebSocket状态失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取WebSocket状态失败: {str(e)}"
        )


@router.post("/websocket/broadcast", response_model=ResponseModel)
async def broadcast_message(message: dict):
    """广播消息给所有WebSocket客户端"""
    try:
        await websocket_manager.broadcast(message)
        
        return ResponseModel(
            success=True,
            message="消息广播成功",
            data={
                "message": message,
                "connections_count": websocket_manager.get_connection_count()
            }
        )
    
    except Exception as e:
        logger.error(f"广播消息失败: {e}")
        return ResponseModel(
            success=False,
            message=f"广播消息失败: {str(e)}"
        )


@router.post("/admin/register", response_model=ResponseModel)
async def register_admin(admin_data: AdminRegister, db: AsyncSession = Depends(get_db)):
    """管理员注册"""
    try:
        # 检查用户名是否已存在
        existing_admin = await auth_service.get_admin_by_username(db, admin_data.username)
        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # 创建新管理员
        admin = await auth_service.create_admin(db, admin_data.username, admin_data.password)
        
        return ResponseModel(
            success=True,
            message="管理员注册成功",
            data=AdminResponse.from_orm(admin)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"管理员注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )


@router.post("/admin/login", response_model=ResponseModel)
async def login_admin(admin_data: AdminLogin, db: AsyncSession = Depends(get_db)):
    """管理员登录"""
    try:
        # 验证管理员凭据
        admin = await auth_service.authenticate_admin(db, admin_data.username, admin_data.password)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 生成JWT令牌
        access_token = auth_service.create_access_token(
            data={"sub": admin.username}
        )
        
        return ResponseModel(
            success=True,
            message="登录成功",
            data={
                "token": Token(access_token=access_token),
                "admin": AdminResponse.from_orm(admin)
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"管理员登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


@router.post("/admin/verify-token", response_model=ResponseModel)
async def verify_token(token_data: dict, db: AsyncSession = Depends(get_db)):
    """验证JWT令牌"""
    try:
        token = token_data.get("token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少令牌"
            )
        
        # 验证令牌
        payload = auth_service.verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        # 获取管理员信息
        admin = await auth_service.get_admin_by_username(db, payload["username"])
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="管理员不存在"
            )
        
        return ResponseModel(
            success=True,
            message="令牌验证成功",
            data=AdminResponse.from_orm(admin)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"令牌验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="验证失败，请稍后重试"
        ) 