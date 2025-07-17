import cv2
import threading
import time
import asyncio
from typing import Optional, Generator, List
import numpy as np
from datetime import datetime
from collections import deque

from app.config import settings
from app.utils.logger import get_logger
from app.services.storage import storage_service
from app.services.video_recording import VideoFrame, video_recording_service

logger = get_logger(__name__)


class VideoStreamService:
    """视频流处理服务（RTMP流+事件录制缓冲区）"""
    def __init__(self):
        self.is_running = False
        self.current_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        self.capture_thread: Optional[threading.Thread] = None
        self.last_screenshot_time = 0
        self.last_cleanup_time = 0
        self.fps = settings.VIDEO_FPS
        self.rtmp_url = settings.RTMP_STREAM_URL
        # 环形缓冲区配置 - 保存前2秒的帧
        self.buffer_duration = 2.0  # 缓冲2秒
        self.buffer_size = int(self.fps * self.buffer_duration)  # 缓冲区大小
        self.frame_buffer: deque = deque(maxlen=self.buffer_size)
        self.buffer_lock = threading.Lock()
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None
        # 事件录制状态
        self.recording_events: dict = {}  # 活动的录制任务 {event_id: recording_data}
        self.recording_lock = threading.Lock() # 线程锁

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.main_loop = loop

    def start(self) -> bool:
        """启动RTMP拉流线程"""
        if self.is_running:
            logger.info("RTMP拉流线程已在运行")
            return True
        logger.info("启动RTMP拉流线程...")
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_rtmp_frames, daemon=True)
        self.capture_thread.start()
        logger.info("RTMP拉流线程启动成功")
        return True

    def stop(self):
        """停止RTMP拉流线程"""
        logger.info("停止RTMP拉流线程...")
        self.is_running = False
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=5.0)
        logger.info("RTMP拉流线程已停止")

    def _capture_rtmp_frames(self):
        """持续拉取RTMP流帧，存入current_frame"""
        import cv2
        import time
        logger.info(f"连接RTMP流: {self.rtmp_url}")
        cap = cv2.VideoCapture(self.rtmp_url)
        if not cap.isOpened():
            logger.error(f"无法打开RTMP流: {self.rtmp_url}")
            self.is_running = False
            return
        while self.is_running:
            ret, frame = cap.read()
            if ret:
                current_time = time.time()
                with self.frame_lock:
                    self.current_frame = frame.copy()
                # 写入环形缓冲区
                video_frame = VideoFrame(frame.copy(), current_time)
                with self.buffer_lock:
                    self.frame_buffer.append(video_frame)
                # 处理正在录制的事件的后续帧
                self._process_recording_events(video_frame)
                # 定期清理旧的录制任务
                if current_time - self.last_cleanup_time > 60:
                    self._cleanup_stale_recording_tasks()
                    self.last_cleanup_time = current_time
            else:
                logger.warning("RTMP流读取帧失败，尝试重连...")
                time.sleep(1)
                cap.release()
                cap = cv2.VideoCapture(self.rtmp_url)
                continue
            time.sleep(1.0 / self.fps)
        cap.release()
        logger.info("RTMP拉流线程结束")

    def get_current_frame(self) -> Optional[np.ndarray]:
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def generate_mjpeg_stream(self) -> Generator[bytes, None, None]:
        logger.info("开始生成MJPEG流...")
        while self.is_running:
            frame = self.get_current_frame()
            if frame is not None:
                try:
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                except Exception as e:
                    logger.error(f"编码视频帧错误: {e}")
            time.sleep(1.0 / self.fps)
        logger.info("MJPEG流生成结束")

    @staticmethod
    def generate_mjpeg_from_rtmp(rtmp_url: str, fps: int = 10):
        """从RTMP流生成MJPEG流（静态方法，便于API调用）"""
        import cv2
        import time
        cap = cv2.VideoCapture(rtmp_url)
        if not cap.isOpened():
            logger.error(f"无法打开RTMP流: {rtmp_url}")
            yield b''
            return
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("RTMP流读取帧失败，尝试重连...")
                    time.sleep(1)
                    continue
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                time.sleep(1.0 / fps)
        except Exception as e:
            logger.error(f"MJPEG流生成异常: {e}")
        finally:
            cap.release()

    async def take_screenshot(self, prefix: str = "auto") -> Optional[tuple[str, str]]:
        try:
            frame = self.get_current_frame()
            if frame is None:
                logger.warning("无法获取当前帧进行截图")
                return None
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if not ret:
                logger.error("编码截图失败")
                return None
            file_path, url = await storage_service.save_screenshot(buffer.tobytes(), prefix=prefix)
            logger.info(f"截图保存成功: {file_path}")
            return file_path, url
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None

    def should_take_screenshot(self) -> bool:
        """判断是否应该进行自动截图"""
        current_time = time.time()
        if current_time - self.last_screenshot_time >= settings.SCREENSHOT_INTERVAL:
            self.last_screenshot_time = current_time
            return True
        return False

    def get_video_info(self) -> dict:
        """获取视频流信息"""
        info = {
            "is_running": self.is_running,
            "rtmp_url": self.rtmp_url,
            "fps": self.fps,
            "has_rtmp_stream": self.rtmp_url is not None and self.rtmp_url != ""
        }
        return info

    def health_check(self) -> dict:
        """健康检查"""
        frame = self.get_current_frame()
        return {
            "service_running": self.is_running,
            "frame_available": frame is not None,
            "capture_thread_alive": self.capture_thread.is_alive() if self.capture_thread else False,
            "last_screenshot_time": self.last_screenshot_time,
            "frame_buffer_size": len(self.frame_buffer), # 移除环形缓冲区大小
            "active_recordings": len(self.recording_events) # 移除事件录制状态
        }

    async def start_event_recording(self, event_id: int, event_type: str) -> Optional[str]:
        """
        开始事件录制（前2秒 + 后2秒）
        返回：视频文件路径，如果录制失败则返回None
        """
        try:
            logger.info(f"开始录制事件 {event_id} 视频")
            pre_frames = self._get_pre_event_frames()
            recording_data = {
                'event_id': event_id,
                'event_type': event_type,
                'start_time': time.time(),
                'pre_frames': pre_frames,
                'post_frames': [],
                'target_post_frames': int(self.fps * 2.0),
                'status': 'collecting_frames'
            }
            with self.recording_lock:
                self.recording_events[event_id] = recording_data
            logger.info(f"事件 {event_id} 录制任务已启动，前置帧数: {len(pre_frames)}")
            return f"recording_started_{event_id}"
        except Exception as e:
            logger.error(f"启动事件录制失败: {e}")
            return None

    def _get_pre_event_frames(self) -> List[VideoFrame]:
        """获取事件前2秒的帧"""
        with self.buffer_lock:
            # 复制缓冲区中的所有帧
            return list(self.frame_buffer)

    def _process_recording_events(self, current_frame: VideoFrame):
        """处理正在录制的事件"""
        with self.recording_lock:
            to_finalize = []
            for event_id, recording_data in self.recording_events.items():
                try:
                    if recording_data.get('status') == 'collecting_frames':
                        recording_data['post_frames'].append(current_frame)
                        if len(recording_data['post_frames']) >= recording_data['target_post_frames']:
                            recording_data['status'] = 'finalizing'
                            to_finalize.append(event_id)
                except Exception as e:
                    logger.error(f"处理事件 {event_id} 录制失败: {e}")
                    recording_data['status'] = 'failed'
            # 异步触发_finalize_event_recording
            for event_id in to_finalize:
                if self.main_loop:
                    asyncio.run_coroutine_threadsafe(self._finalize_event_recording(event_id), self.main_loop)
                else:
                    logger.error(f"无法完成事件 {event_id} 录制: 缺少主事件循环")
                    self.recording_events[event_id]['status'] = 'failed'

    async def _finalize_event_recording(self, event_id: int):
        """完成事件录制，提交给视频编码服务"""
        with self.recording_lock:
            recording_data = self.recording_events.get(event_id)
        if not recording_data:
            logger.warning(f"无法找到事件 {event_id} 的录制数据以完成最终处理")
            return
        try:
            logger.info(f"完成事件 {event_id} 录制，开始视频编码")
            video_path, duration, file_size = await video_recording_service.record_event_video(
                pre_frames=recording_data['pre_frames'],
                post_frames=recording_data['post_frames'],
                event_id=event_id,
                event_type=recording_data['event_type']
            )
            with self.recording_lock:
                recording_data['video_path'] = video_path
                recording_data['duration'] = duration
                recording_data['file_size'] = file_size
                recording_data['status'] = 'completed' if video_path else 'failed'
            logger.info(f"事件 {event_id} 视频录制完成: {video_path}")
        except Exception as e:
            logger.error(f"完成事件 {event_id} 录制失败: {e}")
            with self.recording_lock:
                recording_data['status'] = 'failed'

    def _cleanup_stale_recording_tasks(self):
        """清理旧的、已完成或失败的录制任务以防内存泄漏"""
        with self.recording_lock:
            current_time = time.time()
            stale_event_ids = []
            for event_id, recording_data in self.recording_events.items():
                status = recording_data.get('status', '')
                start_time = recording_data.get('start_time', 0)
                if status in ['completed', 'failed'] and (current_time - start_time > 300):
                    stale_event_ids.append(event_id)
            if stale_event_ids:
                logger.info(f"清理 {len(stale_event_ids)} 个过期的录制任务...")
                for event_id in stale_event_ids:
                    self.recording_events.pop(event_id, None)

    def get_recording_status(self, event_id: int) -> Optional[dict]:
        """获取特定事件的录制状态"""
        with self.recording_lock:
            status = self.recording_events.get(event_id)
            return status.copy() if status else None 