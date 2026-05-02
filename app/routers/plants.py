from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.auth import get_current_user
from app.database import get_db
from app.models import Plant, User
from app.schemas import PlantArchive, PlantCreate, PlantRead, PlantUpdate

router = APIRouter(prefix="/plants", tags=["plants"])


@router.post("/", response_model=PlantRead, status_code=status.HTTP_201_CREATED)
async def create_plant(
    data: PlantCreate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    plant = Plant(**data.model_dump(), created_by=current_user.id)
    db.add(plant)
    await db.flush()
    return PlantRead.model_validate(plant)


@router.get("/", response_model=list[PlantRead])
async def list_active_plants(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(Plant).where(Plant.archived == False).order_by(Plant.name)
    )
    plants = result.scalars().all()
    return [PlantRead.model_validate(p) for p in plants]


@router.get("/archived", response_model=list[PlantRead])
async def list_archived_plants(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(Plant).where(Plant.archived == True).order_by(Plant.archived_at.desc())
    )
    plants = result.scalars().all()
    return [PlantRead.model_validate(p) for p in plants]


@router.get("/{plant_id}", response_model=PlantRead)
async def get_plant_detail(
    plant_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(select(Plant).where(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return PlantRead.model_validate(plant)


@router.put("/{plant_id}", response_model=PlantRead)
async def update_plant(
    plant_id: int,
    data: PlantUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(select(Plant).where(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(plant, key, value)
    plant.updated_at = datetime.now(timezone.utc)
    return PlantRead.model_validate(plant)


@router.post("/{plant_id}/archive", response_model=PlantRead)
async def archive_plant(
    plant_id: int,
    data: PlantArchive,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(select(Plant).where(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    plant.archived = True
    plant.archived_at = datetime.now(timezone.utc)
    plant.archived_by = current_user.id
    plant.archive_reason = data.reason
    return PlantRead.model_validate(plant)


@router.post("/{plant_id}/unarchive", response_model=PlantRead)
async def unarchive_plant(
    plant_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(select(Plant).where(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    plant.archived = False
    plant.archived_at = None
    plant.archived_by = None
    plant.archive_reason = None
    return PlantRead.model_validate(plant)


@router.delete("/{plant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plant(
    plant_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(select(Plant).where(Plant.id == plant_id))
    plant = result.scalar_one_or_none()
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await db.delete(plant)
