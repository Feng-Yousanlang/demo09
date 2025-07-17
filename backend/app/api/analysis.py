from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional
from datetime import datetime, timedelta

from app.models.schemas import ResponseModel, AnalysisLogResponse
from app.models.database import AnalysisLog
from app.services.database import get_db
from app.services.ai_analysis import ai_service
from app.services.storage import storage_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def get_ai_service(request: Request):
    """获取AI分析服务实例"""
    return request.app.state.ai_service


@router.get("/logs", response_model=ResponseModel)
async def get_analysis_logs(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    analysis_type: Optional[str] = Query(None, description="分析类型过滤"),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db)
):
    """获取分析日志列表"""
    try:
        # 构建查询条件
        conditions = []
        
        if analysis_type:
            conditions.append(AnalysisLog.analysis_type == analysis_type)
        if start_date:
            conditions.append(AnalysisLog.created_at >= start_date)
        if end_date:
            conditions.append(AnalysisLog.created_at <= end_date)
        
        # 计算总数
        count_query = select(func.count(AnalysisLog.id))
        if conditions:
            from sqlalchemy import and_
            count_query = count_query.where(and_(*conditions))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 查询数据
        query = select(AnalysisLog).order_by(desc(AnalysisLog.created_at))
        if conditions:
            from sqlalchemy import and_
            query = query.where(and_(*conditions))
        
        query = query.offset((page - 1) * size).limit(size)
        result = await db.execute(query)
        logs = result.scalars().all()
        
        # 转换数据格式
        log_list = []
        for log in logs:
            log_data = {
                "id": log.id,
                "analysis_type": log.analysis_type,
                "screenshot_url": storage_service.get_file_url(log.screenshot_path),
                "result": log.result,
                "confidence": log.confidence,
                "processing_time": log.processing_time,
                "created_at": log.created_at
            }
            log_list.append(log_data)
        
        # 计算分页信息
        pages = (total + size - 1) // size
        
        return ResponseModel(
            success=True,
            message="获取分析日志成功",
            data={
                "items": log_list,
                "total": total,
                "page": page,
                "size": size,
                "pages": pages
            }
        )
    
    except Exception as e:
        logger.error(f"获取分析日志失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取分析日志失败: {str(e)}"
        )


@router.get("/logs/{log_id}", response_model=ResponseModel)
async def get_analysis_log(log_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个分析日志详情"""
    try:
        result = await db.execute(
            select(AnalysisLog).where(AnalysisLog.id == log_id)
        )
        log = result.scalar_one_or_none()
        
        if not log:
            return ResponseModel(
                success=False,
                message="分析日志不存在"
            )
        
        log_data = {
            "id": log.id,
            "analysis_type": log.analysis_type,
            "screenshot_url": storage_service.get_file_url(log.screenshot_path),
            "result": log.result,
            "confidence": log.confidence,
            "processing_time": log.processing_time,
            "created_at": log.created_at
        }
        
        return ResponseModel(
            success=True,
            message="获取分析日志详情成功",
            data=log_data
        )
    
    except Exception as e:
        logger.error(f"获取分析日志详情失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取分析日志详情失败: {str(e)}"
        )


@router.get("/statistics", response_model=ResponseModel)
async def get_analysis_statistics(
    ai_service=Depends(get_ai_service)
):
    """获取AI分析统计信息"""
    try:
        stats = ai_service.get_statistics()
        
        return ResponseModel(
            success=True,
            message="获取AI分析统计成功",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"获取AI分析统计失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取AI分析统计失败: {str(e)}"
        )


@router.get("/stats", response_model=ResponseModel)
async def get_analysis_stats_alias(
    ai_service=Depends(get_ai_service)
):
    """获取AI分析统计信息（别名）"""
    return await get_analysis_statistics(ai_service)


@router.get("/statistics/performance", response_model=ResponseModel)
async def get_analysis_performance(
    days: int = Query(7, ge=1, le=30, description="统计天数"),
    db: AsyncSession = Depends(get_db)
):
    """获取分析性能统计"""
    try:
        # 计算时间范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 按类型统计分析次数
        type_stats_result = await db.execute(
            select(
                AnalysisLog.analysis_type,
                func.count(AnalysisLog.id).label('count'),
                func.avg(AnalysisLog.processing_time).label('avg_time'),
                func.avg(AnalysisLog.confidence).label('avg_confidence')
            ).where(
                AnalysisLog.created_at >= start_date
            ).group_by(AnalysisLog.analysis_type)
        )
        
        type_stats = []
        for row in type_stats_result.fetchall():
            type_stats.append({
                "type": row[0],
                "count": row[1],
                "avg_processing_time": float(row[2]) if row[2] else 0,
                "avg_confidence": float(row[3]) if row[3] else 0
            })
        
        # 总体统计
        total_result = await db.execute(
            select(
                func.count(AnalysisLog.id),
                func.avg(AnalysisLog.processing_time),
                func.avg(AnalysisLog.confidence)
            ).where(
                AnalysisLog.created_at >= start_date
            )
        )
        total_row = total_result.fetchone()
        
        total_stats = {
            "total_analyses": total_row[0] if total_row else 0,
            "avg_processing_time": float(total_row[1]) if total_row and total_row[1] else 0,
            "avg_confidence": float(total_row[2]) if total_row and total_row[2] else 0
        }
        
        # 每日统计
        daily_stats_result = await db.execute(
            select(
                func.date(AnalysisLog.created_at).label('date'),
                func.count(AnalysisLog.id).label('count')
            ).where(
                AnalysisLog.created_at >= start_date
            ).group_by(func.date(AnalysisLog.created_at))
            .order_by(func.date(AnalysisLog.created_at))
        )
        
        daily_stats = []
        for row in daily_stats_result.fetchall():
            daily_stats.append({
                "date": row[0].isoformat(),
                "count": row[1]
            })
        
        performance_data = {
            "total_statistics": total_stats,
            "type_statistics": type_stats,
            "daily_statistics": daily_stats,
            "time_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            }
        }
        
        return ResponseModel(
            success=True,
            message="获取分析性能统计成功",
            data=performance_data
        )
    
    except Exception as e:
        logger.error(f"获取分析性能统计失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取分析性能统计失败: {str(e)}"
        )


@router.post("/reload", response_model=ResponseModel)
async def reload_ai_data(ai_service=Depends(get_ai_service)):
    """重新加载AI数据"""
    try:
        # 重新加载人脸和区域数据
        from app.services.face_recognition import face_service
        from app.services.zone_detection import zone_service
        
        await face_service.load_known_faces()
        await zone_service.load_danger_zones()
        
        stats = ai_service.get_statistics()
        
        return ResponseModel(
            success=True,
            message="AI数据重新加载成功",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"重新加载AI数据失败: {e}")
        return ResponseModel(
            success=False,
            message=f"重新加载AI数据失败: {str(e)}"
        )


@router.get("/health", response_model=ResponseModel)
async def analysis_health_check(ai_service=Depends(get_ai_service)):
    """AI分析服务健康检查"""
    try:
        health_info = {
            "ai_service_running": ai_service.is_running,
            "analysis_thread_alive": ai_service.analysis_thread.is_alive() if ai_service.analysis_thread else False,
            "video_service_connected": ai_service.video_service is not None,
            "known_faces_loaded": ai_service.get_statistics()["known_faces_count"] > 0,
            "danger_zones_loaded": ai_service.get_statistics()["zone_statistics"]["total_zones"] > 0
        }
        
        return ResponseModel(
            success=True,
            message="AI分析服务健康检查完成",
            data=health_info
        )
    
    except Exception as e:
        logger.error(f"AI分析服务健康检查失败: {e}")
        return ResponseModel(
            success=False,
            message=f"健康检查失败: {str(e)}"
        ) 