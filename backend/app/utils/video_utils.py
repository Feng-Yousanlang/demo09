import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Tuple, Any
import json
from datetime import datetime, timedelta

from app.utils.logger import get_logger

logger = get_logger(__name__)


class VideoUtils:
    """视频处理工具类"""
    
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
    PREFERRED_CODEC = cv2.VideoWriter_fourcc(*'mp4v')
    
    @staticmethod
    def is_valid_video_format(file_path: str) -> bool:
        """检查文件是否为支持的视频格式"""
        try:
            path = Path(file_path)
            return path.suffix.lower() in VideoUtils.SUPPORTED_FORMATS
        except Exception as e:
            logger.error(f"检查视频格式失败: {e}")
            return False
    
    @staticmethod
    def get_video_info(video_path: str) -> Dict[str, Any]:
        """获取视频文件详细信息"""
        try:
            path = Path(video_path)
            if not path.exists():
                return {"error": "文件不存在"}
            
            # 基本文件信息
            file_stats = path.stat()
            file_info = {
                "file_path": str(path),
                "file_name": path.name,
                "file_size": file_stats.st_size,
                "created_time": datetime.fromtimestamp(file_stats.st_ctime),
                "modified_time": datetime.fromtimestamp(file_stats.st_mtime),
                "is_valid_format": VideoUtils.is_valid_video_format(str(path))
            }
            
            # 视频元数据
            cap = cv2.VideoCapture(str(path))
            if cap.isOpened():
                # 基本视频属性
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = frame_count / fps if fps > 0 else 0
                
                # 编码信息
                fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                codec = chr(fourcc & 0xFF) + chr((fourcc >> 8) & 0xFF) + \
                       chr((fourcc >> 16) & 0xFF) + chr((fourcc >> 24) & 0xFF)
                
                video_info = {
                    "width": width,
                    "height": height,
                    "resolution": f"{width}x{height}",
                    "fps": fps,
                    "frame_count": frame_count,
                    "duration_seconds": duration,
                    "duration_formatted": VideoUtils.format_duration(duration),
                    "codec": codec,
                    "fourcc": fourcc,
                    "aspect_ratio": width / height if height > 0 else 0,
                    "bitrate_estimate": (file_info["file_size"] * 8) / duration if duration > 0 else 0
                }
                
                cap.release()
                
                # 合并信息
                file_info.update(video_info)
                file_info["analysis_success"] = True
                
            else:
                file_info.update({
                    "analysis_success": False,
                    "error": "无法打开视频文件"
                })
            
            return file_info
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {video_path}, 错误: {e}")
            return {"error": str(e), "analysis_success": False}
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化视频时长"""
        if seconds <= 0:
            return "0s"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h{minutes}m{secs}s"
        elif minutes > 0:
            return f"{minutes}m{secs}s"
        else:
            return f"{secs}s"
    
    @staticmethod
    def format_file_size(bytes_size: int) -> str:
        """格式化文件大小"""
        if bytes_size == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(bytes_size)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f}{size_names[i]}"
    
    @staticmethod
    def validate_video_file(video_path: str) -> Tuple[bool, str]:
        """验证视频文件的完整性和可读性"""
        try:
            path = Path(video_path)
            
            # 检查文件存在
            if not path.exists():
                return False, "文件不存在"
            
            # 检查文件大小
            if path.stat().st_size == 0:
                return False, "文件大小为0"
            
            # 检查格式
            if not VideoUtils.is_valid_video_format(str(path)):
                return False, "不支持的视频格式"
            
            # 尝试打开视频
            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                return False, "无法打开视频文件"
            
            # 检查是否有帧
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_count <= 0:
                cap.release()
                return False, "视频没有有效帧"
            
            # 尝试读取第一帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                return False, "无法读取视频帧"
            
            return True, "视频文件有效"
            
        except Exception as e:
            logger.error(f"验证视频文件失败: {video_path}, 错误: {e}")
            return False, f"验证失败: {str(e)}"
    
    @staticmethod
    def extract_frame_at_timestamp(video_path: str, timestamp: float) -> Optional[np.ndarray]:
        """提取指定时间戳的视频帧"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None
            
            # 设置到指定时间戳
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            
            ret, frame = cap.read()
            cap.release()
            
            return frame if ret else None
            
        except Exception as e:
            logger.error(f"提取视频帧失败: {video_path}, 时间戳: {timestamp}, 错误: {e}")
            return None
    
    @staticmethod
    def extract_thumbnail(video_path: str, output_path: str, timestamp: float = 1.0) -> bool:
        """提取视频缩略图"""
        try:
            frame = VideoUtils.extract_frame_at_timestamp(video_path, timestamp)
            if frame is None:
                return False
            
            # 调整尺寸为缩略图
            height, width = frame.shape[:2]
            thumbnail_width = 320
            thumbnail_height = int(height * (thumbnail_width / width))
            
            thumbnail = cv2.resize(frame, (thumbnail_width, thumbnail_height))
            
            # 保存缩略图
            success = cv2.imwrite(output_path, thumbnail)
            
            if success:
                logger.info(f"生成视频缩略图成功: {output_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"生成视频缩略图失败: {video_path}, 错误: {e}")
            return False
    
    @staticmethod
    def optimize_video_for_web(input_path: str, output_path: str, 
                             target_width: int = 640, 
                             target_fps: int = 15,
                             quality: int = 80) -> bool:
        """优化视频用于Web播放"""
        try:
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                return False
            
            # 获取原始视频信息
            original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            original_fps = cap.get(cv2.CAP_PROP_FPS)
            
            # 计算目标尺寸
            aspect_ratio = original_width / original_height
            target_height = int(target_width / aspect_ratio)
            
            # 创建视频编码器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, target_fps, (target_width, target_height))
            
            if not out.isOpened():
                cap.release()
                return False
            
            # 处理帧
            frame_skip = max(1, int(original_fps / target_fps))
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 跳帧以达到目标帧率
                if frame_count % frame_skip == 0:
                    # 调整尺寸
                    resized_frame = cv2.resize(frame, (target_width, target_height))
                    out.write(resized_frame)
                
                frame_count += 1
            
            cap.release()
            out.release()
            
            logger.info(f"视频优化完成: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"视频优化失败: {input_path}, 错误: {e}")
            return False
    
    @staticmethod
    def get_video_quality_score(video_path: str) -> float:
        """评估视频质量分数（0-1）"""
        try:
            info = VideoUtils.get_video_info(video_path)
            if not info.get("analysis_success", False):
                return 0.0
            
            score = 0.0
            
            # 分辨率分数 (40%)
            width = info.get("width", 0)
            height = info.get("height", 0)
            resolution_score = min(1.0, (width * height) / (1920 * 1080))
            score += resolution_score * 0.4
            
            # 帧率分数 (30%)
            fps = info.get("fps", 0)
            fps_score = min(1.0, fps / 30.0)
            score += fps_score * 0.3
            
            # 码率分数 (20%)
            bitrate = info.get("bitrate_estimate", 0)
            bitrate_score = min(1.0, bitrate / (5 * 1024 * 1024))  # 5Mbps为参考
            score += bitrate_score * 0.2
            
            # 文件完整性分数 (10%)
            if info.get("frame_count", 0) > 0 and info.get("duration_seconds", 0) > 0:
                score += 0.1
            
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"评估视频质量失败: {video_path}, 错误: {e}")
            return 0.0


# 便捷函数
def validate_video(video_path: str) -> Tuple[bool, str]:
    """验证视频文件"""
    return VideoUtils.validate_video_file(video_path)


def get_video_metadata(video_path: str) -> Dict[str, Any]:
    """获取视频元数据"""
    return VideoUtils.get_video_info(video_path)


def create_video_thumbnail(video_path: str, thumbnail_path: str, timestamp: float = 1.0) -> bool:
    """创建视频缩略图"""
    return VideoUtils.extract_thumbnail(video_path, thumbnail_path, timestamp)


def format_video_duration(seconds: float) -> str:
    """格式化视频时长"""
    return VideoUtils.format_duration(seconds)


def format_file_size(bytes_size: int) -> str:
    """格式化文件大小"""
    return VideoUtils.format_file_size(bytes_size) 