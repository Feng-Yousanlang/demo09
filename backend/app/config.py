import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "mysql+aiomysql://root:123456@localhost/homevideo"
    
    # Qwen API配置
    QWEN_API_KEY: str = "sk-f86f2b832a44491c87090d357c260e5a"
    QWEN_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # 文件存储配置
    MEDIA_PATH: str = "app/media"
    FACE_IMAGES_PATH: str = "app/media/faces"
    SCREENSHOTS_PATH: str = "app/media/screenshots"
    VIDEO_CLIPS_PATH: str = "app/media/videos"
    
    # 视频流配置
    CAMERA_INDEX: int = 0  # 摄像头索引，0为默认摄像头
    VIDEO_WIDTH: int = 640
    VIDEO_HEIGHT: int = 480
    VIDEO_FPS: int = 15
    
    # AI分析配置
    SCREENSHOT_INTERVAL: int = 5  # 截图间隔（秒）
    DANGER_ZONE_STAY_THRESHOLD: int = 10  # 危险区域停留告警阈值（秒）
    
    # 视频录制配置
    VIDEO_BUFFER_DURATION: float = 2.0  # 视频缓冲时长（秒）
    VIDEO_RECORDING_FPS: int = 10  # 视频录制帧率
    VIDEO_CODEC: str = "mp4v"  # 视频编码格式
    VIDEO_QUALITY: int = 80  # 视频质量（1-100）
    
    # 视频清理配置
    VIDEO_RETENTION_DAYS: int = 7  # 视频保留天数
    VIDEO_CLEANUP_INTERVAL: int = 3600  # 清理检查间隔（秒）
    DISK_USAGE_THRESHOLD: int = 80  # 磁盘使用率阈值（百分比）
    VIDEO_CLEANUP_BATCH_SIZE: int = 50  # 批量清理大小
    
    # WebSocket配置
    WS_HEARTBEAT_INTERVAL: int = 30
    
    # 人脸识别配置
    FACE_RECOGNITION_THRESHOLD: float = 0.5
    
    # JWT认证配置
    JWT_SECRET_KEY: str = "homevideo_jwt_secret_key_2025"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    JWT_ALGORITHM: str = "HS256"
    
    # RTMP流配置
    RTMP_STREAM_URL: str = "rtmp://121.41.28.35:9090/live/obs_stream"
    
    class Config:
        env_file = ".env"


# 创建全局设置实例
settings = Settings()


def get_media_url(file_path: str) -> str:
    """生成媒体文件访问URL"""
    # 标准化路径分隔符（Windows用反斜杠，Web用正斜杠）
    normalized_path = file_path.replace('\\', '/')
    # 移除media前缀（如果存在）
    if normalized_path.startswith(settings.MEDIA_PATH + '/'):
        relative_path = normalized_path.replace(settings.MEDIA_PATH + '/', '')
    elif normalized_path.startswith(settings.MEDIA_PATH):
        relative_path = normalized_path.replace(settings.MEDIA_PATH, '').lstrip('/')
    else:
        # 如果路径包含media目录，提取相对部分
        if '/media/' in normalized_path:
            relative_path = normalized_path.split('/media/')[-1]
        elif '\\media\\' in file_path:
            relative_path = file_path.split('\\media\\')[-1].replace('\\', '/')
        else:
            relative_path = normalized_path
    
    return f"/static/{relative_path}"


def ensure_media_dirs():
    """确保媒体文件目录存在"""
    import os
    os.makedirs(settings.MEDIA_PATH, exist_ok=True)
    os.makedirs(settings.FACE_IMAGES_PATH, exist_ok=True)
    os.makedirs(settings.SCREENSHOTS_PATH, exist_ok=True)
    os.makedirs(settings.VIDEO_CLIPS_PATH, exist_ok=True) 