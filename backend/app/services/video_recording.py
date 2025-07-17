import asyncio
import cv2
import numpy as np
from collections import deque
from typing import List, Tuple, Optional
from datetime import datetime
import threading
from pathlib import Path
import time

from app.config import settings
from app.utils.logger import get_logger
from app.services.storage import storage_service

logger = get_logger(__name__)


class VideoFrame:
    """视频帧数据结构"""

    def __init__(self, frame: np.ndarray, timestamp: float):
        self.frame = frame
        self.timestamp = timestamp


class VideoRecordingService:
    """视频录制服务 - 处理事件前后2秒视频录制"""

    def __init__(self):
        # 初始化时不要创建队列，等到start时再创建
        self.recording_queue: Optional[asyncio.Queue] = None
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # 视频编码参数
        self.video_fps = 10  # 降低帧率减少文件大小
        self.video_codec = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_width = settings.VIDEO_WIDTH
        self.video_height = settings.VIDEO_HEIGHT

        # 确保视频保存目录存在
        self.video_dir = Path("C:/Users/86195/Desktop/homevideo/backend/app/app/media/videos")
        self.video_dir.mkdir(parents=True, exist_ok=True)

    async def start(self):
        """启动视频录制服务"""
        if self.is_running:
            return

        logger.info("启动视频录制服务...")
        self._loop = asyncio.get_running_loop()  # 获取当前事件循环
        self.recording_queue = asyncio.Queue()  # 现在才创建队列
        self.is_running = True
        self.worker_task = asyncio.create_task(self._process_recording_queue())
        logger.info("视频录制服务启动成功")

    async def stop(self):
        """停止视频录制服务"""
        if not self.is_running:
            return

        logger.info("停止视频录制服务...")
        self.is_running = False

        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        self.recording_queue = None
        self._loop = None
        logger.info("视频录制服务已停止")

    async def record_event_video(
            self,
            pre_frames: List[VideoFrame],
            post_frames: List[VideoFrame],
            event_id: int,
            event_type: str
    ) -> Tuple[Optional[str], Optional[float], Optional[int]]:
        """
        录制事件视频（前2秒 + 后2秒）
        返回: (视频文件路径, 视频时长, 文件大小)
        """
        if not self.is_running or not self.recording_queue:
            logger.warning("视频录制服务未运行，无法录制")
            return None, None, None

        try:
            # 生成视频文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"event_{event_id}_{event_type}_{timestamp}.mp4"
            video_path = self.video_dir / filename

            # 合并前后帧序列
            all_frames = pre_frames + post_frames
            if not all_frames:
                logger.warning(f"事件 {event_id} 没有可用帧进行录制")
                return None, None, None

            # 将录制任务加入队列
            recording_task = {
                'video_path': str(video_path),
                'frames': all_frames,
                'event_id': event_id
            }

            await self.recording_queue.put(recording_task)
            logger.info(f"事件 {event_id} 视频录制任务已加入队列: {filename}")

            # 等待录制完成并返回结果
            return await self._wait_for_recording_completion(str(video_path))

        except Exception as e:
            logger.error(f"创建视频录制任务失败: {e}")
            return None, None, None

    async def _wait_for_recording_completion(self, video_path: str) -> Tuple[
        Optional[str], Optional[float], Optional[int]]:
        """等待视频录制完成"""
        max_wait_time = 30  # 最大等待30秒
        wait_interval = 0.5  # 每0.5秒检查一次
        waited_time = 0

        while waited_time < max_wait_time:
            if Path(video_path).exists():
                # 等待文件写入完成
                await asyncio.sleep(1)

                # 计算文件大小和时长
                file_size = Path(video_path).stat().st_size
                duration = await self._get_video_duration(video_path)

                return video_path, duration, file_size

            await asyncio.sleep(wait_interval)
            waited_time += wait_interval

        logger.warning(f"视频录制超时: {video_path}")
        return None, None, None

    async def _get_video_duration(self, video_path: str) -> Optional[float]:
        """获取视频时长"""
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                duration = frame_count / fps if fps > 0 else None
                cap.release()
                return duration
        except Exception as e:
            logger.error(f"获取视频时长失败: {e}")
        return None

    async def _process_recording_queue(self):
        """处理视频录制队列"""
        logger.info("视频录制队列处理线程启动")

        while self.is_running and self.recording_queue:
            try:
                # 等待录制任务
                recording_task = await asyncio.wait_for(
                    self.recording_queue.get(),
                    timeout=1.0
                )

                # 执行视频编码
                await self._encode_video(recording_task)

            except asyncio.TimeoutError:
                # 超时是正常的，继续等待下一个任务
                continue
            except Exception as e:
                logger.error(f"处理视频录制队列错误: {e}")
                await asyncio.sleep(1)

        logger.info("视频录制队列处理线程结束")

    async def _encode_video(self, recording_task: dict):
        """执行视频编码（在线程池中运行）"""
        if not self._loop:
            logger.error("事件循环不可用，无法编码视频")
            return

        video_path = recording_task['video_path']
        frames = recording_task['frames']
        event_id = recording_task['event_id']

        def _blocking_encode():
            """阻塞式视频编码（在线程中执行）"""
            try:
                logger.info(f"开始编码事件 {event_id} 视频: {video_path}")

                # 创建VideoWriter
                writer = cv2.VideoWriter(
                    video_path,
                    self.video_codec,
                    self.video_fps,
                    (self.video_width, self.video_height)
                )

                if not writer.isOpened():
                    logger.error(f"无法创建视频编码器: {video_path}")
                    return False

                # 写入帧数据
                frames_written = 0
                for video_frame in frames:
                    try:
                        # 确保帧尺寸正确
                        frame = video_frame.frame
                        if frame.shape[:2] != (self.video_height, self.video_width):
                            frame = cv2.resize(frame, (self.video_width, self.video_height))

                        writer.write(frame)
                        frames_written += 1
                    except Exception as e:
                        logger.warning(f"写入帧失败: {e}")
                        continue

                writer.release()

                logger.info(f"视频编码完成: {video_path}, 写入帧数: {frames_written}")
                return True

            except Exception as e:
                logger.error(f"视频编码失败: {e}")
                return False

        # 在线程池中执行阻塞操作
        success = await self._loop.run_in_executor(None, _blocking_encode)

        if not success:
            logger.error(f"事件 {event_id} 视频编码失败")

    def get_status(self) -> dict:
        """获取录制服务状态"""
        return {
            'is_running': self.is_running,
            'queue_size': self.recording_queue.qsize() if self.recording_queue else 0,
            'video_directory': str(self.video_dir),
            'video_fps': self.video_fps,
            'video_resolution': f"{self.video_width}x{self.video_height}"
        }


# 全局视频录制服务实例
video_recording_service = VideoRecordingService()