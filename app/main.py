import asyncio
from contextlib import asynccontextmanager
import os
from datetime import datetime, timezone, timedelta
from email.utils import formatdate, parsedate_to_datetime

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.auth import get_current_user
from app.database import get_db
from app.models import Plant, Task, User
from app.routers import activity, photos, plants, tasks, users
from app.schemas import TaskDueRead


def _ensure_tz(dt: datetime) -> datetime:
    """If dt is offset-naive, assume UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@asynccontextmanager
async def lifespan(app: FastAPI):
    import subprocess

    subprocess.run(["alembic", "upgrade", "head"], check=True)
    from app.background import nightly_maintenance
    from app.database import async_session

    task = asyncio.create_task(nightly_maintenance(async_session))
    yield
    task.cancel()


app = FastAPI(title="Sprout", version="0.1.0", lifespan=lifespan)


# Redirect unauthenticated browser requests to /login
class AuthRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if response.status_code == 401 and "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(url="/login", status_code=302)
        return response


app.add_middleware(AuthRedirectMiddleware)

# Static files (CSS) — no auth required
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include routers (API routes under /api prefix)
app.include_router(users.users_router, prefix="/api")
app.include_router(users.auth_router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(tasks.flat_router, prefix="/api")
app.include_router(plants.router, prefix="/api")
app.include_router(photos.router, prefix="/api")
app.include_router(photos.flat_router, prefix="/api")
app.include_router(activity.router, prefix="/api")


# Global /tasks/due endpoint (not scoped under /plants/{plant_id})
@app.get("/api/tasks/due")
async def list_due_tasks(
    request: Request,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Task, Plant)
        .join(Plant)
        .where(
            Task.is_active == True,
            Plant.archived == False,
            Task.due_date <= now,
        )
        .order_by(Task.due_date)
    )
    rows = result.all()
    due_tasks = []
    latest = now
    for t, p in rows:
        dd = _ensure_tz(t.due_date)
        days = max(0, (now - dd).days)
        due_tasks.append(
            TaskDueRead(
                task_id=t.id,
                plant_id=p.id,
                plant_name=p.name,
                location=p.location,
                type=t.type,
                label=t.label,
                due_date=dd,
                days_overdue=days,
            )
        )
        if dd > latest:
            latest = dd
    if not rows:
        latest = now
    lm = formatdate(latest.timestamp(), usegmt=True)
    ims = request.headers.get("If-Modified-Since")
    if ims:
        if parsedate_to_datetime(ims) >= latest:
            return Response(status_code=304)
    return JSONResponse(
        content=[t.model_dump(mode="json") for t in due_tasks],
        headers={"Last-Modified": lm},
    )


@app.get("/api/tasks/upcoming")
async def list_upcoming_tasks(
    request: Request,
    days: int = 3,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days)
    result = await db.execute(
        select(Task, Plant)
        .join(Plant)
        .where(
            Task.is_active == True,
            Plant.archived == False,
            Task.due_date <= horizon,
        )
        .order_by(Task.due_date)
    )
    rows = result.all()
    upcoming_tasks = []
    latest = now
    for t, p in rows:
        dd = _ensure_tz(t.due_date)
        delta = (dd - now).days
        days_until = max(0, -delta) if delta < 0 else delta
        upcoming_tasks.append(
            TaskDueRead(
                task_id=t.id,
                plant_id=p.id,
                plant_name=p.name,
                location=p.location,
                type=t.type,
                label=t.label,
                due_date=dd,
                days_overdue=max(0, -delta),
            )
        )
        if dd > latest:
            latest = dd
    if not rows:
        latest = now
    lm = formatdate(latest.timestamp(), usegmt=True)
    ims = request.headers.get("If-Modified-Since")
    if ims:
        if parsedate_to_datetime(ims) >= latest:
            return Response(status_code=304)
    return JSONResponse(
        content=[t.model_dump(mode="json") for t in upcoming_tasks],
        headers={"Last-Modified": lm},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# --- HTML Page Routes ---


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


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
            dd = _ensure_tz(next_task.due_date)
            days_overdue = max(0, (now - dd).days)
            entry["next_task"] = {
                "type": next_task.type,
                "label": next_task.label,
                "due_date": dd.isoformat(),
                "days_overdue": days_overdue,
                "interval_days": next_task.interval_days,
            }
        plant_data.append(entry)

    return templates.TemplateResponse(request, "dashboard.html", {"plants": plant_data})


@app.get("/archive")
async def archive_page(request: Request, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Plant)
        .options(selectinload(Plant.photos))
        .where(Plant.archived == True)
        .order_by(Plant.archived_at.desc())
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

    return templates.TemplateResponse(request, "archive.html", {"plants": plant_data})


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
        dd = _ensure_tz(t.due_date)
        days_overdue = max(0, (now - dd).days)
        tasks_list.append({
            "id": t.id,
            "type": t.type,
            "label": t.label,
            "interval_days": t.interval_days,
            "due_date": dd.isoformat(),
            "is_overdue": dd < now,
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
        request, "plant_detail.html",
        {
            "plant": plant_data,
            "tasks": tasks_list,
            "photos": photos_list,
            "activity": activity_list,
        },
    )


# --- Upcoming Tasks / Calendar View ---


@app.get("/tasks")
async def upcoming_tasks_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """HTML page showing upcoming and overdue tasks grouped by date."""
    now = datetime.now(timezone.utc)

    # Fetch upcoming tasks (next 30 days)
    horizon = now + timedelta(days=30)
    result = await db.execute(
        select(Task, Plant)
        .join(Plant)
        .where(
            Task.is_active == True,
            Plant.archived == False,
            Task.due_date <= horizon,
        )
        .order_by(Task.due_date, Plant.name)
    )
    rows = result.all()

    tasks_data = []
    for t, p in rows:
        dd = _ensure_tz(t.due_date)
        tasks_data.append({
            "id": t.id,
            "plant_id": p.id,
            "plant_name": p.name,
            "type": t.type,
            "label": t.label,
            "interval_days": t.interval_days,
            "due_date": dd.isoformat(),
            "days_overdue": max(0, (now - dd).days),
            "is_overdue": dd < now,
        })

    return templates.TemplateResponse(request, "upcoming_tasks.html", {"tasks": tasks_data})