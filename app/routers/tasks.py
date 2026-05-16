from datetime import datetime, timezone, timedelta
from email.utils import formatdate, parsedate_to_datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.auth import get_current_user
from app.database import get_db
from app.dependencies import form_or_json
from app.models import Plant, Task, User
from app.schemas import TaskComplete, TaskCreate, TaskDueRead, TaskRead, TaskUpdate

router = APIRouter(prefix="/plants/{plant_id}/tasks", tags=["tasks"])
flat_router = APIRouter(prefix="/tasks", tags=["tasks"])
api_router = APIRouter(prefix="/tasks", tags=["tasks"])


def _ensure_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# --- Plant-scoped routes ---

@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    plant_id: int,
    task: TaskCreate = Depends(form_or_json(TaskCreate)),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    new_task = Task(
        plant_id=plant_id,
        type=task.type,
        label=task.label,
        interval_days=task.interval_days,
        due_date=task.due_date,
        notes=task.notes,
        created_by=current_user.id,
        is_active=True,
    )
    db.add(new_task)
    await db.flush()
    await db.refresh(new_task)
    return TaskRead.model_validate(new_task)


@router.get("/", response_model=list[TaskRead])
async def list_tasks(
    plant_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(Task)
        .where(Task.plant_id == plant_id)
        .order_by(Task.due_date)
    )
    tasks = result.scalars().all()
    return [TaskRead.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    plant_id: int,
    task_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.plant_id == plant_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return TaskRead.model_validate(task)


def _apply_task_completion(task: Task, body: TaskComplete, current_user: User) -> Task:
    now = datetime.now(timezone.utc)
    task.last_completed_at = now
    task.last_completed_by = current_user.id
    if body.notes:
        if task.notes:
            task.notes += "\n" + body.notes
        else:
            task.notes = body.notes
    if body.advance:
        if task.interval_days is not None:
            if body.next_due_date:
                task.due_date = body.next_due_date
            else:
                task.due_date += timedelta(days=task.interval_days)
        else:
            task.is_active = False
    task.updated_at = now
    return task


# --- Flat routes (not scoped under /plants/{plant_id}) ---


@flat_router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    update_data = task_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
    task.updated_at = datetime.now(timezone.utc)
    return TaskRead.model_validate(task)


@flat_router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    await db.delete(task)


@flat_router.post("/{task_id}/complete", response_model=TaskRead)
async def complete_task(
    task_id: int,
    body: TaskComplete = Depends(form_or_json(TaskComplete)),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    _apply_task_completion(task, body, current_user)
    return TaskRead.model_validate(task)


# Scoped complete route — fixes the frontend bug (plant_detail.html uses this URL)
@router.post("/{task_id}/complete", response_model=TaskRead)
async def complete_task_scoped(
    plant_id: int,
    task_id: int,
    body: TaskComplete = Depends(form_or_json(TaskComplete)),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.plant_id == plant_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    _apply_task_completion(task, body, current_user)
    return TaskRead.model_validate(task)


# --- Global task endpoints (moved from main.py) ---


@api_router.get("/due")
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


@api_router.get("/upcoming")
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
