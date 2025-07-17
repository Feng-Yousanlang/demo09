import asyncio
import json
from typing import List, Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_info: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, client_info: Dict = None):
        """建立WebSocket连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # 记录连接信息
        self.connection_info[websocket] = {
            "connected_at": datetime.now(),
            "client_info": client_info or {},
            "last_heartbeat": datetime.now()
        }
        
        logger.info(f"WebSocket连接建立，当前连接数: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
        if websocket in self.connection_info:
            del self.connection_info[websocket]
        
        logger.info(f"WebSocket连接断开，当前连接数: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.error(f"发送个人消息失败: {e}")
            await self.disconnect(websocket)
    
    async def broadcast(self, message: Dict):
        """广播消息给所有连接的客户端"""
        if not self.active_connections:
            return
        
        # 准备消息
        message_text = json.dumps(message, ensure_ascii=False, default=str)
        
        # 记录要移除的失效连接
        disconnected_connections = []
        
        # 向所有连接发送消息
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message_text)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                disconnected_connections.append(connection)
        
        # 移除失效连接
        for connection in disconnected_connections:
            await self.disconnect(connection)
        
        logger.debug(f"广播消息给 {len(self.active_connections)} 个客户端")
    
    async def send_event_alert(self, event_data: Dict):
        """发送事件告警"""
        message = {
            "type": "event_alert",
            "data": event_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
        logger.info(f"发送事件告警: {event_data.get('title', 'Unknown')}")
    
    async def send_system_status(self, status_data: Dict):
        """发送系统状态"""
        message = {
            "type": "system_status",
            "data": status_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def send_video_recording_status(self, event_id: int, status: str, progress: Dict = None):
        """发送视频录制状态"""
        message = {
            "type": "video_recording_status",
            "data": {
                "event_id": event_id,
                "status": status,  # started, encoding, completed, failed
                "progress": progress or {},
                "timestamp": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
        logger.info(f"发送视频录制状态: 事件 {event_id} - {status}")
    
    async def send_video_encoding_progress(self, event_id: int, progress_percent: float, 
                                         frames_processed: int = 0, total_frames: int = 0):
        """发送视频编码进度"""
        message = {
            "type": "video_encoding_progress",
            "data": {
                "event_id": event_id,
                "progress_percent": progress_percent,
                "frames_processed": frames_processed,
                "total_frames": total_frames,
                "estimated_time_remaining": max(0, (100 - progress_percent) * 0.1)  # 简单估算
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
        logger.debug(f"发送视频编码进度: 事件 {event_id} - {progress_percent:.1f}%")
    
    async def send_video_cleanup_status(self, cleanup_result: Dict):
        """发送视频清理状态"""
        message = {
            "type": "video_cleanup_status",
            "data": {
                "cleaned_files": cleanup_result.get("cleaned_by_time", 0) + cleanup_result.get("cleaned_by_disk", 0),
                "cleaned_by_time": cleanup_result.get("cleaned_by_time", 0),
                "cleaned_by_disk": cleanup_result.get("cleaned_by_disk", 0),
                "cleaned_orphaned": cleanup_result.get("cleaned_orphaned", 0),
                "disk_usage_percent": cleanup_result.get("disk_usage_percent", 0),
                "remaining_videos": cleanup_result.get("remaining_videos", 0),
                "remaining_size_mb": cleanup_result.get("remaining_size_mb", 0),
                "cleanup_type": cleanup_result.get("cleanup_type", "automatic")
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
        logger.info(f"发送视频清理状态: 清理了 {cleanup_result.get('cleaned_by_time', 0)} 个文件")
    
    async def send_video_buffer_status(self, buffer_info: Dict):
        """发送视频缓冲区状态"""
        message = {
            "type": "video_buffer_status",
            "data": {
                "buffer_size": buffer_info.get("buffer_size", 0),
                "buffer_capacity": buffer_info.get("buffer_capacity", 0),
                "buffer_duration": buffer_info.get("buffer_duration", 0),
                "active_recordings": buffer_info.get("active_recordings", 0),
                "memory_usage_mb": buffer_info.get("memory_usage_mb", 0)
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def send_video_storage_stats(self, storage_stats: Dict):
        """发送视频存储统计"""
        message = {
            "type": "video_storage_stats",
            "data": {
                "total_files": storage_stats.get("total_files", 0),
                "total_size_bytes": storage_stats.get("total_size_bytes", 0),
                "total_size_mb": storage_stats.get("total_size_mb", 0),
                "disk_usage_percent": storage_stats.get("disk_usage_percent", 0),
                "storage_path": storage_stats.get("storage_path", ""),
                "average_file_size_mb": storage_stats.get("average_file_size_mb", 0)
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def send_heartbeat(self):
        """发送心跳消息"""
        message = {
            "type": "heartbeat",
            "data": {"server_time": datetime.now().isoformat()},
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)
    
    async def handle_client_message(self, websocket: WebSocket, message: str):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            message_type = data.get("type", "")
            
            if message_type == "heartbeat":
                # 更新心跳时间
                if websocket in self.connection_info:
                    self.connection_info[websocket]["last_heartbeat"] = datetime.now()
                
                # 发送心跳响应
                response = {
                    "type": "heartbeat_response",
                    "data": {"server_time": datetime.now().isoformat()},
                    "timestamp": datetime.now().isoformat()
                }
                await self.send_personal_message(response, websocket)
            
            elif message_type == "subscribe":
                # 处理订阅请求
                await self._handle_subscription(websocket, data.get("data", {}))
            
            elif message_type == "unsubscribe":
                # 处理取消订阅请求
                await self._handle_unsubscription(websocket, data.get("data", {}))
            
            else:
                logger.warning(f"未知的消息类型: {message_type}")
        
        except json.JSONDecodeError:
            logger.error(f"无法解析客户端消息: {message}")
        except Exception as e:
            logger.error(f"处理客户端消息失败: {e}")
    
    async def _handle_subscription(self, websocket: WebSocket, data: Dict):
        """处理订阅请求"""
        # 可以根据需要实现不同类型的订阅
        # 例如：只订阅特定类型的事件、特定严重级别的告警等
        pass
    
    async def _handle_unsubscription(self, websocket: WebSocket, data: Dict):
        """处理取消订阅请求"""
        pass
    
    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self.active_connections)
    
    def get_connection_info(self) -> List[Dict]:
        """获取连接信息"""
        info_list = []
        for websocket, info in self.connection_info.items():
            info_list.append({
                "connected_at": info["connected_at"].isoformat(),
                "last_heartbeat": info["last_heartbeat"].isoformat(),
                "client_info": info["client_info"]
            })
        return info_list
    
    async def cleanup_stale_connections(self, timeout_seconds: int = 300):
        """清理过期连接"""
        current_time = datetime.now()
        stale_connections = []
        
        for websocket, info in self.connection_info.items():
            time_diff = (current_time - info["last_heartbeat"]).total_seconds()
            if time_diff > timeout_seconds:
                stale_connections.append(websocket)
        
        for websocket in stale_connections:
            logger.info("清理过期WebSocket连接")
            await self.disconnect(websocket)
    
    async def start_heartbeat_task(self, interval_seconds: int = 30):
        """启动心跳任务"""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await self.send_heartbeat()
                await self.cleanup_stale_connections()
            except Exception as e:
                logger.error(f"心跳任务错误: {e}")


# 全局WebSocket管理器实例
websocket_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点处理函数"""
    await websocket_manager.connect(websocket)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            await websocket_manager.handle_client_message(websocket, data)
    
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket处理错误: {e}")
        await websocket_manager.disconnect(websocket) 