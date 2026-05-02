from datetime import datetime, timezone, timedelta
from email.utils import formatdate, parsedate_to_datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.auth import get_current_user
from app.database import get_db
from app.models import Plant, Task, User
from app.schemas import TaskComplete, TaskCreate, TaskDueRead, TaskRead, TaskUpdate

router = APIRouter(prefix="/plants/{plant_id}/tasks", tags=["tasks"])


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    plant_id: int,
    task: TaskCreate,
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
    return TaskRead.model_validate(new_task)


@router.get("/", response_model=list[TaskRead])
async def list_tasks(
    plant_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(Task)
        .where(Task.plant_id == plant_id, Task.is_active == True)
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


@router.put("/{task_id}", response_model=TaskRead)
async def update_task(
    plant_id: int,
    task_id: int,
    task_update: TaskUpdate,
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
    update_data = task_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
    task.updated_at = datetime.now(timezone.utc)
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
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
    task.is_active = False
    task.updated_at = datetime.now(timezone.utc)


@router.post("/{task_id}/complete", response_model=TaskRead)
async def complete_task(
    plant_id: int,
    task_id: int,
    body: TaskComplete,
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
    now = datetime.now(timezone.utc)
    task.last_completed_at = now
    task.last_completed_by = current_user.id
    if body.notes:
        if task.notes:
            task.notes += "\n" + body.notes
        else:
            task.notes = body.notes
    if body.advance and task.interval_days is not None:
        if body.next_due_date:
            task.due_date = body.next_due_date
        else:
            task.due_date += timedelta(days=task.interval_days)
    else:
        task.is_active = False
    task.updated_at = now
    return TaskRead.model_validate(task)


@router.get("/due")
async def list_due_tasks(
    request: Request,
    plant_id: int,  # ignored
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    now = datetime.now(timezone.utc)
    seven_days_later = now + timedelta(days=7)
    result = await db.execute(
        select(Task, Plant)
        .join(Plant)
        .where(
            Task.is_active == True,
            Plant.archived == False,
            Task.due_date <= seven_days_later,
        )
        .order_by(Task.due_date)
    )
    tasks_plants = result.all()
    due_tasks = []
    latest_due_date = now
    for task, plant in tasks_plants:
        days_overdue = max(0, (now - task.due_date).days)
        due_task = TaskDueRead(
            task_id=task.id,
            plant_id=plant.id,
            plant_name=plant.name,
            location=plant.location,
            type=task.type,
            label=task.label,
            due_date=task.due_date,
            days_overdue=days_overdue,
        )
        due_tasks.append(due_task)
        if task.due_date > latest_due_date:
            latest_due_date = task.due_date
    if not tasks_plants:
        latest_due_date = now
    last_modified = formatdate(latest_due_date.timestamp(), usegmt=True)
    if_modified_since = request.headers.get("If-Modified-Since")
    if if_modified_since:
        if_modified_datetime = parsedate_to_datetime(if_modified_since)
        if latest_due_date <= if_modified_datetime:
            return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    return JSONResponse(
        content=[due_task.model_dump() for due_task in due_tasks],
        headers={"Last-Modified": last_modified},
    )
