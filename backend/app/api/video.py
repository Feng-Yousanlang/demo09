from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional

from app.models.schemas import ResponseModel
from app.services.video_stream import VideoStreamService
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def get_video_service(request: Request) -> VideoStreamService:
    """获取视频流服务实例"""
    return request.app.state.video_service


@router.get("/stream")
async def video_stream(video_service: VideoStreamService = Depends(get_video_service)):
    """获取MJPEG视频流"""
    try:
        if not video_service or not hasattr(video_service, 'is_running'):
            logger.error("视频服务未初始化")
            return JSONResponse(
                status_code=503,
                content={"message": "视频服务未初始化"}
            )
            
        if not video_service.is_running:
            logger.warning("视频流服务未运行")
            return JSONResponse(
                status_code=503,
                content={"message": "视频流服务未运行"}
            )
        
        # 检查摄像头状态
        if not video_service.camera or not video_service.camera.isOpened():
            logger.error("摄像头未连接或已断开")
            return JSONResponse(
                status_code=503,
                content={"message": "摄像头未连接"}
            )
        
        # 检查是否有可用帧
        current_frame = video_service.get_current_frame()
        if current_frame is None:
            logger.warning("无法获取视频帧")
            return JSONResponse(
                status_code=503,
                content={"message": "无法获取视频帧"}
            )
        
        logger.info("开始提供MJPEG视频流")
        return StreamingResponse(
            video_service.generate_mjpeg_stream(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except Exception as e:
        logger.error(f"获取视频流失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"message": f"视频流获取失败: {str(e)}"}
        )


@router.post("/screenshot")
async def take_screenshot(
    prefix: Optional[str] = "manual",
    video_service: VideoStreamService = Depends(get_video_service)
):
    """手动截图"""
    try:
        if not video_service.is_running:
            return ResponseModel(
                success=False,
                message="视频流服务未运行"
            )
        
        result = await video_service.take_screenshot(prefix)
        if result:
            file_path, url = result
            return ResponseModel(
                success=True,
                message="截图成功",
                data={
                    "file_path": file_path,
                    "url": url,
                    "timestamp": "now"
                }
            )
        else:
            return ResponseModel(
                success=False,
                message="截图失败"
            )
    
    except Exception as e:
        logger.error(f"手动截图失败: {e}")
        return ResponseModel(
            success=False,
            message=f"截图失败: {str(e)}"
        )


@router.get("/info")
async def get_video_info(video_service: VideoStreamService = Depends(get_video_service)):
    """获取视频流信息"""
    try:
        info = video_service.get_video_info()
        return ResponseModel(
            success=True,
            message="获取视频信息成功",
            data=info
        )
    except Exception as e:
        logger.error(f"获取视频信息失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取视频信息失败: {str(e)}"
        )


@router.get("/health")
async def video_health_check(video_service: VideoStreamService = Depends(get_video_service)):
    """视频服务健康检查"""
    try:
        health_info = video_service.health_check()
        return ResponseModel(
            success=True,
            message="视频服务健康检查完成",
            data=health_info
        )
    except Exception as e:
        logger.error(f"视频服务健康检查失败: {e}")
        return ResponseModel(
            success=False,
            message=f"健康检查失败: {str(e)}"
        ) 

@router.post("/camera/start")
async def start_camera(request: Request):
    """启动摄像头监控"""
    try:
        video_service = request.app.state.video_service
        ai_service = request.app.state.ai_service
        
        # 启动视频流服务
        if not getattr(video_service, 'is_running', False):
            video_service.start()
        
        # 启动AI分析服务
        if not getattr(ai_service, 'is_running', False):
            ai_service.start()
        
        return {"success": True, "message": "摄像头监控已启动"}
    except Exception as e:
        logger.error(f"启动摄像头失败: {e}")
        return {"success": False, "message": f"启动失败: {str(e)}"}

@router.post("/camera/stop")
async def stop_camera(request: Request):
    """停止摄像头监控"""
    try:
        video_service = request.app.state.video_service
        ai_service = request.app.state.ai_service
        
        # 停止AI分析服务
        if getattr(ai_service, 'is_running', False):
            ai_service.stop()
        
        # 停止视频流服务
        if getattr(video_service, 'is_running', False):
            video_service.stop()
        
        return {"success": True, "message": "摄像头监控已停止"}
    except Exception as e:
        logger.error(f"停止摄像头失败: {e}")
        return {"success": False, "message": f"停止失败: {str(e)}"}

@router.get("/camera/status")
async def get_camera_status(request: Request):
    """获取摄像头状态"""
    try:
        video_service = request.app.state.video_service
        ai_service = request.app.state.ai_service
        
        video_running = getattr(video_service, 'is_running', False)
        ai_running = getattr(ai_service, 'is_running', False)
        
        return {
            "video_stream": video_running,
            "ai_analysis": ai_running,
            "status": "running" if (video_running and ai_running) else "stopped"
        }
    except Exception as e:
        logger.error(f"获取摄像头状态失败: {e}")
        return {"video_stream": False, "ai_analysis": False, "status": "error"} 