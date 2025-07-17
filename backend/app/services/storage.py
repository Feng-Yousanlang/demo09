import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime
import aiofiles
from PIL import Image

from app.config import settings, get_media_url
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StorageService:
    """文件存储服务 - 统一的存储接口"""
    
    def __init__(self):
        self.base_path = Path(settings.MEDIA_PATH)
        self.face_path = Path(settings.FACE_IMAGES_PATH)
        self.screenshot_path = Path(settings.SCREENSHOTS_PATH)
        # 使用用户指定的视频保存路径
        self.video_path = Path("C:/Users/86195/Desktop/homevideo/backend/app/app/media/videos")
        
        # 确保目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保所有存储目录存在"""
        for path in [self.base_path, self.face_path, self.screenshot_path, self.video_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def _generate_filename(self, prefix: str, extension: str) -> str:
        """生成唯一文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{unique_id}.{extension}"
    
    async def save_face_image(self, file_content: bytes, filename: Optional[str] = None) -> tuple[str, str]:
        """
        保存人脸图片
        返回: (文件路径, 访问URL)
        """
        try:
            if not filename:
                filename = self._generate_filename("face", "jpg")
            elif not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                filename += ".jpg"
            
            file_path = self.face_path / filename
            
            # 保存文件
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            
            # 生成访问URL
            relative_path = str(file_path.relative_to(self.base_path))
            url = get_media_url(str(file_path))
            
            logger.info(f"人脸图片保存成功: {file_path}")
            return str(file_path), url
            
        except Exception as e:
            logger.error(f"保存人脸图片失败: {e}")
            raise
    
    async def save_screenshot(self, image_data: bytes, prefix: str = "screenshot") -> tuple[str, str]:
        """
        保存截图
        返回: (文件路径, 访问URL)
        """
        try:
            filename = self._generate_filename(prefix, "jpg")
            file_path = self.screenshot_path / filename
            
            # 保存文件
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(image_data)
            
            # 生成访问URL
            url = get_media_url(str(file_path))
            
            logger.info(f"截图保存成功: {file_path}")
            return str(file_path), url
            
        except Exception as e:
            logger.error(f"保存截图失败: {e}")
            raise
    
    async def save_video_clip(self, video_data: bytes, prefix: str = "clip") -> tuple[str, str]:
        """
        保存视频片段
        返回: (文件路径, 访问URL)
        """
        try:
            filename = self._generate_filename(prefix, "mp4")
            file_path = self.video_path / filename
            
            # 保存文件
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(video_data)
            
            # 生成访问URL
            url = get_media_url(str(file_path))
            
            logger.info(f"视频片段保存成功: {file_path}")
            return str(file_path), url
            
        except Exception as e:
            logger.error(f"保存视频片段失败: {e}")
            raise
    
    def get_file_url(self, file_path: str) -> str:
        """根据文件路径生成访问URL"""
        return get_media_url(file_path)
    
    async def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"文件删除成功: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除文件失败: {file_path}, 错误: {e}")
            return False
    
    async def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在"""
        return Path(file_path).exists()
    
    def get_file_size(self, file_path: str) -> int:
        """获取文件大小（字节）"""
        try:
            return Path(file_path).stat().st_size
        except:
            return 0
    
    async def optimize_image(self, file_path: str, max_size: tuple = (800, 600)) -> bool:
        """优化图片尺寸和质量"""
        try:
            with Image.open(file_path) as img:
                # 如果图片大于最大尺寸，则调整
                if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    img.save(file_path, format='JPEG', quality=85, optimize=True)
                    logger.info(f"图片优化完成: {file_path}")
            return True
        except Exception as e:
            logger.error(f"图片优化失败: {file_path}, 错误: {e}")
            return False
    
    def get_video_info(self, video_path: str) -> dict:
        """获取视频文件信息"""
        try:
            import cv2
            
            path = Path(video_path)
            if not path.exists():
                return {"error": "文件不存在"}
            
            # 获取文件基本信息
            file_size = path.stat().st_size
            
            # 获取视频元数据
            cap = cv2.VideoCapture(str(path))
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                duration = frame_count / fps if fps > 0 else 0
                
                cap.release()
                
                return {
                    "file_size": file_size,
                    "duration": duration,
                    "fps": fps,
                    "frame_count": int(frame_count),
                    "resolution": f"{width}x{height}",
                    "width": width,
                    "height": height
                }
            else:
                return {"error": "无法打开视频文件"}
                
        except Exception as e:
            logger.error(f"获取视频信息失败: {video_path}, 错误: {e}")
            return {"error": str(e)}
    
    def is_video_file(self, file_path: str) -> bool:
        """检查文件是否为视频格式"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
        return Path(file_path).suffix.lower() in video_extensions
    
    async def cleanup_old_videos(self, days_old: int = 7) -> int:
        """清理指定天数前的旧视频文件"""
        try:
            from datetime import datetime, timedelta
            
            cutoff_time = datetime.now() - timedelta(days=days_old)
            cleaned_count = 0
            
            for video_file in self.video_path.glob("*.mp4"):
                try:
                    file_mtime = datetime.fromtimestamp(video_file.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        video_file.unlink()
                        cleaned_count += 1
                        logger.info(f"清理旧视频文件: {video_file}")
                except Exception as e:
                    logger.warning(f"清理视频文件失败: {video_file}, 错误: {e}")
            
            logger.info(f"清理完成，共删除 {cleaned_count} 个旧视频文件")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理旧视频文件失败: {e}")
            return 0
    
    def get_video_storage_stats(self) -> dict:
        """获取视频存储统计信息"""
        try:
            total_size = 0
            file_count = 0
            
            for video_file in self.video_path.glob("*.mp4"):
                try:
                    total_size += video_file.stat().st_size
                    file_count += 1
                except:
                    continue
            
            # 转换为MB
            total_size_mb = total_size / (1024 * 1024)
            
            return {
                "total_files": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size_mb, 2),
                "storage_path": str(self.video_path)
            }
            
        except Exception as e:
            logger.error(f"获取视频存储统计失败: {e}")
            return {"error": str(e)}


class CloudStorageService(StorageService):
    """云端存储服务 - 为未来扩展预留"""
    
    def __init__(self, cloud_config: dict = None):
        super().__init__()
        self.cloud_config = cloud_config or {}
        # 这里可以初始化OSS、S3等云存储客户端
    
    async def upload_to_cloud(self, local_path: str) -> str:
        """上传文件到云端存储（预留接口）"""
        # TODO: 实现云端上传逻辑
        # 返回云端文件URL
        pass
    
    async def download_from_cloud(self, cloud_url: str, local_path: str) -> bool:
        """从云端下载文件（预留接口）"""
        # TODO: 实现云端下载逻辑
        pass


# 全局存储服务实例
storage_service = StorageService() 