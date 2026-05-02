async def nightly_maintenance(db_session_factory):
    """Single asyncio background task that runs nightly at 02:00 UTC."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import text

    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())

        async with db_session_factory() as db:
            # 1. Deactivate tasks for archived plants
            await db.execute(
                text("UPDATE tasks SET is_active = false "
                     "WHERE plant_id IN (SELECT id FROM plants WHERE archived = true) "
                     "AND is_active = true")
            )
            # 2. Prune expired revoked tokens
            await db.execute(
                text("DELETE FROM revoked_tokens WHERE expires_at < :now"),
                {"now": datetime.now(timezone.utc)}
            )
            await db.commit()
