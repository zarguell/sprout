import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import async_session
from app.models import Plant, Task

logger = logging.getLogger(__name__)


async def generate_due_tasks() -> list[dict]:
    async with async_session() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Task, Plant)
            .join(Plant)
            .where(Task.is_active == True, Plant.archived == False, Task.due_date <= now)
            .order_by(Task.due_date)
        )
        tasks_plants = result.all()
        due_tasks = []
        for t, p in tasks_plants:
            days_overdue = max(0, (now - t.due_date).days)
            due_tasks.append({
                "task_id": t.id,
                "plant_id": p.id,
                "plant_name": p.name,
                "location": p.location,
                "type": t.type,
                "label": t.label,
                "due_date": t.due_date,
                "days_overdue": days_overdue,
            })
        return due_tasks


async def run_scheduled_check():
    due_tasks = await generate_due_tasks()
    logger.info(f"Scheduled check: {len(due_tasks)} tasks are due")


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_scheduled_check, "interval", minutes=60, id="due_task_check")
    scheduler.start()
    return scheduler
