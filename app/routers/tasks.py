from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.auth import get_current_user
from app.database import get_db
from app.models import Plant, Task, User
from app.schemas import TaskComplete, TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/plants/{plant_id}/tasks", tags=["tasks"])
flat_router = APIRouter(prefix="/tasks", tags=["tasks"])


# --- Plant-scoped routes ---

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
    body: TaskComplete,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
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
    if body.advance:
        if task.interval_days is not None:
            # Recurring task: advance the due date
            if body.next_due_date:
                task.due_date = body.next_due_date
            else:
                task.due_date += timedelta(days=task.interval_days)
        else:
            # One-shot task consumed
            task.is_active = False
    # If advance=False: no date change, task stays active as-is
    task.updated_at = now
    return TaskRead.model_validate(task)
