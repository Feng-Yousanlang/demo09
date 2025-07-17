import cv2
import numpy as np
import time
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from shapely.geometry import Point, Polygon
from collections import defaultdict

from app.config import settings
from app.utils.logger import get_logger
from app.services.database import AsyncSessionLocal
from app.models.database import DangerZone
from sqlalchemy import select

logger = get_logger(__name__)


class ZoneDetectionService:
    """危险区域检测服务"""
    
    def __init__(self):
        self.danger_zones: Dict[int, Dict] = {}  # 缓存危险区域数据
        self.person_positions: Dict[str, Dict] = {}  # 追踪人员位置历史
        self.zone_violations: Dict[str, Dict] = {}  # 当前区域违规状态
        
    async def load_danger_zones(self):
        """从数据库加载危险区域配置"""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(DangerZone).where(DangerZone.is_active == True)
                )
                zones = result.scalars().all()
                
                self.danger_zones.clear()
                for zone in zones:
                    try:
                        # 创建Shapely多边形对象
                        coordinates = [(point["x"], point["y"]) for point in zone.coordinates]
                        polygon = Polygon(coordinates)
                        
                        self.danger_zones[zone.id] = {
                            "name": zone.name,
                            "zone_type": zone.zone_type,
                            "coordinates": zone.coordinates,
                            "polygon": polygon,
                            "stay_threshold": zone.stay_threshold,
                            "created_at": zone.created_at
                        }
                    except Exception as e:
                        logger.error(f"加载危险区域 {zone.name} 失败: {e}")
                
                logger.info(f"已加载 {len(self.danger_zones)} 个危险区域")
                
        except Exception as e:
            logger.error(f"加载危险区域失败: {e}")
    
    def _get_person_id(self, face_result: Dict) -> str:
        """根据人脸识别结果生成人员ID"""
        if face_result["is_stranger"]:
            # 对陌生人使用位置作为临时ID
            location = face_result["location"]
            return f"stranger_{location['left']}_{location['top']}"
        else:
            # 对已知人员使用用户ID
            return f"user_{face_result['match']['user_id']}"
    
    def _get_person_center(self, face_result: Dict) -> Tuple[float, float]:
        """获取人员中心点坐标"""
        location = face_result["location"]
        center_x = (location["left"] + location["right"]) // 2
        center_y = (location["top"] + location["bottom"]) // 2
        return center_x, center_y
    
    def check_zone_violations(self, face_results: List[Dict]) -> List[Dict]:
        """检查危险区域违规情况"""
        violations = []
        current_time = time.time()
        
        try:
            # 更新人员位置
            current_persons = set()
            for face_result in face_results:
                person_id = self._get_person_id(face_result)
                current_persons.add(person_id)
                
                center_x, center_y = self._get_person_center(face_result)
                person_point = Point(center_x, center_y)
                
                # 更新位置历史
                if person_id not in self.person_positions:
                    self.person_positions[person_id] = {
                        "positions": [],
                        "first_seen": current_time
                    }
                
                self.person_positions[person_id]["positions"].append({
                    "point": person_point,
                    "timestamp": current_time,
                    "face_data": face_result
                })
                
                # 限制历史记录长度
                max_history = 50
                if len(self.person_positions[person_id]["positions"]) > max_history:
                    self.person_positions[person_id]["positions"] = \
                        self.person_positions[person_id]["positions"][-max_history:]
                
                # 检查每个危险区域
                for zone_id, zone_data in self.danger_zones.items():
                    violation_key = f"{person_id}_{zone_id}"
                    
                    # 检查是否在危险区域内
                    is_in_zone = zone_data["polygon"].contains(person_point)
                    
                    if is_in_zone:
                        # 进入危险区域
                        if violation_key not in self.zone_violations:
                            self.zone_violations[violation_key] = {
                                "person_id": person_id,
                                "zone_id": zone_id,
                                "zone_name": zone_data["name"],
                                "enter_time": current_time,
                                "face_data": face_result,
                                "notified": False
                            }
                            
                            # 立即触发进入告警
                            violations.append({
                                "type": "zone_entry",
                                "person_id": person_id,
                                "zone_id": zone_id,
                                "zone_name": zone_data["name"],
                                "message": f"检测到人员进入危险区域: {zone_data['name']}",
                                "face_data": face_result,
                                "location": {"x": center_x, "y": center_y},
                                "timestamp": current_time
                            })
                        
                        # 检查停留时间
                        violation_info = self.zone_violations[violation_key]
                        stay_duration = current_time - violation_info["enter_time"]
                        
                        if (stay_duration >= zone_data["stay_threshold"] and 
                            not violation_info["notified"]):
                            
                            violations.append({
                                "type": "zone_stay_timeout",
                                "person_id": person_id,
                                "zone_id": zone_id,
                                "zone_name": zone_data["name"],
                                "message": f"人员在危险区域停留超时: {zone_data['name']} ({stay_duration:.1f}秒)",
                                "face_data": face_result,
                                "location": {"x": center_x, "y": center_y},
                                "stay_duration": stay_duration,
                                "timestamp": current_time
                            })
                            
                            # 标记已通知
                            violation_info["notified"] = True
                    
                    else:
                        # 离开危险区域
                        if violation_key in self.zone_violations:
                            stay_duration = current_time - self.zone_violations[violation_key]["enter_time"]
                            logger.info(f"人员离开危险区域: {zone_data['name']}, 停留时间: {stay_duration:.1f}秒")
                            del self.zone_violations[violation_key]
            
            # 清理不再存在的人员
            self._cleanup_old_persons(current_persons, current_time)
            
        except Exception as e:
            logger.error(f"检查危险区域违规失败: {e}")
        
        return violations
    
    def _cleanup_old_persons(self, current_persons: set, current_time: float):
        """清理长时间未出现的人员记录"""
        timeout = 30  # 30秒未出现则清理
        
        # 清理位置历史
        persons_to_remove = []
        for person_id in self.person_positions:
            if person_id not in current_persons:
                last_seen = max(pos["timestamp"] for pos in self.person_positions[person_id]["positions"])
                if current_time - last_seen > timeout:
                    persons_to_remove.append(person_id)
        
        for person_id in persons_to_remove:
            del self.person_positions[person_id]
            logger.debug(f"清理过期人员记录: {person_id}")
        
        # 清理违规记录
        violations_to_remove = []
        for violation_key in self.zone_violations:
            person_id = self.zone_violations[violation_key]["person_id"]
            if person_id not in current_persons:
                if current_time - self.zone_violations[violation_key]["enter_time"] > timeout:
                    violations_to_remove.append(violation_key)
        
        for violation_key in violations_to_remove:
            del self.zone_violations[violation_key]
    
    def draw_danger_zones(self, frame: np.ndarray) -> np.ndarray:
        """在图像上绘制危险区域"""
        try:
            result_frame = frame.copy()
            
            for zone_id, zone_data in self.danger_zones.items():
                coordinates = zone_data["coordinates"]
                
                # 转换坐标格式
                points = np.array([[int(p["x"]), int(p["y"])] for p in coordinates], np.int32)
                points = points.reshape((-1, 1, 2))
                
                # 绘制半透明区域
                overlay = result_frame.copy()
                cv2.fillPoly(overlay, [points], (0, 0, 255, 128))  # 红色半透明
                cv2.addWeighted(result_frame, 0.7, overlay, 0.3, 0, result_frame)
                
                # 绘制边界线
                cv2.polylines(result_frame, [points], True, (0, 0, 255), 2)
                
                # 绘制区域名称
                if coordinates:
                    center_x = int(sum(p["x"] for p in coordinates) / len(coordinates))
                    center_y = int(sum(p["y"] for p in coordinates) / len(coordinates))
                    
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    text = zone_data["name"]
                    text_size = cv2.getTextSize(text, font, 0.7, 2)[0]
                    
                    # 绘制文字背景
                    cv2.rectangle(result_frame, 
                                (center_x - text_size[0]//2 - 5, center_y - text_size[1] - 5),
                                (center_x + text_size[0]//2 + 5, center_y + 5),
                                (0, 0, 255), -1)
                    
                    # 绘制文字
                    cv2.putText(result_frame, text, 
                              (center_x - text_size[0]//2, center_y),
                              font, 0.7, (255, 255, 255), 2)
            
            return result_frame
            
        except Exception as e:
            logger.error(f"绘制危险区域失败: {e}")
            return frame
    
    def get_zone_statistics(self) -> Dict:
        """获取区域统计信息"""
        return {
            "total_zones": len(self.danger_zones),
            "active_violations": len(self.zone_violations),
            "tracked_persons": len(self.person_positions),
            "zones_info": [
                {
                    "id": zone_id,
                    "name": zone_data["name"],
                    "stay_threshold": zone_data["stay_threshold"]
                }
                for zone_id, zone_data in self.danger_zones.items()
            ]
        }


# 全局区域检测服务实例
zone_service = ZoneDetectionService() 