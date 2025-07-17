from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.models.schemas import ResponseModel, DangerZoneCreate, DangerZoneUpdate, DangerZoneResponse
from app.models.database import DangerZone
from app.services.database import get_db
from app.services.zone_detection import zone_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=ResponseModel)
async def create_danger_zone(
    zone_data: DangerZoneCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建危险区域"""
    try:
        # 创建数据库记录
        zone = DangerZone(
            name=zone_data.name,
            zone_type=zone_data.zone_type,
            coordinates=zone_data.coordinates,
            stay_threshold=zone_data.stay_threshold
        )
        
        db.add(zone)
        await db.commit()
        await db.refresh(zone)
        
        # 重新加载危险区域数据
        await zone_service.load_danger_zones()
        
        return ResponseModel(
            success=True,
            message="危险区域创建成功",
            data={
                "id": zone.id,
                "name": zone.name,
                "zone_type": zone.zone_type,
                "coordinates": zone.coordinates,
                "stay_threshold": zone.stay_threshold
            }
        )
    
    except Exception as e:
        logger.error(f"创建危险区域失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"创建危险区域失败: {str(e)}"
        )


@router.get("/", response_model=ResponseModel)
async def get_danger_zones(db: AsyncSession = Depends(get_db)):
    """获取所有危险区域"""
    try:
        result = await db.execute(
            select(DangerZone).where(DangerZone.is_active == True).order_by(DangerZone.created_at.desc())
        )
        zones = result.scalars().all()
        
        zone_list = []
        for zone in zones:
            zone_list.append({
                "id": zone.id,
                "name": zone.name,
                "zone_type": zone.zone_type,
                "coordinates": zone.coordinates,
                "stay_threshold": zone.stay_threshold,
                "is_active": zone.is_active,
                "created_at": zone.created_at,
                "updated_at": zone.updated_at
            })
        
        return ResponseModel(
            success=True,
            message="获取危险区域列表成功",
            data=zone_list
        )
    
    except Exception as e:
        logger.error(f"获取危险区域列表失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取危险区域列表失败: {str(e)}"
        )


@router.get("/{zone_id}", response_model=ResponseModel)
async def get_danger_zone(zone_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个危险区域"""
    try:
        result = await db.execute(
            select(DangerZone).where(DangerZone.id == zone_id, DangerZone.is_active == True)
        )
        zone = result.scalar_one_or_none()
        
        if not zone:
            return ResponseModel(
                success=False,
                message="危险区域不存在"
            )
        
        zone_data = {
            "id": zone.id,
            "name": zone.name,
            "zone_type": zone.zone_type,
            "coordinates": zone.coordinates,
            "stay_threshold": zone.stay_threshold,
            "is_active": zone.is_active,
            "created_at": zone.created_at,
            "updated_at": zone.updated_at
        }
        
        return ResponseModel(
            success=True,
            message="获取危险区域信息成功",
            data=zone_data
        )
    
    except Exception as e:
        logger.error(f"获取危险区域信息失败: {e}")
        return ResponseModel(
            success=False,
            message=f"获取危险区域信息失败: {str(e)}"
        )


@router.put("/{zone_id}", response_model=ResponseModel)
async def update_danger_zone(
    zone_id: int,
    zone_data: DangerZoneUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新危险区域"""
    try:
        result = await db.execute(
            select(DangerZone).where(DangerZone.id == zone_id, DangerZone.is_active == True)
        )
        zone = result.scalar_one_or_none()
        
        if not zone:
            return ResponseModel(
                success=False,
                message="危险区域不存在"
            )
        
        # 更新字段
        if zone_data.name is not None:
            zone.name = zone_data.name
        if zone_data.coordinates is not None:
            zone.coordinates = zone_data.coordinates
        if zone_data.stay_threshold is not None:
            zone.stay_threshold = zone_data.stay_threshold
        if zone_data.is_active is not None:
            zone.is_active = zone_data.is_active
        
        await db.commit()
        await db.refresh(zone)
        
        # 重新加载危险区域数据
        await zone_service.load_danger_zones()
        
        return ResponseModel(
            success=True,
            message="危险区域更新成功",
            data={
                "id": zone.id,
                "name": zone.name,
                "zone_type": zone.zone_type,
                "coordinates": zone.coordinates,
                "stay_threshold": zone.stay_threshold,
                "is_active": zone.is_active
            }
        )
    
    except Exception as e:
        logger.error(f"更新危险区域失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"更新危险区域失败: {str(e)}"
        )


@router.delete("/{zone_id}", response_model=ResponseModel)
async def delete_danger_zone(zone_id: int, db: AsyncSession = Depends(get_db)):
    """删除危险区域（软删除）"""
    try:
        result = await db.execute(
            select(DangerZone).where(DangerZone.id == zone_id, DangerZone.is_active == True)
        )
        zone = result.scalar_one_or_none()
        
        if not zone:
            return ResponseModel(
                success=False,
                message="危险区域不存在"
            )
        
        # 软删除
        zone.is_active = False
        await db.commit()
        
        # 重新加载危险区域数据
        await zone_service.load_danger_zones()
        
        return ResponseModel(
            success=True,
            message="危险区域删除成功"
        )
    
    except Exception as e:
        logger.error(f"删除危险区域失败: {e}")
        await db.rollback()
        return ResponseModel(
            success=False,
            message=f"删除危险区域失败: {str(e)}"
        )


@router.post("/reload", response_model=ResponseModel)
async def reload_danger_zones():
    """重新加载危险区域数据"""
    try:
        await zone_service.load_danger_zones()
        stats = zone_service.get_zone_statistics()
        
        return ResponseModel(
            success=True,
            message="危险区域数据重新加载成功",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"重新加载危险区域数据失败: {e}")
        return ResponseModel(
            success=False,
            message=f"重新加载危险区域数据失败: {str(e)}"
        )


@router.get("/statistics/current", response_model=ResponseModel)
async def get_zone_statistics():
    """获取危险区域统计信息"""
    try:
        stats = zone_service.get_zone_statistics()
        
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