import asyncio
import threading
import time
import json
import base64
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp
from io import BytesIO
import cv2
import numpy as np

from app.config import settings
from app.utils.logger import get_logger
from app.services.video_stream import VideoStreamService
from app.services.face_recognition import face_service
from app.services.zone_detection import zone_service
from app.services.storage import storage_service
# WebSocket manager will be imported when needed

logger = get_logger(__name__)


class AIAnalysisService:
    """AI分析服务 - 集成多种AI能力"""
    
    def __init__(self):
        self.is_running = False
        self.analysis_thread: Optional[threading.Thread] = None
        self.video_service: Optional[VideoStreamService] = None
        # 主事件循环，由 FastAPI 应用启动时注入
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # 行为识别相关
        self.behavior_keywords = [
            "摔倒", "睡觉", "打架", "玩手机", "喝水", "吃东西",
            "坐着", "站立", "走路", "跑步", "躺下", "打电话", "阅读"
        ]
        
        # 异常行为定义
        self.abnormal_behaviors = [
            "摔倒", "睡觉", "打架",  "喝水"
        ]
    
    def start(self):
        """启动AI分析服务"""
        if self.is_running:
            return
        
        logger.info("启动AI分析服务...")
        self.is_running = True
        self.analysis_thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self.analysis_thread.start()
        
        # 异步加载人脸和区域数据（在主循环中执行）
        if self.main_loop:
            asyncio.run_coroutine_threadsafe(self._load_ai_data(), self.main_loop)
        else:
            # 退回当前线程事件循环，但仍预期会被主循环覆盖
            asyncio.create_task(self._load_ai_data())
        
        logger.info("AI分析服务启动成功")
    
    def stop(self):
        """停止AI分析服务"""
        logger.info("停止AI分析服务...")
        self.is_running = False
        
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analysis_thread.join(timeout=10.0)
        
        logger.info("AI分析服务已停止")
    
    async def _load_ai_data(self):
        """加载AI所需的数据"""
        try:
            await face_service.load_known_faces()
            await zone_service.load_danger_zones()
            logger.info("AI数据加载完成")
        except Exception as e:
            logger.error(f"加载AI数据失败: {e}")
    
    def _analysis_loop(self):
        """AI分析主循环 (在后台线程运行)"""
        logger.info("AI分析循环开始...")

        while self.is_running:
            try:
                if self.video_service is None or self.main_loop is None:
                    time.sleep(1)
                    continue

                if self.video_service.should_take_screenshot():
                    future = asyncio.run_coroutine_threadsafe(
                        self._perform_analysis(), self.main_loop
                    )
                    # 等待分析完成，必要时可设置 timeout
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"AI分析执行错误: {e}")

                time.sleep(1)

            except Exception as e:
                logger.error(f"AI分析循环错误: {e}")
                time.sleep(5)

        logger.info("AI分析循环结束")
    
    async def _perform_analysis(self):
        """执行完整的AI分析"""
        try:
            # 获取当前帧
            frame = self.video_service.get_current_frame()
            if frame is None:
                return
            
            # 保存截图
            screenshot_result = await self.video_service.take_screenshot("analysis")
            if not screenshot_result:
                return
            
            file_path, url = screenshot_result
            
            # 并行执行多种分析
            tasks = [
                self._analyze_faces(frame, file_path),
                self._analyze_behavior(file_path),
            ]
            
            face_results, behavior_result = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理人脸识别结果
            if not isinstance(face_results, Exception) and face_results:
                await self._process_face_results(face_results, file_path)
            
            # 处理行为识别结果
            if not isinstance(behavior_result, Exception) and behavior_result:
                await self._process_behavior_result(behavior_result, file_path)
            
            # 检查危险区域违规（如果有人脸检测结果）
            if not isinstance(face_results, Exception) and face_results:
                zone_violations = zone_service.check_zone_violations(face_results)
                if zone_violations:
                    await self._process_zone_violations(zone_violations, file_path)
            
        except Exception as e:
            logger.error(f"执行AI分析失败: {e}")
    
    async def _analyze_faces(self, frame: np.ndarray, file_path: str) -> List[Dict]:
        """人脸识别分析"""
        try:
            face_results = await face_service.recognize_faces_in_frame(frame)
            
            # 构建详细的分析结果
            recognized_users = []
            strangers_count = 0
            
            for face_result in face_results:
                if face_result["is_stranger"]:
                    strangers_count += 1
                else:
                    # 提取识别到的用户信息
                    match_info = face_result.get("match", {})
                    recognized_users.append({
                        "user_id": match_info.get("user_id"),
                        "user_name": match_info.get("name"),
                        "confidence": match_info.get("confidence"),
                        "distance": match_info.get("distance"),
                        "location": face_result.get("location")
                    })
            
            # 记录详细分析日志
            detailed_result = {
                "faces_detected": len(face_results),
                "recognized_users": recognized_users,
                "strangers_count": strangers_count,
                "analysis_timestamp": file_path  # 通过文件路径可以关联截图
            }
            
            await self._log_analysis_result(
                "face_recognition",
                file_path,
                detailed_result,
                len(face_results) / 10.0  # 简单的置信度计算
            )
            
            # 通过WebSocket广播实时人脸检测数据
            await self._broadcast_face_detection(face_results)
            
            return face_results
            
        except Exception as e:
            logger.error(f"人脸识别分析失败: {e}")
            return []
    
    def _extract_json_from_markdown(self, content: str) -> Optional[str]:
        """从markdown格式的响应中提取JSON内容"""
        try:
            # 查找```json标记
            start_marker = "```json"
            end_marker = "```"
            
            start_index = content.find(start_marker)
            if start_index == -1:
                # 如果没有找到markdown标记，直接返回原内容
                return content.strip()
            
            # 找到JSON开始位置
            json_start = start_index + len(start_marker)
            
            # 找到JSON结束位置
            end_index = content.find(end_marker, json_start)
            if end_index == -1:
                # 如果没有找到结束标记，取到字符串末尾
                json_content = content[json_start:].strip()
            else:
                json_content = content[json_start:end_index].strip()
            
            return json_content
        except Exception as e:
            logger.error(f"提取JSON失败: {e}")
            return None

    async def _analyze_behavior(self, image_path: str) -> Optional[Dict]:
        """行为识别分析"""
        try:
            # 检查API配置
            if not settings.QWEN_API_KEY or settings.QWEN_API_KEY == "":
                logger.error("通义千问API密钥未配置")
                return {
                    "detected_behaviors": [],
                    "confidence": 0.1,
                    "description": "API密钥未配置",
                    "is_abnormal": False
                }
            
            # 将图片编码为base64
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            if len(image_data) == 0:
                logger.error(f"图片文件为空: {image_path}")
                return None
            
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            logger.debug(f"图片编码完成，大小: {len(image_base64)} 字符")
            
            # 强化AI prompt，明确异常行为定义
            prompt = f"""
            请分析这张图片中人物的行为状态。

            重要：以下行为必须被识别为异常行为：{', '.join(self.abnormal_behaviors)}
            
            请从以下所有行为中识别人物的具体行为：
            {', '.join(self.behavior_keywords)}
            
            请严格按照以下JSON格式返回，不要添加任何其他内容：
            {{
                "detected_behaviors": ["行为1", "行为2"],
                "confidence": 0.95,
                "description": "详细描述人物行为",
                "is_abnormal": true
            }}
            
            判定规则：
            1. 如果检测到的行为包含以下任何一种，必须设置is_abnormal为true：{', '.join(self.abnormal_behaviors)}
            2. 其他行为设置is_abnormal为false
            3. confidence表示识别的置信度，范围0-1
            4. 只返回JSON，不要添加解释文字
            """
            
            payload = {
                "model": "qwen-vl-max",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.1
            }
            
            headers = {
                "Authorization": f"Bearer {settings.QWEN_API_KEY}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"发送通义千问API请求到: {settings.QWEN_API_BASE}/chat/completions")
            
            # 发送API请求，增加重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{settings.QWEN_API_BASE}/chat/completions",
                            json=payload,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=60)
                        ) as response:
                            logger.info(f"API响应状态码: {response.status}")
                            
                            if response.status == 200:
                                result = await response.json()
                                logger.debug(f"API响应结构: {result.keys()}")
                                
                                if "choices" in result and len(result["choices"]) > 0:
                                    content = result["choices"][0]["message"]["content"]
                                    logger.info(f"API返回内容: {content[:200]}...")
                                    
                                    # 从markdown格式中提取JSON
                                    json_content = self._extract_json_from_markdown(content)
                                    if json_content is None:
                                        logger.error("无法从响应中提取JSON内容")
                                        return None
                                    
                                    logger.info(f"提取的JSON内容: {json_content[:200]}...")
                                    
                                    # 尝试解析JSON响应
                                    try:
                                        behavior_data = json.loads(json_content)
                                        logger.info(f"成功解析JSON: {behavior_data}")
                                        
                                        # 记录分析日志
                                        await self._log_analysis_result(
                                            "behavior_analysis",
                                            image_path,
                                            behavior_data,
                                            behavior_data.get("confidence", 0.5)
                                        )
                                        
                                        return behavior_data
                                    except json.JSONDecodeError as je:
                                        logger.warning(f"JSON解析失败: {je}, 提取内容: {json_content}")
                                        # 如果不是JSON格式，创建简单的结构
                                        fallback_data = {
                                            "detected_behaviors": [],
                                            "confidence": 0.3,
                                            "description": content,
                                            "is_abnormal": any(ab in content for ab in self.abnormal_behaviors)
                                        }
                                        logger.info(f"使用回退数据: {fallback_data}")
                                        return fallback_data
                                else:
                                    logger.error(f"API响应格式异常: {result}")
                                    return None
                            else:
                                error_text = await response.text()
                                logger.error(f"API请求失败 - 状态码: {response.status}, 响应: {error_text}")
                                
                                if attempt < max_retries - 1:
                                    wait_time = 2 ** attempt
                                    logger.info(f"第{attempt + 1}次尝试失败，{wait_time}秒后重试...")
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    return {
                                        "detected_behaviors": [],
                                        "confidence": 0.2,
                                        "description": f"API调用失败: {response.status}",
                                        "is_abnormal": False
                                    }
                            
                except aiohttp.ClientError as ce:
                    logger.error(f"网络连接错误 (尝试 {attempt + 1}/{max_retries}): {ce}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.info(f"网络错误，{wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return {
                            "detected_behaviors": [],
                            "confidence": 0.1,
                            "description": f"网络连接失败: {str(ce)}",
                            "is_abnormal": False
                        }
                except asyncio.TimeoutError:
                    logger.error(f"API调用超时 (尝试 {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.info(f"超时错误，{wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return {
                            "detected_behaviors": [],
                            "confidence": 0.1,
                            "description": "API调用超时",
                            "is_abnormal": False
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"行为识别过程中发生未预期错误: {e}", exc_info=True)
            return {
                "detected_behaviors": [],
                "confidence": 0.1,
                "description": f"分析过程中发生错误: {str(e)}",
                "is_abnormal": False
            }
    
    async def _process_face_results(self, face_results: List[Dict], file_path: str):
        """处理人脸识别结果"""
        try:
            strangers = [face for face in face_results if face["is_stranger"]]
            
            if strangers:
                for stranger in strangers:
                    await self._create_event(
                        event_type="stranger",
                        title="检测到陌生人",
                        description=f"在监控区域检测到未注册的陌生人",
                        screenshot_path=file_path,
                        confidence=0.8,
                        location=stranger["location"],
                        severity="high"
                    )
            
        except Exception as e:
            logger.error(f"处理人脸识别结果失败: {e}")
    
    async def _process_behavior_result(self, behavior_result: Dict, file_path: str):
        """处理行为识别结果"""
        try:
            # 记录所有行为分析结果用于调试
            detected_behaviors = behavior_result.get("detected_behaviors", [])
            is_abnormal_flag = behavior_result.get("is_abnormal", False)
            description = behavior_result.get("description", "")
            confidence = behavior_result.get("confidence", 0.5)
            
            logger.info(f"行为分析结果: 检测到行为={detected_behaviors}, AI判定异常={is_abnormal_flag}, 置信度={confidence}")
            
            # 强化验证：检查实际行为类型
            contains_abnormal_behavior = any(
                behavior in self.abnormal_behaviors 
                for behavior in detected_behaviors
            )
            
            # 三重验证机制：
            # 1. 检查检测到的行为是否在异常行为列表中（主要依据）
            # 2. AI判定标志作为辅助参考
            # 3. 如果行为包含异常行为，强制创建事件（确保不遗漏）
            
            if contains_abnormal_behavior:
                abnormal_behaviors_found = [
                    behavior for behavior in detected_behaviors 
                    if behavior in self.abnormal_behaviors
                ]
                
                # 即使AI判定错误，只要检测到异常行为就创建事件
                await self._create_event(
                    event_type="abnormal_behavior",
                    title="检测到异常行为",
                    description=f"识别到异常行为: {', '.join(abnormal_behaviors_found)}. {description}",
                    screenshot_path=file_path,
                    confidence=confidence,
                    metadata=behavior_result,
                    severity="high" if confidence > 0.8 else ("medium" if confidence > 0.6 else "low")
                )
                
                logger.warning(f"创建异常行为事件: {abnormal_behaviors_found} (AI判定={is_abnormal_flag}, 本地强制识别)")
            else:
                # 记录正常行为但不创建告警事件
                logger.info(f"检测到正常行为: {detected_behaviors}, 无需创建告警事件")
            
        except Exception as e:
            logger.error(f"处理行为识别结果失败: {e}")
    
    async def _process_zone_violations(self, violations: List[Dict], file_path: str):
        """处理危险区域违规"""
        try:
            for violation in violations:
                event_type = "zone_violation"
                title = f"危险区域告警 - {violation['zone_name']}"
                
                if violation["type"] == "zone_entry":
                    description = f"人员进入危险区域: {violation['zone_name']}"
                    severity = "medium"
                elif violation["type"] == "zone_stay_timeout":
                    description = f"人员在危险区域停留超时: {violation['zone_name']}, 停留时间: {violation.get('stay_duration', 0):.1f}秒"
                    severity = "high"
                else:
                    continue
                
                await self._create_event(
                    event_type=event_type,
                    title=title,
                    description=description,
                    screenshot_path=file_path,
                    confidence=0.9,
                    location=violation["location"],
                    metadata=violation,
                    severity=severity
                )
            
        except Exception as e:
            logger.error(f"处理危险区域违规失败: {e}")
    
    async def _create_event(self, **event_data):
        """创建事件记录"""
        try:
            from app.services.database import AsyncSessionLocal
            from app.models.database import Event
            
            # 首先创建事件记录
            async with AsyncSessionLocal() as session:
                event = Event(**event_data)
                session.add(event)
                await session.commit()
                await session.refresh(event)
                
                logger.info(f"创建事件: {event.title} (ID: {event.id})")
                
                # 启动视频录制
                if self.video_service:
                    video_result = await self.video_service.start_event_recording(
                        event_id=event.id,
                        event_type=event.event_type
                    )
                    
                    if video_result:
                        logger.info(f"事件 {event.id} 视频录制已启动")
                        
                        # 等待视频录制完成并更新事件记录
                        asyncio.create_task(self._update_event_with_video(event.id))
                    else:
                        logger.warning(f"事件 {event.id} 视频录制启动失败")
                
                # 通过WebSocket推送实时告警
                await self._send_realtime_alert(event)
                
        except Exception as e:
            logger.error(f"创建事件失败: {e}")
    
    async def _update_event_with_video(self, event_id: int):
        """等待视频录制完成并更新事件记录"""
        try:
            # 等待视频录制完成（最多等待60秒）
            max_wait_time = 60
            wait_interval = 2
            waited_time = 0
            
            while waited_time < max_wait_time:
                if self.video_service:
                    recording_status = self.video_service.get_recording_status(event_id)
                    
                    if recording_status and 'video_path' in recording_status:
                        # 视频录制完成，更新事件记录
                        await self._update_event_video_info(
                            event_id, 
                            recording_status['video_path'],
                            recording_status.get('duration'),
                            recording_status.get('file_size')
                        )
                        logger.info(f"事件 {event_id} 视频信息已更新")
                        return
                
                await asyncio.sleep(wait_interval)
                waited_time += wait_interval
            
            logger.warning(f"事件 {event_id} 视频录制超时")
            
        except Exception as e:
            logger.error(f"更新事件视频信息失败: {e}")
    
    async def _update_event_video_info(self, event_id: int, video_path: str, duration: float, file_size: int):
        """更新事件的视频信息"""
        try:
            from app.services.database import AsyncSessionLocal
            from app.models.database import Event
            from sqlalchemy import select
            
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Event).where(Event.id == event_id)
                )
                event = result.scalar_one_or_none()
                
                if event:
                    event.video_clip_path = video_path
                    event.video_duration = duration
                    event.video_size = file_size
                    
                    await session.commit()
                    logger.info(f"事件 {event_id} 视频信息更新成功: {video_path}")
                else:
                    logger.error(f"未找到事件 {event_id}")
                    
        except Exception as e:
            logger.error(f"更新事件 {event_id} 视频信息失败: {e}")
    
    async def _send_realtime_alert(self, event):
        """发送实时告警"""
        try:
            from app.services.storage import storage_service
            
            alert_data = {
                "id": event.id,
                "type": event.event_type,
                "title": event.title,
                "description": event.description,
                "screenshot_url": storage_service.get_file_url(event.screenshot_path) if event.screenshot_path else None,
                "confidence": event.confidence,
                "severity": event.severity,
                "created_at": event.created_at.isoformat(),
                "location": event.location,
                "event_data": event.event_data
            }
            
            # 通过WebSocket推送
            message = {
                "type": "event_alert",
                "data": alert_data,
                "timestamp": datetime.now().isoformat()
            }
            
            # 导入并使用WebSocket管理器
            try:
                from app.services.websocket import websocket_manager
                await websocket_manager.send_event_alert(alert_data)
            except Exception as ws_error:
                logger.warning(f"WebSocket推送失败: {ws_error}")
            
            logger.info(f"发送实时告警: {event.title}")
            
        except Exception as e:
            logger.error(f"发送实时告警失败: {e}")
    
    async def _log_analysis_result(self, analysis_type: str, image_path: str, result: dict, confidence: float):
        """记录分析结果到数据库"""
        try:
            from app.services.database import AsyncSessionLocal
            from app.models.database import AnalysisLog
            
            async with AsyncSessionLocal() as session:
                log_entry = AnalysisLog(
                    analysis_type=analysis_type,
                    screenshot_path=image_path,
                    result=result,
                    confidence=confidence,
                    processing_time=0.0  # TODO: 实际计算处理时间
                )
                session.add(log_entry)
                await session.commit()
                
        except Exception as e:
            logger.error(f"记录分析日志失败: {e}")
    
    async def _broadcast_face_detection(self, face_results: List[Dict]):
        """通过WebSocket广播实时人脸检测数据"""
        try:
            from app.services.websocket import websocket_manager
            
            # 构建完整的人脸检测数据（包含已识别和陌生人）
            face_detection_data = {
                "faces": face_results,
                "total_faces": len(face_results),
                "recognized_users": [face for face in face_results if not face["is_stranger"]],
                "strangers_count": len([face for face in face_results if face["is_stranger"]]),
                "timestamp": datetime.now().isoformat()
            }
            
            message = {
                "type": "face_detection",
                "data": face_detection_data,
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket_manager.broadcast(message)
            logger.debug(f"广播人脸检测数据: {len(face_results)} 张人脸")
            
        except Exception as e:
            logger.error(f"广播人脸检测数据失败: {e}")
    
    def set_video_service(self, video_service: VideoStreamService):
        """设置视频流服务引用"""
        self.video_service = video_service
    
    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """由应用在启动时注入主事件循环"""
        self.main_loop = loop
    
    def get_statistics(self) -> Dict:
        """获取AI分析统计信息"""
        return {
            "is_running": self.is_running,
            "known_faces_count": face_service.get_known_faces_count(),
            "zone_statistics": zone_service.get_zone_statistics(),
            "analysis_thread_alive": self.analysis_thread.is_alive() if self.analysis_thread else False
        }


# 全局AI分析服务实例
ai_service = AIAnalysisService() 