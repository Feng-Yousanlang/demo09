import cv2
import numpy as np
import json
import asyncio
from typing import List, Dict, Optional, Tuple
from deepface import DeepFace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import settings
from app.utils.logger import get_logger
from app.services.database import AsyncSessionLocal
from app.models.database import User
from sqlalchemy import select, delete

logger = get_logger(__name__)


def convert_numpy_types(obj):
    """将NumPy类型转换为Python原生类型，用于JSON序列化"""
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(v) for v in obj]
    return obj


class FaceRecognitionService:
    """
    人脸识别服务
    使用DeepFace库，并可配置不同的检测器和模型。
    """
    
    def __init__(self, detector_backend='opencv', model_name='VGG-Face'):
        self.detector_backend = detector_backend
        self.model_name = model_name
        self.known_faces_db_path = str(settings.FACE_IMAGES_PATH)
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.known_faces = {}
        
        # 确保人脸数据库目录存在
        Path(self.known_faces_db_path).mkdir(exist_ok=True)
        
        logger.info(f"人脸识别服务初始化，检测器: {self.detector_backend}, 模型: {self.model_name}")

    async def load_known_faces(self):
        """加载已知人脸数据（兼容性方法）"""
        try:
            # 检查人脸数据库目录中的图片数量
            face_files = list(Path(self.known_faces_db_path).glob("*.jpg")) + \
                        list(Path(self.known_faces_db_path).glob("*.png"))
            
            logger.info(f"人脸数据库中找到 {len(face_files)} 个人脸文件")
            return len(face_files)
        except Exception as e:
            logger.error(f"加载人脸数据失败: {e}")
            return 0

    def get_known_faces_count(self) -> int:
        """获取已知人脸数量"""
        try:
            # 检查人脸数据库目录中的图片数量
            face_files = list(Path(self.known_faces_db_path).glob("*.jpg")) + \
                        list(Path(self.known_faces_db_path).glob("*.png"))
            
            return len(face_files)
        except Exception as e:
            logger.error(f"获取已知人脸数量失败: {e}")
            return 0

    def _has_face_data(self) -> bool:
        """检查是否有有效的人脸数据（符合user_ID.jpg格式）"""
        try:
            face_files = list(Path(self.known_faces_db_path).glob("*.jpg")) + \
                        list(Path(self.known_faces_db_path).glob("*.png"))
            
            # 只计算符合user_ID格式的文件
            valid_files = []
            for file_path in face_files:
                stem = file_path.stem
                if stem.startswith('user_'):
                    try:
                        user_id = int(stem.split('_')[1])
                        valid_files.append(file_path)
                    except (IndexError, ValueError):
                        logger.warning(f"跳过不符合命名规范的文件: {file_path}")
                        continue
                else:
                    logger.warning(f"跳过不符合命名规范的文件: {file_path}")
            
            logger.info(f"人脸数据库状态: 总文件{len(face_files)}个, 有效文件{len(valid_files)}个")
            return len(valid_files) > 0
        except Exception as e:
            logger.error(f"检查人脸数据失败: {e}")
            return False

    def _extract_face_encoding(self, image_path: str) -> Optional[np.ndarray]:
        """
        从单个图像中提取人脸特征编码（同步方法）。
        使用DeepFace.represent。
        """
        try:
            embedding_objs = DeepFace.represent(
                img_path=image_path,
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                enforce_detection=True
            )
            
            if embedding_objs and 'embedding' in embedding_objs[0]:
                return np.array(embedding_objs[0]['embedding'])
            else:
                logger.warning(f"在图片中未提取到有效的人脸特征: {image_path}")
                return None
                
        except Exception as e:
            logger.error(f"提取人脸特征失败 for {image_path}: {e}")
            return None

    async def extract_face_encoding(self, image_path: str) -> Optional[np.ndarray]:
        """异步提取人脸特征编码"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._extract_face_encoding,
            image_path
        )

    def _recognize_faces_in_frame(self, frame: np.ndarray) -> List[Dict]:
        """
        在视频帧中识别已知人脸（同步方法）。
        使用DeepFace.find进行识别。
        """
        try:
            # 如果人脸数据库为空，只进行陌生人检测
            if not self._has_face_data():
                return self._detect_strangers_only(frame)
            
            # DeepFace.find 在数据库中查找匹配项
            # df_path必须指向包含人脸图片的目录
            dfs = DeepFace.find(
                img_path=frame,
                db_path=self.known_faces_db_path,
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                enforce_detection=False, # 不强制检测，以便处理空帧
                silent=True
            )

            logger.info(f"DeepFace.find 返回 {len(dfs)} 个DataFrame")
            
            results = []
            if isinstance(dfs, list) and len(dfs) > 0:
                for i, df in enumerate(dfs):
                    if not df.empty:
                        logger.info(f"DataFrame {i} 结构调试:")
                        logger.info(f"  列名: {df.columns.tolist()}")
                        logger.info(f"  数据形状: {df.shape}")
                        logger.info(f"  前几行数据:")
                        for idx, row in df.head(3).iterrows():
                            logger.info(f"    索引{idx}: {dict(row)}")
                        
                        # 确定距离列名
                        distance_column = f"{self.model_name}_cosine"
                        if distance_column not in df.columns:
                            if 'distance' in df.columns:
                                distance_column = 'distance'
                            else:
                                distance_cols = [col for col in df.columns if 'distance' in col.lower() or 'cosine' in col.lower()]
                                if distance_cols:
                                    distance_column = distance_cols[0]
                                else:
                                    logger.warning(f"未找到距离列，跳过此DataFrame")
                                    continue
                        
                        logger.info(f"使用距离列: {distance_column}")
                        
                        # 首先过滤出符合命名规范的文件
                        valid_matches = []
                        for idx, row in df.iterrows():
                            identity_path = Path(row['identity'])
                            distance = row[distance_column]
                            
                            # 检查文件名格式
                            if identity_path.stem.startswith('user_'):
                                try:
                                    user_id = int(identity_path.stem.split('_')[1])
                                    valid_matches.append({
                                        'row': row,
                                        'identity_path': identity_path,
                                        'user_id': user_id,
                                        'distance': distance
                                    })
                                    logger.info(f"有效匹配: {identity_path.name}, 用户ID: {user_id}, 距离: {distance:.3f}")
                                except (IndexError, ValueError):
                                    logger.warning(f"无法从路径解析用户ID: {identity_path}")
                                    continue
                            else:
                                logger.info(f"跳过不符合命名规范的文件: {identity_path.name}")
                        
                        if not valid_matches:
                            logger.info("没有找到符合命名规范的有效匹配")
                            continue
                        
                        # 从有效匹配中选择距离最小的
                        best_match_info = min(valid_matches, key=lambda x: x['distance'])
                        best_distance = best_match_info['distance']
                        best_user_id = best_match_info['user_id']
                        best_identity_path = best_match_info['identity_path']
                        best_row = best_match_info['row']
                        
                        logger.info(f"最佳有效匹配: {best_identity_path.name}, 用户ID: {best_user_id}, 距离: {best_distance:.3f}")
                        
                        # 使用配置的阈值进行判断（cosine距离，值越小越相似）
                        if best_distance <= settings.FACE_RECOGNITION_THRESHOLD:
                            logger.info(f"距离 {best_distance:.3f} 在阈值 {settings.FACE_RECOGNITION_THRESHOLD} 内，接受匹配")
                            
                            location = best_row['source_w'], best_row['source_h'], best_row['source_x'], best_row['source_y']
                            
                            # 对于cosine距离，confidence = 1 - distance
                            confidence = 1 - float(best_distance) if best_distance is not None else 0.5
                            
                            result = {
                                "location": {"top": location[3], "right": location[0] + location[2], "bottom": location[1] + location[3], "left": location[2]},
                                "match": {
                                    "user_id": best_user_id,
                                    "name": best_identity_path.stem,
                                    "confidence": confidence,
                                    "distance": float(best_distance) if best_distance is not None else 0.5
                                },
                                "is_stranger": False
                            }
                            results.append(result)
                            logger.info(f"✅ 成功识别用户: 用户{best_user_id}, 置信度{confidence:.3f}")
                        else:
                            logger.info(f"距离 {best_distance:.3f} 超过阈值 {settings.FACE_RECOGNITION_THRESHOLD}，跳过: {best_identity_path.name}")

            # 补充陌生人检测 (DeepFace.find不直接返回陌生人)
            all_faces = DeepFace.extract_faces(
                img_path=frame,
                detector_backend=self.detector_backend,
                enforce_detection=False
            )
            
            known_locations = {json.dumps(convert_numpy_types(r['location'])) for r in results}
            
            for face in all_faces:
                face_area = face['facial_area']
                loc = {"top": face_area['y'], "right": face_area['x'] + face_area['w'], "bottom": face_area['y'] + face_area['h'], "left": face_area['x']}
                loc = convert_numpy_types(loc)  # 转换NumPy类型
                
                if json.dumps(loc) not in known_locations:
                    results.append({
                        "location": loc,
                        "match": None,
                        "is_stranger": True
                    })

            logger.info(f"🎯 人脸识别完成: 已知人脸{len([r for r in results if not r['is_stranger']])}个, 陌生人脸{len([r for r in results if r['is_stranger']])}个")
            return results
            
        except Exception as e:
            # DeepFace在找不到人脸时会抛出ValueError
            if "Face could not be detected" in str(e):
                return []
            logger.error(f"人脸识别过程中发生错误: {e}")
            return []

    def _detect_strangers_only(self, frame: np.ndarray) -> List[Dict]:
        """当没有已知人脸数据时，只检测陌生人"""
        try:
            all_faces = DeepFace.extract_faces(
                img_path=frame,
                detector_backend=self.detector_backend,
                enforce_detection=False
            )
            
            results = []
            for face in all_faces:
                face_area = face['facial_area']
                loc = {"top": face_area['y'], "right": face_area['x'] + face_area['w'], "bottom": face_area['y'] + face_area['h'], "left": face_area['x']}
                loc = convert_numpy_types(loc)  # 转换NumPy类型
                
                results.append({
                    "location": loc,
                    "match": None,
                    "is_stranger": True
                })
            
            return results
        except Exception as e:
            if "Face could not be detected" in str(e):
                return []
            logger.error(f"陌生人检测失败: {e}")
            return []

    async def recognize_faces_in_frame(self, frame: np.ndarray) -> List[Dict]:
        """异步识别视频帧中的人脸"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._recognize_faces_in_frame,
            frame
        )
    
    async def register_face(self, image_path: str, user_name: str) -> Optional[int]:
        """
        注册新的人脸。
        这里我们将图片保存到特定目录，DeepFace.find会利用这个目录。
        """
        try:
            # 确保图片中有可用的人脸
            face_objects = DeepFace.extract_faces(
                img_path=image_path,
                detector_backend=self.detector_backend,
                enforce_detection=True
            )
            
            if not face_objects:
                logger.warning(f"注册失败：在图片 {image_path} 中未检测到人脸")
                return None

            # 保存到数据库以获取用户ID
            async with AsyncSessionLocal() as session:
                # 检查同名用户
                existing_user = await session.execute(select(User).where(User.name == user_name))
                if existing_user.scalar_one_or_none():
                    logger.warning(f"用户 {user_name} 已存在。")
                    # 可选择更新或返回错误
                    return None

                # 暂时不保存encoding，因为DeepFace是基于文件夹的
                user = User(
                    name=user_name,
                    face_image_path="", # 路径将在下一步确定
                    face_encoding=json.dumps([]) # 留空
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

                # 将图片保存到人脸数据库目录，文件名格式：user_{id}.jpg
                file_extension = Path(image_path).suffix
                new_image_filename = f"user_{user.id}{file_extension}"
                new_image_path = Path(self.known_faces_db_path) / new_image_filename
                
                # 复制文件
                import shutil
                shutil.copy(image_path, new_image_path)
                
                # 更新数据库中的路径
                user.face_image_path = str(new_image_path)
                # 计算并保存face_encoding
                encoding = await self.extract_face_encoding(str(new_image_path))
                if encoding is not None:
                    user.face_encoding = json.dumps(encoding.tolist())
                await session.commit()

                logger.info(f"人脸注册成功: {user_name} (ID: {user.id})")
                
                # 清理DeepFace的pickle缓存，以便新用户能被识别
                self._clear_deepface_cache()
                
                return user.id
                
        except Exception as e:
            logger.error(f"注册人脸失败 for {user_name}: {e}")
            # 如果数据库条目已创建，需要回滚或删除
            return None
            
    async def delete_face(self, user_id: int) -> bool:
        """删除已注册的人脸"""
        try:
            async with AsyncSessionLocal() as session:
                user_result = await session.execute(select(User).where(User.id == user_id))
                user = user_result.scalar_one_or_none()

                if not user:
                    return False

                # 从文件系统删除人脸图片
                face_path = Path(user.face_image_path)
                if face_path.exists():
                    face_path.unlink()
                    logger.info(f"已从文件系统删除人脸图片: {face_path}")
                
                # 从数据库删除用户记录
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()
                
                logger.info(f"已删除用户: {user.name} (ID: {user.id})")

                # 清理缓存
                self._clear_deepface_cache()
                
                return True
        except Exception as e:
            logger.error(f"删除人脸失败 (ID: {user_id}): {e}")
            return False

    def _clear_deepface_cache(self):
        """删除DeepFace在db_path下生成的.pkl缓存文件"""
        try:
            pkl_files = list(Path(self.known_faces_db_path).glob("*.pkl"))
            for file in pkl_files:
                file.unlink()
            if pkl_files:
                logger.info(f"已清理 {len(pkl_files)} 个DeepFace缓存文件。")
        except Exception as e:
            logger.error(f"清理DeepFace缓存失败: {e}")

    async def cleanup_invalid_face_files(self) -> dict:
        """清理并返回人脸文件状态信息"""
        try:
            face_files = list(Path(self.known_faces_db_path).glob("*.jpg")) + \
                        list(Path(self.known_faces_db_path).glob("*.png"))
            
            valid_files = []
            invalid_files = []
            
            for file_path in face_files:
                stem = file_path.stem
                if stem.startswith('user_'):
                    try:
                        user_id = int(stem.split('_')[1])
                        valid_files.append(file_path.name)
                    except (IndexError, ValueError):
                        invalid_files.append(file_path.name)
                else:
                    invalid_files.append(file_path.name)
            
            result = {
                "total_files": len(face_files),
                "valid_files": len(valid_files),
                "invalid_files": invalid_files,
                "valid_file_names": valid_files
            }
            
            logger.info(f"人脸文件状态: 总计{len(face_files)}个, 有效{len(valid_files)}个, 无效{len(invalid_files)}个")
            
            return result
            
        except Exception as e:
            logger.error(f"检查人脸文件状态失败: {e}")
            return {
                "total_files": 0,
                "valid_files": 0,
                "invalid_files": [],
                "valid_file_names": []
            }

    def draw_face_boxes(self, frame: np.ndarray, face_results: List[Dict]) -> np.ndarray:
        """在视频帧上绘制人脸框和信息"""
        for res in face_results:
            loc = res['location']
            top, right, bottom, left = loc['top'], loc['right'], loc['bottom'], loc['left']
            
            if res['is_stranger']:
                color = (0, 0, 255)  # 红色
                name = "陌生人"
            else:
                color = (0, 255, 0)  # 绿色
                name = res['match']['name']
                confidence = res['match']['confidence']
                name = f"{name} ({confidence:.2f})"

            # 绘制人脸框
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            
            # 绘制标签
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)
        
        return frame 

# 创建全局人脸识别服务实例，供其他模块直接导入使用
face_service = FaceRecognitionService(detector_backend='opencv') 