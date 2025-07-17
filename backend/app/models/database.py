from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional

Base = declarative_base()


class Admin(Base):
    __tablename__ = 'admins'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    """用户表 - 存储已注册的人脸信息"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="用户姓名")
    face_image_path = Column(String(255), nullable=False, comment="人脸图片路径")
    face_encoding = Column(Text, nullable=False, comment="人脸特征编码（JSON格式）")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    is_active = Column(Boolean, default=True, comment="是否启用")


class DangerZone(Base):
    """危险区域表"""
    __tablename__ = "danger_zones"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="区域名称")
    zone_type = Column(String(50), default="polygon", comment="区域类型：polygon/circle")
    coordinates = Column(JSON, nullable=False, comment="区域坐标点（JSON格式）")
    stay_threshold = Column(Integer, default=10, comment="停留告警阈值（秒）")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")


class Event(Base):
    """事件表 - 存储所有告警事件"""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, comment="事件类型：stranger/zone_violation/abnormal_behavior")
    title = Column(String(200), nullable=False, comment="事件标题")
    description = Column(Text, comment="事件描述")
    screenshot_path = Column(String(255), comment="事件截图路径")
    video_clip_path = Column(String(255), comment="视频片段路径")
    confidence = Column(Float, comment="置信度")
    location = Column(JSON, comment="事件位置信息（坐标等）")
    event_data = Column(JSON, comment="其他元数据")
    is_processed = Column(Boolean, default=False, comment="是否已处理")
    is_read = Column(Boolean, default=False, comment="是否已读")
    status = Column(String(20), default="pending", comment="处理状态：pending/processing/resolved")
    severity = Column(String(20), default="medium", comment="严重程度：low/medium/high")
    created_at = Column(DateTime, default=func.now(), comment="发生时间")
    processed_at = Column(DateTime, comment="处理时间")


class AnalysisLog(Base):
    """分析日志表 - 记录AI分析结果"""
    __tablename__ = "analysis_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    analysis_type = Column(String(50), nullable=False, comment="分析类型：face_recognition/behavior_analysis/zone_detection")
    screenshot_path = Column(String(255), nullable=False, comment="分析图片路径")
    result = Column(JSON, comment="分析结果（JSON格式）")
    confidence = Column(Float, comment="置信度")
    processing_time = Column(Float, comment="处理耗时（秒）")
    created_at = Column(DateTime, default=func.now(), comment="分析时间")


class SystemLog(Base):
    """系统日志表"""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), nullable=False, comment="日志级别：DEBUG/INFO/WARNING/ERROR")
    module = Column(String(100), comment="模块名称")
    message = Column(Text, nullable=False, comment="日志消息")
    log_data = Column(JSON, comment="附加数据")
    created_at = Column(DateTime, default=func.now(), comment="记录时间") 