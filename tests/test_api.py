"""API integration tests — full CRUD flows against an in-memory database."""

import os
import asyncio
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Point at in-memory SQLite before any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-for-testing-only"

from app.database import get_db, engine as real_engine
from app.models import Base
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@asynccontextmanager
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with setup_db():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def auth_client(client):
    """Client with a user created and authenticated."""
    from app.auth import get_password_hash

    async with TestSession() as db:
        from app.models import User

        user = User(username="testuser", display_name="Test", hashed_password=get_password_hash("pass123"))
        db.add(user)
        await db.commit()

    resp = await client.post(
        "/api/auth/token",
        data={"username": "testuser", "password": "pass123"},
    )
    assert resp.status_code == 200
    client.cookies.set("token", resp.json()["access_token"])
    return client


# --- Auth ---


@pytest.mark.asyncio
async def test_login(auth_client):
    resp = await auth_client.get("/api/users/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"


@pytest.mark.asyncio
async def test_login_bad_password(auth_client):
    resp = await auth_client.post(
        "/api/auth/token",
        data={"username": "testuser", "password": "wrongpass"},
    )
    assert resp.status_code == 401


# --- Health ---


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# --- Plants CRUD ---


@pytest.mark.asyncio
async def test_create_plant(auth_client):
    resp = await auth_client.post(
        "/api/plants/",
        json={"name": "Monstera", "species": "Monstera deliciosa", "location": "Living room"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Monstera"


@pytest.mark.asyncio
async def test_list_plants(auth_client):
    await auth_client.post("/api/plants/", json={"name": "Plant 1"})
    await auth_client.post("/api/plants/", json={"name": "Plant 2"})
    resp = await auth_client.get("/api/plants/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_plant(auth_client):
    create = await auth_client.post("/api/plants/", json={"name": "Fern"})
    plant_id = create.json()["id"]
    resp = await auth_client.get(f"/api/plants/{plant_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Fern"


@pytest.mark.asyncio
async def test_update_plant(auth_client):
    create = await auth_client.post("/api/plants/", json={"name": "Fern", "location": "Kitchen"})
    plant_id = create.json()["id"]
    resp = await auth_client.put(f"/api/plants/{plant_id}", json={"location": "Bathroom"})
    assert resp.status_code == 200
    assert resp.json()["location"] == "Bathroom"


@pytest.mark.asyncio
async def test_archive_plant(auth_client):
    create = await auth_client.post("/api/plants/", json={"name": "Dead plant"})
    plant_id = create.json()["id"]
    resp = await auth_client.post(f"/api/plants/{plant_id}/archive", json={})
    assert resp.status_code == 200
    assert resp.json()["archived"] is True


@pytest.mark.asyncio
async def test_delete_plant(auth_client):
    create = await auth_client.post("/api/plants/", json={"name": "Goner"})
    plant_id = create.json()["id"]
    resp = await auth_client.delete(f"/api/plants/{plant_id}")
    assert resp.status_code == 204
    resp = await auth_client.get(f"/api/plants/{plant_id}")
    assert resp.status_code == 404


# --- Tasks ---


@pytest.mark.asyncio
async def test_create_task(auth_client):
    plant = await auth_client.post("/api/plants/", json={"name": "Aloe"})
    plant_id = plant.json()["id"]
    resp = await auth_client.post(
        f"/api/plants/{plant_id}/tasks/",
        json={"type": "water", "label": "Weekly water", "interval_days": 7, "due_date": "2026-05-03"},
    )
    assert resp.status_code == 201
    assert resp.json()["type"] == "water"


@pytest.mark.asyncio
async def test_complete_task(auth_client):
    plant = await auth_client.post("/api/plants/", json={"name": "Cactus"})
    plant_id = plant.json()["id"]
    task = await auth_client.post(
        f"/api/plants/{plant_id}/tasks/",
        json={"type": "water", "label": "Water", "interval_days": 7, "due_date": "2026-05-01"},
    )
    task_id = task.json()["id"]
    resp = await auth_client.post(f"/api/tasks/{task_id}/complete", json={})
    assert resp.status_code == 200
    # Recurring task should advance due_date by 7 days
    data = resp.json()
    assert data["due_date"] > "2026-05-01"


# --- Activity ---


@pytest.mark.asyncio
async def test_add_activity(auth_client):
    plant = await auth_client.post("/api/plants/", json={"name": "Basil"})
    plant_id = plant.json()["id"]
    resp = await auth_client.post(
        f"/api/plants/{plant_id}/activity/",
        json={"content": "Repotted into a bigger pot"},
    )
    assert resp.status_code == 201
    assert "bigger pot" in resp.json()["content"]


@pytest.mark.asyncio
async def test_list_activity(auth_client):
    plant = await auth_client.post("/api/plants/", json={"name": "Mint"})
    plant_id = plant.json()["id"]
    await auth_client.post(f"/api/plants/{plant_id}/activity/", json={"content": "Note 1"})
    await auth_client.post(f"/api/plants/{plant_id}/activity/", json={"content": "Note 2"})
    resp = await auth_client.get(f"/api/plants/{plant_id}/activity/")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- Due tasks endpoint ---


@pytest.mark.asyncio
async def test_due_tasks_empty(auth_client):
    resp = await auth_client.get("/api/tasks/due")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_due_tasks(auth_client):
    plant = await auth_client.post("/api/plants/", json={"name": "Thyme"})
    plant_id = plant.json()["id"]
    # Create a task due today (should show up in due tasks)
    await auth_client.post(
        f"/api/plants/{plant_id}/tasks/",
        json={"type": "water", "label": "Water", "interval_days": 7, "due_date": "2026-05-02"},
    )
    resp = await auth_client.get("/api/tasks/due")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["plant_name"] == "Thyme"


# --- Page routes ---


@pytest.mark.asyncio
async def test_login_page(client):
    resp = await client.get("/login")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client):
    resp = await client.get("/")
    assert resp.status_code in (401, 403, 307)  # redirect or forbidden


@pytest.mark.asyncio
async def test_dashboard(auth_client):
    resp = await auth_client.get("/")
    assert resp.status_code == 200
