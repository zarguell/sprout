from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.utils import formatdate, parsedate_to_datetime

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.auth import get_current_user
from app.database import get_db
from app.models import Plant, Task, User
from app.routers import activity, photos, plants, tasks, users
from app.schemas import TaskDueRead


@asynccontextmanager
async def lifespan(app: FastAPI):
    import subprocess

    subprocess.run(["alembic", "upgrade", "head"], check=True)
    from app.tasks_scheduler import start_scheduler

    scheduler = start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="Sprout", version="0.1.0", lifespan=lifespan)

# Static files (CSS) — no auth required
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include routers (API routes under /api prefix)
app.include_router(users.users_router, prefix="/api")
app.include_router(users.auth_router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(plants.router, prefix="/api")
app.include_router(photos.router, prefix="/api")
app.include_router(activity.router, prefix="/api")


# Global /tasks/due endpoint (not scoped under /plants/{plant_id})
@app.get("/api/tasks/due")
async def list_due_tasks(
    request: Request,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    now = datetime.now(timezone.utc)
    seven_days = now + timedelta(days=7)
    result = await db.execute(
        select(Task, Plant)
        .join(Plant)
        .where(
            Task.is_active == True,
            Plant.archived == False,
            Task.due_date <= seven_days,
        )
        .order_by(Task.due_date)
    )
    rows = result.all()
    due_tasks = []
    latest = now
    for t, p in rows:
        days = max(0, (now - t.due_date).days)
        due_tasks.append(
            TaskDueRead(
                task_id=t.id,
                plant_id=p.id,
                plant_name=p.name,
                location=p.location,
                type=t.type,
                label=t.label,
                due_date=t.due_date,
                days_overdue=days,
            )
        )
        if t.due_date > latest:
            latest = t.due_date
    if not rows:
        latest = now
    lm = formatdate(latest.timestamp(), usegmt=True)
    ims = request.headers.get("If-Modified-Since")
    if ims:
        if parsedate_to_datetime(ims) >= latest:
            return Response(status_code=304)
    return JSONResponse(
        content=[t.model_dump() for t in due_tasks],
        headers={"Last-Modified": lm},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# --- HTML Page Routes ---


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/")
async def dashboard_page(request: Request, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    from sqlalchemy.orm import selectinload

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Plant)
        .options(selectinload(Plant.photos))
        .where(Plant.archived == False)
        .order_by(Plant.name)
    )
    plants = result.scalars().unique().all()

    plant_data = []
    for p in plants:
        thumbnail_url = None
        for photo in p.photos:
            if photo.is_primary:
                thumbnail_url = f"/api/plants/{p.id}/photos/{photo.id}/thumbnail"
                break
        if not thumbnail_url and p.photos:
            thumbnail_url = f"/api/plants/{p.id}/photos/{p.photos[0].id}/thumbnail"

        # Get next due task
        task_result = await db.execute(
            select(Task)
            .where(Task.plant_id == p.id, Task.is_active == True)
            .order_by(Task.due_date)
            .limit(1)
        )
        next_task = task_result.scalar_one_or_none()

        entry = {
            "id": p.id,
            "name": p.name,
            "species": p.species,
            "location": p.location,
            "thumbnail_url": thumbnail_url,
            "next_task": None,
        }
        if next_task:
            days_overdue = max(0, (now - next_task.due_date).days)
            entry["next_task"] = {
                "type": next_task.type,
                "label": next_task.label,
                "due_date": next_task.due_date.isoformat(),
                "days_overdue": days_overdue,
            }
        plant_data.append(entry)

    return templates.TemplateResponse("dashboard.html", {"request": request, "plants": plant_data})


@app.get("/archive")
async def archive_page(request: Request, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Plant)
        .options(selectinload(Plant.photos))
        .where(Plant.archived == True)
        .order_by(Plant.name)
    )
    plants = result.scalars().unique().all()

    plant_data = []
    for p in plants:
        thumbnail_url = None
        for photo in p.photos:
            if photo.is_primary:
                thumbnail_url = f"/api/plants/{p.id}/photos/{photo.id}/thumbnail"
                break
        if not thumbnail_url and p.photos:
            thumbnail_url = f"/api/plants/{p.id}/photos/{p.photos[0].id}/thumbnail"

        plant_data.append({
            "id": p.id,
            "name": p.name,
            "species": p.species,
            "location": p.location,
            "thumbnail_url": thumbnail_url,
        })

    return templates.TemplateResponse("archive.html", {"request": request, "plants": plant_data})


@app.get("/plants/{plant_id}")
async def plant_detail_page(
    plant_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    from sqlalchemy.orm import selectinload

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Plant).options(selectinload(Plant.photos)).where(Plant.id == plant_id)
    )
    plant = result.scalar_one_or_none()
    if not plant:
        return JSONResponse(status_code=404, content={"detail": "Plant not found"})

    # Tasks
    task_result = await db.execute(
        select(Task)
        .where(Task.plant_id == plant_id, Task.is_active == True)
        .order_by(Task.due_date)
    )
    tasks_list = []
    for t in task_result.scalars().all():
        days_overdue = max(0, (now - t.due_date).days)
        tasks_list.append({
            "id": t.id,
            "type": t.type,
            "label": t.label,
            "interval_days": t.interval_days,
            "due_date": t.due_date.isoformat(),
            "is_overdue": t.due_date < now,
            "days_overdue": days_overdue,
        })

    # Photos
    photos_list = []
    for ph in plant.photos:
        photos_list.append({
            "id": ph.id,
            "thumbnail_url": f"/api/plants/{plant_id}/photos/{ph.id}/thumbnail",
            "file_url": f"/api/plants/{plant_id}/photos/{ph.id}/file",
            "caption": ph.caption,
            "is_primary": ph.is_primary,
        })

    # Activity
    from app.models import PlantActivity

    act_result = await db.execute(
        select(PlantActivity)
        .where(PlantActivity.plant_id == plant_id)
        .order_by(PlantActivity.created_at.desc())
        .limit(50)
    )
    activity_list = []
    for a in act_result.scalars().all():
        activity_list.append({
            "id": a.id,
            "content": a.content,
            "created_at": a.created_at.isoformat(),
            "user": {"username": "user", "display_name": "User"},
        })

    plant_data = {
        "id": plant.id,
        "name": plant.name,
        "species": plant.species,
        "location": plant.location,
        "notes": plant.notes,
        "archived": plant.archived,
        "archived_at": plant.archived_at.isoformat() if plant.archived_at else None,
        "archive_reason": plant.archive_reason,
    }

    return templates.TemplateResponse(
        "plant_detail.html",
        {
            "request": request,
            "plant": plant_data,
            "tasks": tasks_list,
            "photos": photos_list,
            "activity": activity_list,
        },
    )
