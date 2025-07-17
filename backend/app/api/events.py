from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_
from typing import List, Optional
from datetime import datetime, timedelta

from app.models.schemas import ResponseModel, EventResponse, EventUpdate, PaginatedResponse
from app.models.database import Event
from app.services.database import get_db
from app.services.storage import storage_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=ResponseModel)
async def get_events(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    severity: Optional[str] = Query(None, description="严重程度过滤"),
    is_processed: Optional[bool] = Query(None, description="处理状态过滤"),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db)
):
    """获取事件列表（分页）"""
    try:
        # 构建查询条件
        conditions = []
        
        if event_type:
            conditions.append(Event.event_type == event_type)
        if severity:
            conditions.append(Event.severity == severity)
        if is_processed is not None:
            conditions.append(Event.is_processed == is_processed)
        if start_date:
            conditions.append(Event.created_at >= start_date)
        if end_date:
            conditions.append(Event.created_at <= end_date)
        
        # 计算总数
        count_query = select(func.count(Event.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 查询数据
        query = select(Event).order_by(desc(Event.created_at))
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.offset((page - 1) * size).limit(size)
        result = await db.execute(query)
        events = result.scalars().all()
        
        # 转换数据格式
        event_list = []
        for event in events:
            # 生成视频URL（特殊处理视频文件路径）
            video_url = None
            if event.video_clip_path:
                # 由于视频文件保存在特殊路径，需要特殊处理URL生成
                from pathlib import Path
                video_path = Path(event.video_clip_path)
                if video_path.exists():
                    # 生成相对于media目录的URL
                    video_filename = video_path.name
                    video_url = f"/static/videos/{video_filename}"
            
            event_data = {
                "id": event.id,
                "event_type": event.event_type,
                "type": event.event_type,  # 前端使用的字段名
                "title": event.title,
                "description": event.description,
                "screenshot_url": storage_service.get_file_url(event.screenshot_path) if event.screenshot_path else None,
                "image_url": storage_service.get_file_url(event.screenshot_path) if event.screenshot_path else None,  # 前端使用的字段名
                "video_clip_url": video_url,
                "video_duration": getattr(event, 'video_duration', None),
                "video_size": getattr(event, 'video_size', None),
                "has_video": bool(video_url),
                "confidence": event.confidence,
                "location": event.location,
                "event_data": event.event_data,
                "is_processed": event.is_processed,
                "is_read": getattr(event, 'is_read', False),
                "status": getattr(event, 'status', 'pending'),
                "severity": event.severity,
                "created_at": event.created_at,
                "processed_at": event.processed_at
            }
            event_list.append(event_data)
        
        # 计算分页信息
        pages = (total + size - 1) // size
        
        return ResponseModel(
            success=True,
            message="获取事件列表成功",
            data={
                "items": event_list,
                "total": total,
                "page": page,
                "size": size,
                "pages": pages
            }
        )
    
    except Exception as e:
        logger.error(f"获取事件列表失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取事件列表失败: {str(e)}"
        )


@router.get("/recent", response_model=ResponseModel)
async def get_recent_events(
    limit: int = Query(10, ge=1, le=50, description="获取最近事件数量"),
    db: AsyncSession = Depends(get_db)
):
    """获取最近的事件列表"""
    try:
        # 查询最近的事件
        query = select(Event).order_by(desc(Event.created_at)).limit(limit)
        result = await db.execute(query)
        events = result.scalars().all()
        
        # 转换数据格式
        event_list = []
        for event in events:
            # 生成视频URL（特殊处理视频文件路径）
            video_url = None
            if event.video_clip_path:
                # 由于视频文件保存在特殊路径，需要特殊处理URL生成
                from pathlib import Path
                video_path = Path(event.video_clip_path)
                if video_path.exists():
                    # 生成相对于media目录的URL
                    video_filename = video_path.name
                    video_url = f"/static/videos/{video_filename}"
            
            event_data = {
                "id": event.id,
                "event_type": event.event_type,
                "type": event.event_type,  # 前端使用的字段名
                "title": event.title,
                "description": event.description,
                "screenshot_url": storage_service.get_file_url(event.screenshot_path) if event.screenshot_path else None,
                "image_url": storage_service.get_file_url(event.screenshot_path) if event.screenshot_path else None,  # 前端使用的字段名
                "video_clip_url": video_url,
                "video_duration": getattr(event, 'video_duration', None),
                "video_size": getattr(event, 'video_size', None),
                "has_video": bool(video_url),
                "confidence": event.confidence,
                "location": event.location,
                "event_data": event.event_data,
                "is_processed": event.is_processed,
                "is_read": getattr(event, 'is_read', False),
                "status": getattr(event, 'status', 'pending'),
                "severity": event.severity,
                "created_at": event.created_at,
                "processed_at": event.processed_at
            }
            event_list.append(event_data)
        
        return ResponseModel(
            success=True,
            message="获取最近事件成功",
            data={
                "items": event_list,
                "count": len(event_list),
                "limit": limit
            }
        )
    
    except Exception as e:
        logger.error(f"获取最近事件失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取最近事件失败: {str(e)}"
        )


@router.get("/{event_id}", response_model=ResponseModel)
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个事件详情"""
    try:
        result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            return ResponseModel(
                success=False,
                message="事件不存在"
            )

        # 生成视频URL（特殊处理视频文件路径）
        video_url = None
        if event.video_clip_path:
            from pathlib import Path
            video_path = Path(event.video_clip_path)
            if video_path.exists():
                video_filename = video_path.name
                video_url = f"/static/videos/{video_filename}"
        
        event_data = {
            "id": event.id,
            "event_type": event.event_type,
            "type": event.event_type, # 兼容前端
            "title": event.title,
            "description": event.description,
            "screenshot_path": event.screenshot_path,
            "image_url": storage_service.get_file_url(event.screenshot_path) if event.screenshot_path else None, # 兼容前端
            "video_clip_path": event.video_clip_path, # 保留原始路径供后端使用
            "video_clip_url": video_url, # 为前端提供URL
            "video_duration": getattr(event, 'video_duration', None),
            "video_size": getattr(event, 'video_size', None),
            "has_video": bool(video_url),
            "confidence": event.confidence,
            "location": event.location,
            "event_data": event.event_data,
            "is_processed": event.is_processed,
            "is_read": getattr(event, 'is_read', False), # 兼容前端
            "status": getattr(event, 'status', 'pending'), # 兼容前端
            "severity": event.severity,
            "created_at": event.created_at,
            "processed_at": event.processed_at
        }
        
        return ResponseModel(
            success=True,
            message="获取事件详情成功",
            data=event_data
        )
    
    except Exception as e:
        logger.error(f"获取事件详情失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取事件详情失败: {str(e)}"
        )


@router.put("/{event_id}", response_model=ResponseModel)
async def update_event(
    event_id: int,
    event_update: EventUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新事件信息"""
    try:
        result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            return ResponseModel(
                success=False,
                message="事件不存在"
            )
        
        # 更新字段
        if event_update.is_processed is not None:
            event.is_processed = event_update.is_processed
            if event_update.is_processed:
                event.processed_at = datetime.now()
            else:
                event.processed_at = None
        
        await db.commit()
        await db.refresh(event)
        
        return ResponseModel(
            success=True,
            message="事件更新成功",
            data={
                "id": event.id,
                "is_processed": event.is_processed,
                "processed_at": event.processed_at
            }
        )
    
    except Exception as e:
        logger.error(f"更新事件失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"更新事件失败: {str(e)}"
        )


@router.post("/{event_id}/process", response_model=ResponseModel)
async def process_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """标记事件为已处理"""
    try:
        result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            return ResponseModel(
                success=False,
                message="事件不存在"
            )
        
        event.is_processed = True
        event.processed_at = datetime.now()
        
        await db.commit()
        
        return ResponseModel(
            success=True,
            message="事件已标记为处理完成"
        )
    
    except Exception as e:
        logger.error(f"处理事件失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"处理事件失败: {str(e)}"
        )


@router.post("/batch/process", response_model=ResponseModel)
async def batch_process_events(
    event_ids: List[int],
    db: AsyncSession = Depends(get_db)
):
    """批量处理事件"""
    try:
        result = await db.execute(
            select(Event).where(Event.id.in_(event_ids))
        )
        events = result.scalars().all()
        
        processed_count = 0
        for event in events:
            if not event.is_processed:
                event.is_processed = True
                event.processed_at = datetime.now()
                processed_count += 1
        
        await db.commit()
        
        return ResponseModel(
            success=True,
            message=f"批量处理完成，共处理 {processed_count} 个事件"
        )
    
    except Exception as e:
        logger.error(f"批量处理事件失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"批量处理事件失败: {str(e)}"
        )


@router.get("/statistics/summary", response_model=ResponseModel)
async def get_event_statistics(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(get_db)
):
    """获取事件统计信息"""
    try:
        # 计算时间范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 总事件数
        total_result = await db.execute(
            select(func.count(Event.id)).where(
                Event.created_at >= start_date
            )
        )
        total_events = total_result.scalar()
        
        # 未处理事件数
        unprocessed_result = await db.execute(
            select(func.count(Event.id)).where(
                and_(
                    Event.created_at >= start_date,
                    Event.is_processed == False
                )
            )
        )
        unprocessed_events = unprocessed_result.scalar()
        
        # 按类型统计
        type_stats_result = await db.execute(
            select(Event.event_type, func.count(Event.id)).where(
                Event.created_at >= start_date
            ).group_by(Event.event_type)
        )
        type_stats = {row[0]: row[1] for row in type_stats_result.fetchall()}
        
        # 按严重程度统计
        severity_stats_result = await db.execute(
            select(Event.severity, func.count(Event.id)).where(
                Event.created_at >= start_date
            ).group_by(Event.severity)
        )
        severity_stats = {row[0]: row[1] for row in severity_stats_result.fetchall()}
        
        # 最近24小时事件数
        last_24h_result = await db.execute(
            select(func.count(Event.id)).where(
                Event.created_at >= (datetime.now() - timedelta(hours=24))
            )
        )
        last_24h_events = last_24h_result.scalar()
        
        statistics = {
            "total_events": total_events,
            "unprocessed_events": unprocessed_events,
            "processed_events": total_events - unprocessed_events,
            "last_24h_events": last_24h_events,
            "type_statistics": type_stats,
            "severity_statistics": severity_stats,
            "time_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            }
        }
        
        return ResponseModel(
            success=True,
            message="获取事件统计成功",
            data=statistics
        )
    
    except Exception as e:
        logger.error(f"获取事件统计失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取事件统计失败: {str(e)}"
        )


@router.get("/statistics", response_model=ResponseModel)
async def get_event_statistics_alias(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(get_db)
):
    """获取事件统计信息（别名）"""
    return await get_event_statistics(days, db)


@router.delete("/{event_id}", response_model=ResponseModel)
async def delete_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """删除事件"""
    try:
        result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            return ResponseModel(
                success=False,
                message="事件不存在"
            )
        
        # 删除关联的文件
        if event.screenshot_path:
            await storage_service.delete_file(event.screenshot_path)
        if event.video_clip_path:
            await storage_service.delete_file(event.video_clip_path)
        
        # 删除数据库记录
        await db.delete(event)
        await db.commit()
        
        return ResponseModel(
            success=True,
            message="事件删除成功"
        )
    
    except Exception as e:
        logger.error(f"删除事件失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"删除事件失败: {str(e)}"
        ) 


@router.put("/{event_id}/read", response_model=ResponseModel)
async def mark_event_as_read(event_id: int, db: AsyncSession = Depends(get_db)):
    """标记单个事件为已读"""
    try:
        result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            return ResponseModel(
                success=False,
                message="事件不存在"
            )
        
        event.is_read = True
        await db.commit()
        
        return ResponseModel(
            success=True,
            message="事件已标记为已读"
        )
    
    except Exception as e:
        logger.error(f"标记事件已读失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"标记事件已读失败: {str(e)}"
        )


@router.put("/mark-all-read", response_model=ResponseModel)
async def mark_all_events_as_read(db: AsyncSession = Depends(get_db)):
    """标记所有事件为已读"""
    try:
        # 查询所有未读事件
        result = await db.execute(
            select(Event).where(Event.is_read == False)
        )
        events = result.scalars().all()
        
        # 标记为已读
        for event in events:
            event.is_read = True
        
        await db.commit()
        
        return ResponseModel(
            success=True,
            message=f"已标记 {len(events)} 个事件为已读"
        )
    
    except Exception as e:
        logger.error(f"批量标记事件已读失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"批量标记事件已读失败: {str(e)}"
        )


@router.put("/{event_id}/status", response_model=ResponseModel)
async def update_event_status(
    event_id: int,
    status_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """更新事件状态"""
    try:
        result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        event = result.scalar_one_or_none()
        
        if not event:
            return ResponseModel(
                success=False,
                message="事件不存在"
            )
        
        # 更新状态
        new_status = status_data.get('status')
        if new_status:
            event.status = new_status
            if new_status == 'resolved':
                event.is_processed = True
                event.processed_at = datetime.now()
        
        await db.commit()
        
        return ResponseModel(
            success=True,
            message="事件状态更新成功",
            data={
                "id": event.id,
                "status": event.status,
                "is_processed": event.is_processed,
                "processed_at": event.processed_at
            }
        )
    
    except Exception as e:
        logger.error(f"更新事件状态失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"更新事件状态失败: {str(e)}"
        )


@router.get("/video/stats", response_model=ResponseModel)
async def get_video_storage_stats():
    """获取视频存储统计信息"""
    try:
        stats = storage_service.get_video_storage_stats()
        return ResponseModel(
            success=True,
            message="获取视频存储统计成功",
            data=stats
        )
    except Exception as e:
        logger.error(f"获取视频存储统计失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取视频存储统计失败: {str(e)}"
        ) 