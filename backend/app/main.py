from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
from contextlib import asynccontextmanager
import asyncio

from app.api import auth, video, face, zone, events, analysis, system
from app.services.database import init_database
from app.services.video_stream import VideoStreamService
from app.services.ai_analysis import AIAnalysisService
from app.services.video_recording import video_recording_service
from app.services.video_cleanup import video_cleanup_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    await init_database()
    
    # 创建服务实例
    video_service = VideoStreamService()
    ai_service = AIAnalysisService()
    
    # 注入主事件循环
    main_loop = asyncio.get_running_loop()
    ai_service.set_loop(main_loop)
    video_service.set_loop(main_loop)
    video_cleanup_service.set_loop(main_loop)
    
    # 设置服务间依赖
    ai_service.set_video_service(video_service)
    
    # 启动后台服务
    await video_recording_service.start()
    # await video_cleanup_service.start()
    
    # 将服务实例存储到app状态中，供API调用
    app.state.video_service = video_service
    app.state.ai_service = ai_service
    app.state.video_recording_service = video_recording_service
    app.state.video_cleanup_service = video_cleanup_service
    
    yield
    
    # 关闭时清理（如果服务正在运行）
    if hasattr(video_service, 'is_running') and video_service.is_running:
        video_service.stop()
    if hasattr(ai_service, 'is_running') and ai_service.is_running:
        ai_service.stop()
    
    # 停止视频录制和清理服务
    await video_recording_service.stop()
    # await video_cleanup_service.stop()


app = FastAPI(
    title="家庭视频监控系统",
    description="智能家庭监控系统API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
app.mount("/static", StaticFiles(directory="app/media"), name="static")

# 视频文件静态服务（特殊路径）
import os
video_static_path = "C:/Users/86195/Desktop/homevideo/backend/app/app/media/videos"
if os.path.exists(video_static_path):
    app.mount("/static/videos", StaticFiles(directory=video_static_path), name="videos")

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(video.router, prefix="/api/video", tags=["视频"])
app.include_router(face.router, prefix="/api/face", tags=["人脸识别"])
app.include_router(zone.router, prefix="/api/zone", tags=["危险区域"])
app.include_router(events.router, prefix="/api/events", tags=["事件告警"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["行为分析"])
app.include_router(system.router, prefix="/api/system", tags=["系统状态"])


@app.websocket("/ws")
async def websocket_endpoint_handler(websocket: WebSocket):
    """WebSocket连接处理实时推送"""
    from app.services.websocket import websocket_endpoint
    await websocket_endpoint(websocket)


@app.get("/api/stream/mjpeg")
def mjpeg_stream(request: Request):
    """MJPEG流API，复用全局帧"""
    video_service = request.app.state.video_service
    return StreamingResponse(
        video_service.generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/")
async def root():
    return {"message": "家庭视频监控系统API服务正在运行"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    ) 