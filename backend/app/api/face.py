from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_, or_
from typing import List, Optional
import shutil
import os
from pathlib import Path
from pydantic import BaseModel
import json

from app.models.schemas import ResponseModel, UserResponse, UserCreate
from app.models.database import User, AnalysisLog
from app.services.database import get_db
from app.services.face_recognition import face_service
from app.services.storage import storage_service
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=ResponseModel)
async def get_face_list_simple(db: AsyncSession = Depends(get_db)):
    """获取人脸列表（简化版本）"""
    try:
        result = await db.execute(
            select(User).where(User.is_active == True).order_by(User.created_at.desc())
        )
        users = result.scalars().all()
        
        user_list = []
        for user in users:
            user_list.append({
                "id": user.id,
                "name": user.name,
                "face_image_url": storage_service.get_file_url(user.face_image_path),
                "created_at": user.created_at
            })
        
        return ResponseModel(
            success=True,
            message="获取人脸列表成功",
            data=user_list
        )
    
    except Exception as e:
        logger.error(f"获取人脸列表失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取人脸列表失败: {str(e)}"
        )


@router.post("/register", response_model=ResponseModel)
async def register_face(
    name: str = Form(...),
    face_image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """注册新的人脸"""
    try:
        # 验证文件类型
        if not face_image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="请上传图片文件")
        
        # 读取图片数据
        image_content = await face_image.read()
        
        # 保存人脸图片
        file_path, url = await storage_service.save_face_image(
            image_content,
            f"{name}_{face_image.filename}"
        )
        
        # 优化图片
        await storage_service.optimize_image(file_path)
        
        # 注册人脸
        user_id = await face_service.register_face(file_path, name)
        
        if user_id:
            return ResponseModel(
                success=True,
                message="人脸注册成功",
                data={
                    "user_id": user_id,
                    "name": name,
                    "face_image_url": url
                }
            )
        else:
            # 删除已保存的文件
            await storage_service.delete_file(file_path)
            return ResponseModel(
                success=False,
                message="人脸注册失败，请确保图片中包含清晰的人脸"
            )
    
    except Exception as e:
        logger.error(f"人脸注册失败: {e}")
        return ResponseModel(
            success=False,
            message=f"人脸注册失败: {str(e)}"
        )


class RegisterByPathRequest(BaseModel):
    name: str
    image_path: str
    description: Optional[str] = None

@router.post("/register-by-path", response_model=ResponseModel)
async def register_face_by_path(
    req: RegisterByPathRequest,
    db: AsyncSession = Depends(get_db)
):
    """通过已上传的图片路径注册人脸"""
    try:
        name = req.name
        image_path = req.image_path
        # 验证文件是否存在
        if not os.path.exists(image_path):
            return ResponseModel(success=False, message="图片文件不存在")
        user_id = await face_service.register_face(image_path, name)
        if user_id:
            url = storage_service.get_file_url(image_path)
            return ResponseModel(success=True, message="人脸注册成功", data={"user_id": user_id, "name": name, "face_image_url": url})
        else:
            return ResponseModel(success=False, message="人脸注册失败，请确保图片中包含清晰的人脸")
    except Exception as e:
        logger.error(f"人脸注册失败: {e}")
        return ResponseModel(success=False, message=f"人脸注册失败: {str(e)}")


@router.get("/users", response_model=ResponseModel)
async def get_users(db: AsyncSession = Depends(get_db)):
    """获取所有已注册用户"""
    try:
        # 获取所有用户（包括禁用的）
        result = await db.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = result.scalars().all()
        
        user_list = []
        for user in users:
            # 查询该用户的识别统计
            try:
                # 查询最后一次识别时间
                last_recognition_result = await db.execute(
                    select(AnalysisLog)
                    .where(
                        AnalysisLog.analysis_type == 'face_recognition',
                        AnalysisLog.result.like(f'%"user_id": {user.id}%')
                    )
                    .order_by(desc(AnalysisLog.created_at))
                    .limit(1)
                )
                last_recognition = last_recognition_result.scalar_one_or_none()
                
                # 查询识别总次数
                recognition_count_result = await db.execute(
                    select(func.count(AnalysisLog.id))
                    .where(
                        AnalysisLog.analysis_type == 'face_recognition',
                        AnalysisLog.result.like(f'%"user_id": {user.id}%')
                    )
                )
                recognition_count = recognition_count_result.scalar() or 0
                
                user_data = {
                    "id": user.id,
                    "name": user.name,
                    "face_image_url": storage_service.get_file_url(user.face_image_path),
                    "created_at": user.created_at,
                    "is_active": user.is_active,
                    "last_recognized_at": last_recognition.created_at if last_recognition else None,
                    "recognition_count": recognition_count
                }
                
            except Exception as stat_error:
                logger.error(f"获取用户 {user.id} 统计信息失败: {stat_error}")
                # 如果统计查询失败，仍然返回基本信息
                user_data = {
                    "id": user.id,
                    "name": user.name,
                    "face_image_url": storage_service.get_file_url(user.face_image_path),
                    "created_at": user.created_at,
                    "is_active": user.is_active,
                    "last_recognized_at": None,
                    "recognition_count": 0
                }
            
            user_list.append(user_data)
        
        return ResponseModel(
            success=True,
            message="获取用户列表成功",
            data=user_list
        )
    
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取用户列表失败: {str(e)}"
        )


@router.get("/users/{user_id}", response_model=ResponseModel)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个用户信息"""
    try:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return ResponseModel(
                success=False,
                message="用户不存在"
            )
        
        user_data = {
            "id": user.id,
            "name": user.name,
            "face_image_url": storage_service.get_file_url(user.face_image_path),
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "is_active": user.is_active
        }
        
        return ResponseModel(
            success=True,
            message="获取用户信息成功",
            data=user_data
        )
    
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取用户信息失败: {str(e)}"
        )


@router.put("/users/{user_id}", response_model=ResponseModel)
async def update_user(
    user_id: int,
    name: str = Form(None),
    face_image: UploadFile = File(None),
    db: AsyncSession = Depends(get_db)
):
    """更新用户信息"""
    try:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return ResponseModel(
                success=False,
                message="用户不存在"
            )
        
        # 更新姓名
        if name:
            user.name = name
        
        # 更新人脸图片
        if face_image:
            if not face_image.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="请上传图片文件")
            
            # 删除旧图片
            await storage_service.delete_file(user.face_image_path)
            
            # 保存新图片
            image_content = await face_image.read()
            file_path, url = await storage_service.save_face_image(
                image_content,
                f"{user.name}_{face_image.filename}"
            )
            
            # 优化图片
            await storage_service.optimize_image(file_path)
            
            # 重新提取人脸特征
            face_encoding = await face_service.extract_face_encoding(file_path)
            if not face_encoding:
                await storage_service.delete_file(file_path)
                return ResponseModel(
                    success=False,
                    message="新图片中未检测到人脸，请重新上传"
                )
            
            # 更新数据库
            import json
            user.face_image_path = file_path
            user.face_encoding = json.dumps(face_encoding.tolist())
            
            # 更新内存缓存
            face_service.known_faces[user.id] = {
                "name": user.name,
                "encoding": face_encoding,
                "image_path": file_path
            }
        
        await db.commit()
        await db.refresh(user)
        
        return ResponseModel(
            success=True,
            message="用户信息更新成功",
            data={
                "id": user.id,
                "name": user.name,
                "face_image_url": storage_service.get_file_url(user.face_image_path)
            }
        )
    
    except Exception as e:
        logger.error(f"更新用户信息失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"更新用户信息失败: {str(e)}"
        )


@router.delete("/users/{user_id}", response_model=ResponseModel)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """删除用户（软删除）"""
    try:
        result = await face_service.delete_face(user_id)
        
        if result:
            return ResponseModel(
                success=True,
                message="用户删除成功"
            )
        else:
            return ResponseModel(
                success=False,
                message="用户不存在或删除失败"
            )
    
    except Exception as e:
        logger.error(f"删除用户失败: {e}")
        return ResponseModel(
            success=False,
            message=f"删除用户失败: {str(e)}"
        )


class UpdateStatusRequest(BaseModel):
    is_active: bool

@router.put("/{user_id}/status", response_model=ResponseModel)
async def update_user_status(
    user_id: int,
    req: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新用户状态（启用/禁用）"""
    try:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return ResponseModel(
                success=False,
                message="用户不存在"
            )
        
        # 更新状态
        old_status = user.is_active
        user.is_active = req.is_active
        await db.commit()
        await db.refresh(user)
        
        # 状态变更时需要同步人脸识别缓存
        if old_status != req.is_active:
            try:
                # 清理DeepFace缓存文件，强制重新建立索引
                face_service._clear_deepface_cache()
                
                # 重新加载已知人脸数据
                await face_service.load_known_faces()
                
                logger.info(f"用户 {user.name} (ID: {user_id}) 状态已更新为 {'启用' if req.is_active else '禁用'}，已同步人脸识别缓存")
                
            except Exception as cache_error:
                logger.error(f"同步人脸识别缓存失败: {cache_error}")
                # 即使缓存同步失败，数据库状态更新仍然有效
        
        status_text = "启用" if req.is_active else "禁用"
        return ResponseModel(
            success=True,
            message=f"用户已{status_text}",
            data={
                "id": user.id,
                "name": user.name,
                "is_active": user.is_active
            }
        )
    
    except Exception as e:
        logger.error(f"更新用户状态失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"更新用户状态失败: {str(e)}"
        )


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_path: Optional[str] = None

@router.put("/{user_id}", response_model=ResponseModel)
async def update_user_simple(
    user_id: int,
    req: UpdateUserRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新用户信息（简化版本）"""
    try:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return ResponseModel(
                success=False,
                message="用户不存在"
            )
        
        # 更新姓名
        if req.name:
            user.name = req.name.strip()
        
        # 更新人脸图片
        if req.image_path:
            if not os.path.exists(req.image_path):
                return ResponseModel(
                    success=False,
                    message="指定的图片文件不存在"
                )
            
            # 删除旧图片
            if user.face_image_path and os.path.exists(user.face_image_path):
                await storage_service.delete_file(user.face_image_path)
            
            # 重新提取人脸特征
            face_encoding = await face_service.extract_face_encoding(req.image_path)
            if not face_encoding:
                return ResponseModel(
                    success=False,
                    message="新图片中未检测到人脸，请重新上传"
                )
            
            # 更新数据库
            import json
            user.face_image_path = req.image_path
            user.face_encoding = json.dumps(face_encoding.tolist())
            
            # 更新内存缓存
            face_service.known_faces[user.id] = {
                "name": user.name,
                "encoding": face_encoding,
                "image_path": req.image_path
            }
        
        await db.commit()
        await db.refresh(user)
        
        return ResponseModel(
            success=True,
            message="用户信息更新成功",
            data={
                "id": user.id,
                "name": user.name,
                "face_image_url": storage_service.get_file_url(user.face_image_path),
                "is_active": user.is_active
            }
        )
    
    except Exception as e:
        logger.error(f"更新用户信息失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"更新用户信息失败: {str(e)}"
        )


@router.post("/reload", response_model=ResponseModel)
async def reload_faces():
    """重新加载人脸数据"""
    try:
        await face_service.load_known_faces()
        return ResponseModel(
            success=True,
            message="人脸数据重新加载成功",
            data={
                "known_faces_count": face_service.get_known_faces_count()
            }
        )
    
    except Exception as e:
        logger.error(f"重新加载人脸数据失败: {e}")
        return ResponseModel(
            success=False,
            message=f"重新加载人脸数据失败: {str(e)}"
        )


@router.get("/statistics", response_model=ResponseModel)
async def get_face_statistics(db: AsyncSession = Depends(get_db)):
    """获取人脸识别统计信息"""
    try:
        # 获取清理状态信息
        cleanup_result = await face_service.cleanup_invalid_face_files()
        
        # 计算今日识别次数
        from datetime import datetime, timedelta
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # 查询今日人脸识别记录数（包含实际识别到的用户）
        today_recognition_result = await db.execute(
            select(func.count(AnalysisLog.id))
            .where(
                AnalysisLog.analysis_type == 'face_recognition',
                AnalysisLog.created_at >= today_start,
                AnalysisLog.created_at < today_end,
                AnalysisLog.result.like('%"user_id":%')
            )
        )
        today_recognitions = today_recognition_result.scalar() or 0
        
        # 计算总识别次数（包含实际识别到的用户）
        total_recognition_result = await db.execute(
            select(func.count(AnalysisLog.id))
            .where(
                AnalysisLog.analysis_type == 'face_recognition',
                AnalysisLog.result.like('%"user_id":%')
            )
        )
        total_recognitions = total_recognition_result.scalar() or 0
        
        stats = {
            "known_faces_count": face_service.get_known_faces_count(),
            "service_status": "运行中" if face_service.known_faces else "未初始化",
            "today_recognitions": today_recognitions,
            "total_recognitions": total_recognitions,
            "file_status": {
                "total_files": cleanup_result.get("total_files", 0),
                "valid_files": cleanup_result.get("valid_files", 0),
                "invalid_files_count": len(cleanup_result.get("invalid_files", [])),
                "invalid_files": cleanup_result.get("invalid_files", [])
            }
        }
        
        return ResponseModel(
            success=True,
            message="获取统计信息成功",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取统计信息失败: {str(e)}"
        ) 

@router.post("/upload", response_model=ResponseModel)
async def upload_face(
    person_name: Optional[str] = Form(None, alias="name", description="（可选）用户姓名，用于直接注册"),
    file: UploadFile = File(..., description="人脸图片文件"),
    db: AsyncSession = Depends(get_db)
):
    """上传人脸图片并注册"""
    logger.debug(f"收到上传请求: name={person_name}, filename={file.filename if file else '无'}, content_type={file.content_type if file else '无'}")
    try:
        name = person_name.strip() if person_name else None
        
        # 验证文件
        if not file or not file.filename:
            return ResponseModel(
                success=False,
                message="请选择要上传的图片文件"
            )
        
        # 验证文件类型
        if not file.content_type or not file.content_type.startswith('image/'):
            return ResponseModel(
                success=False,
                message="文件必须是图片格式（jpg、png等）"
            )
        
        # 读取图片数据
        image_content = await file.read()
        
        if len(image_content) == 0:
            return ResponseModel(
                success=False,
                message="上传的图片文件为空"
            )
        
        # 保存人脸图片
        file_path, url = await storage_service.save_face_image(
            image_content,
            f"{name}_{file.filename}" if name else file.filename
        )
        
        # 优化图片
        await storage_service.optimize_image(file_path)
        
        # 修复URL中的反斜杠为正斜杠
        url = url.replace('\\', '/')
        
        if name:
            # 注册人脸
            user_id = await face_service.register_face(file_path, name)
        else:
            user_id = None

        if user_id:
            return ResponseModel(
                success=True,
                message="人脸注册成功",
                data={
                    "user_id": user_id,
                    "name": name,
                    "face_image_url": url
                }
            )
        else:
            # 如果仅上传，不删除文件，返回路径供后续注册
            if not name:
                return ResponseModel(
                    success=True,
                    message="图片上传成功",
                    data={
                        "file_path": file_path,
                        "url": url
                    }
                )
            await storage_service.delete_file(file_path)
            return ResponseModel(
                success=False,
                message="人脸注册失败，请确保图片中包含清晰的人脸"
            )
            
    except Exception as e:
        logger.error(f"上传人脸失败: {e}")
        return ResponseModel(
            success=False,
            message=f"上传失败: {str(e)}"
        )

@router.get("/{user_id}/recognition-history", response_model=ResponseModel)
async def get_user_recognition_history(
    user_id: int,
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db)
):
    """获取指定用户的识别历史记录"""
    try:
        # 验证用户是否存在
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return ResponseModel(
                success=False,
                message="用户不存在"
            )
        
        # 查询人脸识别分析日志
        logs_query = select(AnalysisLog).where(
            AnalysisLog.analysis_type == "face_recognition"
        ).order_by(desc(AnalysisLog.created_at))
        
        logs_result = await db.execute(logs_query)
        all_logs = logs_result.scalars().all()
        
        # 过滤包含目标用户的识别记录
        user_recognition_records = []
        for log in all_logs:
            if log.result and isinstance(log.result, dict):
                recognized_users = log.result.get("recognized_users", [])
                
                # 查找是否包含目标用户
                for recognized_user in recognized_users:
                    if recognized_user.get("user_id") == user_id:
                        user_recognition_records.append({
                            "id": log.id,
                            "recognition_time": log.created_at,
                            "screenshot_url": storage_service.get_file_url(log.screenshot_path),
                            "confidence": recognized_user.get("confidence", 0.0),
                            "distance": recognized_user.get("distance", 0.0),
                            "location": recognized_user.get("location", {}),
                            "user_id": user_id,
                            "user_name": user.name,
                            "processing_time": log.processing_time,
                            "faces_detected_total": log.result.get("faces_detected", 0),
                            "strangers_count": log.result.get("strangers_count", 0)
                        })
                        break  # 一个日志中只记录一次该用户
        
        # 分页处理
        total = len(user_recognition_records)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_records = user_recognition_records[start_idx:end_idx]
        
        pages = (total + size - 1) // size
        
        return ResponseModel(
            success=True,
            message="获取用户识别历史成功",
            data={
                "user_id": user_id,
                "user_name": user.name,
                "records": paginated_records,
                "total": total,
                "page": page,
                "size": size,
                "pages": pages
            }
        )
        
    except Exception as e:
        logger.error(f"获取用户识别历史失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取用户识别历史失败: {str(e)}"
        )

@router.get("/list")
async def get_face_list():
    """获取已注册的人脸列表"""
    try:
        from app.services.database import AsyncSessionLocal
        from app.models.database import User
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.is_active == True))
            users = result.scalars().all()
            
            face_list = []
            for user in users:
                face_list.append({
                    "id": user.id,
                    "name": user.name,
                    "face_image_path": user.face_image_path,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                })
            
            return {"success": True, "faces": face_list}
            
    except Exception as e:
        logger.error(f"获取人脸列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")

@router.delete("/{user_id}")
async def delete_face(user_id: int):
    """删除指定的人脸"""
    try:
        success = await face_service.delete_face(user_id)
        
        if success:
            return {"success": True, "message": "人脸删除成功"}
        else:
            return {"success": False, "message": "人脸删除失败，用户不存在"}
            
    except Exception as e:
        logger.error(f"删除人脸失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}") 