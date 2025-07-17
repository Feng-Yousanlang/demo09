from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """事件类型枚举"""
    stranger = "stranger"
    zone_violation = "zone_violation"
    abnormal_behavior = "abnormal_behavior"


class Severity(str, Enum):
    """严重程度枚举"""
    low = "low"
    medium = "medium"
    high = "high"


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# 管理员认证相关模型
class AdminLogin(BaseModel):
    """管理员登录请求模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class AdminRegister(BaseModel):
    """管理员注册请求模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class AdminResponse(BaseModel):
    """管理员响应模型"""
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT令牌响应模型"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """JWT令牌数据模型"""
    username: Optional[str] = None


# 用户相关模型
class UserCreate(BaseModel):
    """创建用户请求模型"""
    name: str = Field(..., min_length=1, max_length=100, description="用户姓名")


class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    name: str
    face_image_url: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


# 危险区域相关模型
class DangerZoneCreate(BaseModel):
    """创建危险区域请求模型"""
    name: str = Field(..., min_length=1, max_length=100, description="区域名称")
    zone_type: str = Field(default="polygon", description="区域类型")
    coordinates: List[Dict[str, float]] = Field(..., description="区域坐标点")
    stay_threshold: int = Field(default=10, ge=1, description="停留告警阈值（秒）")


class DangerZoneUpdate(BaseModel):
    """更新危险区域请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    coordinates: Optional[List[Dict[str, float]]] = None
    stay_threshold: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class DangerZoneResponse(BaseModel):
    """危险区域响应模型"""
    id: int
    name: str
    zone_type: str
    coordinates: List[Dict[str, float]]
    stay_threshold: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 事件相关模型
class EventBase(BaseModel):
    event_type: str
    title: str
    description: Optional[str] = None
    screenshot_path: Optional[str] = None
    video_clip_path: Optional[str] = None
    confidence: Optional[float] = None
    location: Optional[Dict[str, Any]] = None
    event_data: Optional[Dict[str, Any]] = None
    is_processed: bool = False
    severity: str = "medium"

class EventCreate(EventBase):
    pass

class Event(EventBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class EventResponse(BaseModel):
    """事件响应模型"""
    id: int
    event_type: str
    title: str
    description: Optional[str]
    screenshot_url: Optional[str]
    video_clip_url: Optional[str]
    video_duration: Optional[float] = Field(None, description="视频时长（秒）")
    video_size: Optional[int] = Field(None, description="视频文件大小（字节）")
    has_video: bool = Field(default=False, description="是否有视频文件")
    confidence: Optional[float]
    location: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    is_processed: bool
    is_read: bool = Field(default=False, description="是否已读")
    status: str = Field(default="pending", description="处理状态")
    severity: str
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class EventUpdate(BaseModel):
    """更新事件请求模型"""
    is_processed: Optional[bool] = None


# 分析日志相关模型
class AnalysisLogCreate(BaseModel):
    """创建分析日志请求模型"""
    analysis_type: str
    screenshot_path: str
    result: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    processing_time: Optional[float] = Field(None, ge=0)


class AnalysisLogResponse(BaseModel):
    """分析日志响应模型"""
    id: int
    analysis_type: str
    screenshot_url: str
    result: Optional[Dict[str, Any]]
    confidence: Optional[float]
    processing_time: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# 系统日志相关模型
class SystemLogBase(BaseModel):
    level: str
    module: Optional[str] = None
    message: str
    log_data: Optional[Dict[str, Any]] = None

class SystemLogCreate(SystemLogBase):
    pass

class SystemLog(SystemLogBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# 通用响应模型
class ResponseModel(BaseModel):
    """通用响应模型"""
    success: bool = True
    message: str = "操作成功"
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    """分页响应模型"""
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


# WebSocket消息模型
class WSMessage(BaseModel):
    """WebSocket消息模型"""
    type: str  # event_alert, system_status, etc.
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


# 视频相关模型
class VideoStorageStats(BaseModel):
    """视频存储统计模型"""
    total_files: int = Field(description="视频文件总数")
    total_size_bytes: int = Field(description="总大小（字节）")
    total_size_mb: float = Field(description="总大小（MB）")
    storage_path: str = Field(description="存储路径") 