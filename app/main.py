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

# Include routers
app.include_router(users.users_router)
app.include_router(users.auth_router)
app.include_router(tasks.router)
app.include_router(plants.router)
app.include_router(photos.router)
app.include_router(activity.router)


# Global /tasks/due endpoint (not scoped under /plants/{plant_id})
@app.get("/tasks/due")
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
