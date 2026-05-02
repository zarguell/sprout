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


# --- Form data submission tests (UI sends URLSearchParams, not JSON) ---


@pytest.mark.asyncio
async def test_create_plant_via_form_data(auth_client):
    """Dashboard / plant_detail HTML forms send URLSearchParams (form-encoded), not JSON.
    This test reproduces what the frontend actually does."""
    resp = await auth_client.post(
        "/api/plants/",
        data={"name": "Monstera", "species": "Monstera deliciosa", "location": "Living room"},
    )
    assert resp.status_code == 201, f"Form data POST /api/plants/ got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["name"] == "Monstera"
    assert data["species"] == "Monstera deliciosa"
    assert data["location"] == "Living room"


@pytest.mark.asyncio
async def test_create_plant_via_form_data_minimal(auth_client):
    """Minimal form data — only required fields."""
    resp = await auth_client.post(
        "/api/plants/",
        data={"name": "Snake Plant"},
    )
    assert resp.status_code == 201, f"Minimal form data got {resp.status_code}: {resp.text}"
    assert resp.json()["name"] == "Snake Plant"


@pytest.mark.asyncio
async def test_update_plant_via_form_data(auth_client):
    """plant_detail.html saveEdit() sends PUT with URLSearchParams."""
    # Create via JSON
    create = await auth_client.post("/api/plants/", json={"name": "Pothos"})
    pid = create.json()["id"]

    # Update via form data (as the frontend does)
    resp = await auth_client.put(
        f"/api/plants/{pid}",
        data={"name": "Golden Pothos", "location": "Kitchen shelf"},
    )
    assert resp.status_code == 200, f"Form data PUT /api/plants/{pid} got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["name"] == "Golden Pothos"
    assert data["location"] == "Kitchen shelf"


@pytest.mark.asyncio
async def test_archive_plant_via_form_data(auth_client):
    """plant_detail.html archivePlant() sends POST with URLSearchParams."""
    create = await auth_client.post("/api/plants/", json={"name": "To Archive"})
    pid = create.json()["id"]

    resp = await auth_client.post(
        f"/api/plants/{pid}/archive",
        data={"reason": "Outgrew the shelf"},
    )
    assert resp.status_code == 200, f"Form data archive got {resp.status_code}: {resp.text}"
    assert resp.json()["archived"] is True


@pytest.mark.asyncio
async def test_create_task_via_form_data(auth_client):
    """plant_detail.html addTask() sends POST with URLSearchParams."""
    create = await auth_client.post("/api/plants/", json={"name": "Plant for Tasks"})
    pid = create.json()["id"]

    resp = await auth_client.post(
        f"/api/plants/{pid}/tasks/",
        data={"type": "water", "label": "Water me", "interval_days": "7", "due_date": "2026-06-01"},
    )
    assert resp.status_code == 201, f"Form data create task got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["type"] == "water"
    assert data["label"] == "Water me"


@pytest.mark.asyncio
async def test_complete_task_via_post(auth_client):
    """plant_detail.html completeTask() sends POST with no body (empty)."""
    create = await auth_client.post("/api/plants/", json={"name": "Plant for Complete"})
    pid = create.json()["id"]

    task_resp = await auth_client.post(
        f"/api/plants/{pid}/tasks/",
        json={"type": "water", "label": "Water", "interval_days": 7, "due_date": "2026-06-01"},
    )
    tid = task_resp.json()["id"]

    # Empty POST (as the frontend does)
    resp = await auth_client.post(f"/api/tasks/{tid}/complete")
    assert resp.status_code == 200, f"Empty POST complete task got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["last_completed_at"] is not None


@pytest.mark.asyncio
async def test_add_activity_via_form_data(auth_client):
    """plant_detail.html addNote() sends POST with URLSearchParams."""
    create = await auth_client.post("/api/plants/", json={"name": "Plant for Activity"})
    pid = create.json()["id"]

    resp = await auth_client.post(
        f"/api/plants/{pid}/activity/",
        data={"content": "Watered and looked great!"},
    )
    assert resp.status_code == 201, f"Form data activity got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["content"] == "Watered and looked great!"


# --- Timezone safety ---


@pytest.mark.asyncio
async def test_plant_detail_with_naive_dates(auth_client):
    """Regression: plant_detail_page must handle offset-naive due_date from SQLite."""
    plant = await auth_client.post("/api/plants/", json={"name": "TZ Test"})
    pid = plant.json()["id"]
    # Create a task with a naive datetime (as SQLite stores it)
    resp = await auth_client.post(
        f"/api/plants/{pid}/tasks/",
        json={"type": "water", "label": "TZ test", "interval_days": 7, "due_date": "2026-05-01"},
    )
    assert resp.status_code == 201
    # Hit the HTML page route — this was crashing with 500
    resp = await auth_client.get(f"/plants/{pid}")
    assert resp.status_code == 200, f"plant_detail_page got {resp.status_code}: {resp.text[:200]}"


@pytest.mark.asyncio
async def test_dashboard_with_naive_dates(auth_client):
    """Regression: dashboard_page must handle offset-naive due_date from SQLite."""
    plant = await auth_client.post("/api/plants/", json={"name": "Dashboard TZ"})
    pid = plant.json()["id"]
    await auth_client.post(
        f"/api/plants/{pid}/tasks/",
        json={"type": "water", "label": "Dashboard task", "interval_days": 7, "due_date": "2026-05-01"},
    )
    resp = await auth_client.get("/")
    assert resp.status_code == 200, f"dashboard got {resp.status_code}: {resp.text[:200]}"


# --- Upcoming tasks endpoint ---


@pytest.mark.asyncio
async def test_upcoming_tasks_endpoint(auth_client):
    plant = await auth_client.post("/api/plants/", json={"name": "Upcoming Plant"})
    pid = plant.json()["id"]
    # Task due today
    await auth_client.post(
        f"/api/plants/{pid}/tasks/",
        json={"type": "water", "label": "Today task", "interval_days": 7, "due_date": "2026-05-02"},
    )
    # Task due in future
    await auth_client.post(
        f"/api/plants/{pid}/tasks/",
        json={"type": "fertilize", "label": "Future task", "due_date": "2026-05-10"},
    )
    resp = await auth_client.get("/api/tasks/upcoming?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["plant_name"] == "Upcoming Plant"


@pytest.mark.asyncio
async def test_upcoming_tasks_page_route(auth_client):
    """The upcoming tasks HTML page at /tasks should render."""
    plant = await auth_client.post("/api/plants/", json={"name": "Page Test"})
    pid = plant.json()["id"]
    await auth_client.post(
        f"/api/plants/{pid}/tasks/",
        json={"type": "water", "due_date": "2026-05-05"},
    )
    resp = await auth_client.get("/tasks")
    assert resp.status_code == 200, f"/tasks page got {resp.status_code}: {resp.text[:200]}"
    assert "upcoming" in resp.text.lower() or "tasks" in resp.text.lower()


@pytest.mark.asyncio
async def test_upcoming_tasks_days_param(auth_client):
    """Verify the days query parameter limits scope."""
    plant = await auth_client.post("/api/plants/", json={"name": "Far Future"})
    pid = plant.json()["id"]
    await auth_client.post(
        f"/api/plants/{pid}/tasks/",
        json={"type": "water", "due_date": "2026-08-01"},
    )
    # With days=1, this should not appear
    resp = await auth_client.get("/api/tasks/upcoming?days=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 0
