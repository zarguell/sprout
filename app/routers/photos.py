import os
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth import get_current_user
from app.database import get_db
from app.images import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    create_thumbnail,
    generate_photo_filename,
    get_content_type,
)
from app.models import Photo, Plant
from app.schemas import PhotoRead

PHOTO_STORAGE_PATH = os.getenv("PHOTO_STORAGE_PATH", "./data/photos")

router = APIRouter(prefix="/plants/{plant_id}/photos", tags=["photos"])


@router.post("/", response_model=PhotoRead, status_code=201)
async def upload_photo(
    plant_id: int,
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type")

    # Validate size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    # Check if first photo
    result = await db.execute(
        select(func.count(Photo.id)).where(Photo.plant_id == plant_id)
    )
    is_first = result.scalar() == 0

    # Generate filename
    base_name = generate_photo_filename(plant_id)
    filename = f"{base_name}{ext}"

    # Paths
    original_path_rel = filename
    thumbnail_path_rel = f"{filename}.thumbnail.jpg"
    original_full = Path(PHOTO_STORAGE_PATH) / original_path_rel
    thumbnail_full = Path(PHOTO_STORAGE_PATH) / thumbnail_path_rel

    # Ensure dir exists
    original_full.parent.mkdir(parents=True, exist_ok=True)

    # Save original
    with open(original_full, "wb") as f:
        f.write(contents)

    # Create thumbnail
    create_thumbnail(str(original_full), str(thumbnail_full))

    # Create DB record
    photo = Photo(
        plant_id=plant_id,
        original_path=original_path_rel,
        thumbnail_path=thumbnail_path_rel,
        uploaded_by=current_user.id,
        caption=caption,
    )
    db.add(photo)
    await db.flush()

    # Set as primary if first
    if is_first:
        plant = await db.get(Plant, plant_id)
        plant.primary_photo_id = photo.id

    await db.commit()

    # Return PhotoRead
    result = await db.execute(
        select(Photo)
        .where(Photo.id == photo.id)
        .options(joinedload(Photo.uploaded_by_user))
    )
    photo = result.scalar_one()
    plant_result = await db.execute(
        select(Plant.primary_photo_id).where(Plant.id == plant_id)
    )
    primary_id = plant_result.scalar()
    original_url = f"/api/plants/{plant_id}/photos/{photo.id}/file"
    thumbnail_url = f"/api/plants/{plant_id}/photos/{photo.id}/thumbnail"
    is_primary = photo.id == primary_id
    return PhotoRead.model_validate(
        {
            "id": photo.id,
            "plant_id": photo.plant_id,
            "original_url": original_url,
            "thumbnail_url": thumbnail_url,
            "uploaded_by": photo.uploaded_by_user.username,
            "uploaded_at": photo.uploaded_at,
            "caption": photo.caption,
            "is_primary": is_primary,
        }
    )


@router.get("/", response_model=list[PhotoRead])
async def list_photos(
    plant_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo)
        .where(Photo.plant_id == plant_id)
        .order_by(desc(Photo.uploaded_at))
        .limit(limit)
        .offset(offset)
        .options(joinedload(Photo.uploaded_by_user))
    )
    photos = result.scalars().all()
    plant_result = await db.execute(
        select(Plant.primary_photo_id).where(Plant.id == plant_id)
    )
    primary_id = plant_result.scalar()
    photos_read = []
    for photo in photos:
        original_url = f"/api/plants/{plant_id}/photos/{photo.id}/file"
        thumbnail_url = f"/api/plants/{plant_id}/photos/{photo.id}/thumbnail"
        is_primary = photo.id == primary_id
        photos_read.append(
            PhotoRead.model_validate(
                {
                    "id": photo.id,
                    "plant_id": photo.plant_id,
                    "original_url": original_url,
                    "thumbnail_url": thumbnail_url,
                    "uploaded_by": photo.uploaded_by_user.username,
                    "uploaded_at": photo.uploaded_at,
                    "caption": photo.caption,
                    "is_primary": is_primary,
                }
            )
        )
    return photos_read


@router.post("/{photo_id}/set-primary", response_model=PhotoRead)
async def set_primary_photo(
    plant_id: int,
    photo_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo)
        .where(Photo.id == photo_id, Photo.plant_id == plant_id)
        .options(joinedload(Photo.uploaded_by_user))
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Update plant
    plant = await db.get(Plant, plant_id)
    plant.primary_photo_id = photo.id
    await db.commit()

    # Return PhotoRead
    original_url = f"/api/plants/{plant_id}/photos/{photo.id}/file"
    thumbnail_url = f"/api/plants/{plant_id}/photos/{photo.id}/thumbnail"
    return PhotoRead.model_validate(
        {
            "id": photo.id,
            "plant_id": photo.plant_id,
            "original_url": original_url,
            "thumbnail_url": thumbnail_url,
            "uploaded_by": photo.uploaded_by_user.username,
            "uploaded_at": photo.uploaded_at,
            "caption": photo.caption,
            "is_primary": True,
        }
    )


@router.get("/{photo_id}/file")
async def serve_original(
    plant_id: int,
    photo_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.plant_id == plant_id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = Path(PHOTO_STORAGE_PATH) / photo.original_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    content_type = get_content_type(str(file_path))
    return FileResponse(file_path, media_type=content_type)


@router.get("/{photo_id}/thumbnail")
async def serve_thumbnail(
    plant_id: int,
    photo_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.plant_id == plant_id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = Path(PHOTO_STORAGE_PATH) / photo.thumbnail_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, media_type="image/jpeg")


# Flat router for non-plant-scoped photo endpoints
flat_router = APIRouter(prefix="/photos", tags=["photos"])


@flat_router.delete("/{photo_id}", status_code=204)
async def delete_photo(
    photo_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    plant_id = photo.plant_id

    # Check if primary and null it
    plant = await db.get(Plant, plant_id)
    if plant and plant.primary_photo_id == photo.id:
        plant.primary_photo_id = None

    # Delete files from disk (best-effort per PRD: DB record removed regardless)
    original_full = Path(PHOTO_STORAGE_PATH) / photo.original_path
    thumbnail_full = Path(PHOTO_STORAGE_PATH) / photo.thumbnail_path
    try:
        original_full.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        thumbnail_full.unlink(missing_ok=True)
    except OSError:
        pass

    # Delete DB record
    await db.delete(photo)
    await db.commit()
    return Response(status_code=204)
