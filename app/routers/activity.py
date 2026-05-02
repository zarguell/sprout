from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload

from app.auth import get_current_user
from app.database import get_db
from app.dependencies import form_or_json
from app.models import Plant, PlantActivity, User
from app.schemas import ActivityCreate, ActivityRead

router = APIRouter(prefix="/plants/{plant_id}/activity", tags=["activity"])


@router.get("/", response_model=list[ActivityRead])
async def list_activity(
    plant_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(PlantActivity)
        .where(PlantActivity.plant_id == plant_id)
        .options(joinedload(PlantActivity.user))
        .order_by(desc(PlantActivity.created_at))
        .limit(limit)
        .offset(offset)
    )
    entries = result.scalars().unique().all()
    return [
        ActivityRead(
            id=e.id,
            plant_id=e.plant_id,
            user_id=e.user_id,
            username=e.user.username,
            display_name=e.user.display_name or e.user.username,
            content=e.content,
            created_at=e.created_at,
        )
        for e in entries
    ]


@router.post("/", response_model=ActivityRead, status_code=status.HTTP_201_CREATED)
async def create_activity(
    plant_id: int,
    data: ActivityCreate = Depends(form_or_json(ActivityCreate)),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    # Verify plant exists
    plant = await db.get(Plant, plant_id)
    if not plant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plant not found")

    entry = PlantActivity(
        plant_id=plant_id,
        user_id=current_user.id,
        content=data.content,
    )
    db.add(entry)
    await db.flush()

    return ActivityRead(
        id=entry.id,
        plant_id=entry.plant_id,
        user_id=entry.user_id,
        username=current_user.username,
        display_name=current_user.display_name or current_user.username,
        content=entry.content,
        created_at=entry.created_at,
    )
