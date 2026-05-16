"""Comprehensive test gap coverage for Sprout.

Tests code paths and edge cases missed by test_api.py.
Uses shared conftest infrastructure for DB and fixtures.

Covers:
- Auth edge cases (bad passwords, expired tokens, missing tokens)
- User profile (GET, PUT)
- Plant error cases (404s, validation, location filter)
- Task recurrence, advance, one-shot consumption
- Photo upload, set-primary, delete, promotion
- Activity validation
- Upcoming tasks edge cases
- Archive page rendering
- Photo file serving (404s)
- Health check

NOTE: All list/create endpoints use trailing slashes (e.g., POST /api/plants/)
because Starlette's redirect_slashes=True redirects /api/plants → /api/plants/
with a 307, which the httpx test client follows transparently.
"""
import pytest
import pytest_asyncio
from fastapi import status
from io import BytesIO

from test_shared import TestSession
from app.auth import create_access_token, get_password_hash
from app.models import Plant, Task, User


@pytest_asyncio.fixture
async def auth_client(client):
    """Client with a user created and authenticated."""
    async with TestSession() as db:
        user = User(
            username="gaptest", display_name="Gap Test",
            hashed_password=get_password_hash("pass123"),
        )
        db.add(user)
        await db.commit()

    resp = await client.post(
        "/api/auth/token",
        data={"username": "gaptest", "password": "pass123"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code}: {resp.text}"
    token = resp.json()["access_token"]
    client.cookies.set("token", token)
    return client


@pytest_asyncio.fixture
async def test_plant(auth_client):
    """Create a test plant via API. Uses trailing slash to avoid 307 redirect."""
    resp = await auth_client.post(
        "/api/plants/",
        json={"name": "Gap Test Plant", "species": "Testus", "location": "lab"},
    )
    assert resp.status_code == 201, (
        f"Plant creation failed: {resp.status_code}: {resp.text[:200]}"
    )
    return resp.json()


# ============================================================
# Auth Edge Cases
# ============================================================


class TestAuth:
    """Tests for auth endpoint edge cases."""

    @pytest.mark.asyncio
    async def test_login_bad_username(self, client):
        resp = await client.post(
            "/api/auth/token",
            data={"username": "nobody", "password": "x"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_bad_password(self, client):
        async with TestSession() as db:
            user = User(
                username="badpw", display_name="BadPW",
                hashed_password=get_password_hash("correct"),
            )
            db.add(user)
            await db.commit()

        resp = await client.post(
            "/api/auth/token",
            data={"username": "badpw", "password": "wrong"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client):
        resp = await client.post("/api/auth/token", data={})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_empty_token(self, client):
        client.cookies.set("token", "")
        resp = await client.get("/api/users/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_junk_token(self, client):
        client.cookies.set("token", "not-a-valid-jwt")
        resp = await client.get("/api/users/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_expired_token(self, client):
        async with TestSession() as db:
            user = User(
                username="expuser", display_name="Expired User",
                hashed_password=get_password_hash("x"),
            )
            db.add(user)
            await db.commit()
            user_id = user.id

        bad_token = create_access_token(
            user_id=user_id, username="expuser", expiry_days=-1,
        )
        client.cookies.set("token", bad_token)
        resp = await client.get("/api/users/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_missing_token(self, client):
        resp = await client.get("/api/users/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================
# User Profile
# ============================================================

class TestUserProfile:
    """Profile GET/PUT. No DELETE endpoint exists yet."""

    @pytest_asyncio.fixture
    async def ac(self, client):
        async with TestSession() as db:
            user = User(
                username="proftest", display_name="Profile Test",
                hashed_password=get_password_hash("pass123"),
            )
            db.add(user)
            await db.commit()
        resp = await client.post(
            "/api/auth/token",
            data={"username": "proftest", "password": "pass123"},
        )
        assert resp.status_code == 200
        client.cookies.set("token", resp.json()["access_token"])
        return client

    @pytest.mark.asyncio
    async def test_get_me(self, ac):
        resp = await ac.get("/api/users/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "proftest"

    @pytest.mark.asyncio
    async def test_update_display_name(self, ac):
        resp = await ac.put("/api/users/me", json={"display_name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated"

    @pytest.mark.asyncio
    async def test_update_empty_body(self, ac):
        resp = await ac.put("/api/users/me", json={})
        assert resp.status_code == 200


# ============================================================
# Plants — Error / Edge Cases
# ============================================================

class TestPlants:
    """404s on nonexistent, validation, filter, archive idempotence.
    All list/create requests use trailing slashes to avoid 307 redirect."""

    @pytest_asyncio.fixture
    async def ac(self, client):
        async with TestSession() as db:
            user = User(
                username="planttest", display_name="Plant Test",
                hashed_password=get_password_hash("pass123"),
            )
            db.add(user)
            await db.commit()
        resp = await client.post(
            "/api/auth/token",
            data={"username": "planttest", "password": "pass123"},
        )
        assert resp.status_code == 200
        client.cookies.set("token", resp.json()["access_token"])
        return client

    @pytest_asyncio.fixture
    async def plant(self, ac):
        resp = await ac.post("/api/plants/", json={"name": "Test Plant", "location": "lab"})
        assert resp.status_code == 201
        return resp.json()

    @pytest.mark.asyncio
    async def test_404_get(self, ac):
        assert (await ac.get("/api/plants/99999")).status_code == 404

    @pytest.mark.asyncio
    async def test_404_update(self, ac):
        assert (await ac.put("/api/plants/99999", json={"name": "Ghost"})).status_code == 404

    @pytest.mark.asyncio
    async def test_404_archive(self, ac):
        assert (await ac.post("/api/plants/99999/archive")).status_code == 404

    @pytest.mark.asyncio
    async def test_404_delete(self, ac):
        assert (await ac.delete("/api/plants/99999")).status_code == 404

    @pytest.mark.asyncio
    async def test_create_missing_name(self, ac):
        resp = await ac.post("/api/plants/", json={"species": "test"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_archive_idempotent(self, ac, plant):
        r1 = await ac.post(f"/api/plants/{plant['id']}/archive")
        assert r1.status_code == 200
        r2 = await ac.post(f"/api/plants/{plant['id']}/archive")
        assert r2.status_code == 200

    @pytest.mark.asyncio
    async def test_location_filter(self, ac, plant):
        """List endpoint does NOT support a location query param (known gap)."""
        await ac.put(f"/api/plants/{plant['id']}", json={"location": "kitchen"})
        r = await ac.post("/api/plants/", json={"name": "Second", "location": "greenhouse"})
        assert r.status_code == 201

        # The endpoint currently ignores location filter and returns all plants
        r1 = await ac.get("/api/plants/?location=kitchen")
        plants = r1.json()
        assert len(plants) == 2  # returns all plants, ignores filter
        locations = [p["location"] for p in plants]
        assert "kitchen" in locations
        assert "greenhouse" in locations


# ============================================================
# Tasks — Recurrence, Edge Cases, Bug Detection
# ============================================================

class TestTasks:
    """Tests for task recurrence, advance, one-shot consumption, notes,
    and the dead-link bug in the frontend."""

    @pytest_asyncio.fixture
    async def ac(self, client):
        async with TestSession() as db:
            user = User(
                username="tasktest", display_name="Task Test",
                hashed_password=get_password_hash("pass123"),
            )
            db.add(user)
            await db.commit()
        resp = await client.post(
            "/api/auth/token",
            data={"username": "tasktest", "password": "pass123"},
        )
        assert resp.status_code == 200
        client.cookies.set("token", resp.json()["access_token"])
        return client

    @pytest_asyncio.fixture
    async def plant(self, ac):
        resp = await ac.post("/api/plants/", json={"name": "Task Plant"})
        assert resp.status_code == 201
        return resp.json()

    @pytest.mark.asyncio
    async def test_no_due_date(self, ac, plant):
        resp = await ac.post(f"/api/plants/{plant['id']}/tasks/",
                             json={"type": "water"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_complete_nonexistent(self, ac):
        assert (await ac.post("/api/tasks/99999/complete")).status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, ac, plant):
        assert (await ac.get(f"/api/plants/{plant['id']}/tasks/99999")).status_code == 404

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, ac):
        assert (await ac.put("/api/tasks/99999", json={"label": "Nope"})).status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, ac):
        assert (await ac.delete("/api/tasks/99999")).status_code == 404

    @pytest.mark.asyncio
    async def test_recurring_advance(self, ac, plant):
        r = await ac.post(f"/api/plants/{plant['id']}/tasks/",
                          json={"type": "water", "due_date": "2026-05-02", "interval_days": 7})
        tid, orig = r.json()["id"], r.json()["due_date"]

        r2 = await ac.post(f"/api/tasks/{tid}/complete", json={"advance": True})
        assert r2.status_code == 200
        assert r2.json()["due_date"] != orig
        assert r2.json()["is_active"] is True

    @pytest.mark.asyncio
    async def test_recurring_with_next_date(self, ac, plant):
        r = await ac.post(f"/api/plants/{plant['id']}/tasks/",
                          json={"type": "water", "due_date": "2026-05-02", "interval_days": 7})
        r2 = await ac.post(f"/api/tasks/{r.json()['id']}/complete",
                           json={"advance": True, "next_due_date": "2026-06-01"})
        assert r2.status_code == 200
        assert r2.json()["due_date"].startswith("2026-06-01")

    @pytest.mark.asyncio
    async def test_one_shot_consumed(self, ac, plant):
        r = await ac.post(f"/api/plants/{plant['id']}/tasks/",
                          json={"type": "fertilize", "due_date": "2026-05-02"})
        r2 = await ac.post(f"/api/tasks/{r.json()['id']}/complete", json={"advance": True})
        assert r2.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_complete_no_advance(self, ac, plant):
        r = await ac.post(f"/api/plants/{plant['id']}/tasks/",
                          json={"type": "water", "due_date": "2026-05-02", "interval_days": 7})
        orig = r.json()["due_date"]
        r2 = await ac.post(f"/api/tasks/{r.json()['id']}/complete", json={"advance": False})
        assert r2.json()["due_date"] == orig
        assert r2.json()["is_active"] is True
        assert r2.json()["last_completed_at"] is not None

    @pytest.mark.asyncio
    async def test_complete_with_notes(self, ac, plant):
        r = await ac.post(f"/api/plants/{plant['id']}/tasks/",
                          json={"type": "water", "due_date": "2026-05-02", "notes": "original"})
        r2 = await ac.post(f"/api/tasks/{r.json()['id']}/complete",
                           json={"advance": True, "notes": "added"})
        assert "original" in r2.json()["notes"]
        assert "added" in r2.json()["notes"]

    @pytest.mark.asyncio
    async def test_update(self, ac, plant):
        r = await ac.post(f"/api/plants/{plant['id']}/tasks/",
                          json={"type": "water", "due_date": "2026-05-02"})
        r2 = await ac.put(f"/api/tasks/{r.json()['id']}",
                          json={"label": "Updated", "interval_days": 14})
        assert r2.json()["label"] == "Updated"
        assert r2.json()["interval_days"] == 14

    @pytest.mark.asyncio
    async def test_delete(self, ac, plant):
        r = await ac.post(f"/api/plants/{plant['id']}/tasks/",
                          json={"type": "water", "due_date": "2026-05-02"})
        tid = r.json()["id"]
        assert (await ac.delete(f"/api/tasks/{tid}")).status_code == 204
        assert (await ac.get(f"/api/plants/{plant['id']}/tasks/99999")).status_code == 404

    # --- Regression: scoped complete route (was broken, now fixed) ---
    @pytest.mark.asyncio
    async def test_plant_scoped_complete_url(self, ac, plant):
        """
        The frontend JS at plant_detail.html calls
        POST /api/plants/{plant_id}/tasks/{task_id}/complete.
        This endpoint was missing (dead link) and has been added via the
        scoped router to match what the frontend actually sends.
        """
        r = await ac.post(f"/api/plants/{plant['id']}/tasks/",
                          json={"type": "water", "due_date": "2026-05-02"})
        tid = r.json()["id"]

        resp = await ac.post(f"/api/plants/{plant['id']}/tasks/{tid}/complete")
        assert resp.status_code == 200, (
            f"Frontend uses /api/plants/.../tasks/.../complete but got "
            f"{resp.status_code}. Expected 200 since the scoped route was added."
        )
        data = resp.json()
        assert data["is_active"] == False  # one-shot task consumed


# ============================================================
# Photos — Upload, Primary, Delete, Error Handling
# ============================================================

class TestPhotos:
    @pytest_asyncio.fixture
    async def ac(self, client):
        async with TestSession() as db:
            user = User(
                username="phototest", display_name="Photo Test",
                hashed_password=get_password_hash("pass123"),
            )
            db.add(user)
            await db.commit()
        resp = await client.post(
            "/api/auth/token",
            data={"username": "phototest", "password": "pass123"},
        )
        assert resp.status_code == 200
        client.cookies.set("token", resp.json()["access_token"])
        return client

    @pytest_asyncio.fixture
    async def plant(self, ac):
        resp = await ac.post("/api/plants/", json={"name": "Photo Plant"})
        assert resp.status_code == 201
        return resp.json()

    @pytest.mark.asyncio
    async def test_empty_list(self, ac, plant):
        assert (await ac.get(f"/api/plants/{plant['id']}/photos/")).json() == []

    @pytest.mark.asyncio
    async def test_upload(self, ac, plant):
        """Upload a real PNG using PIL to exercise the full pipeline."""
        from PIL import Image
        buf = BytesIO()
        img = Image.new("RGB", (100, 100), color="red")
        img.save(buf, format="PNG")
        buf.seek(0)
        resp = await ac.post(
            f"/api/plants/{plant['id']}/photos/",
            files={"file": ("test.png", buf, "image/png")},
            data={"caption": "Test photo"},
        )
        assert resp.status_code == 201
        assert resp.json()["is_primary"] is True
        assert resp.json()["caption"] == "Test photo"

    @pytest.mark.asyncio
    async def test_upload_no_file(self, ac, plant):
        resp = await ac.post(f"/api/plants/{plant['id']}/photos/", data={"caption": "nofile"})
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_set_primary_nonexistent(self, ac, plant):
        assert (
            await ac.post(f"/api/plants/{plant['id']}/photos/99999/set-primary")
        ).status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, ac, plant):
        assert (
            await ac.delete(f"/api/plants/{plant['id']}/photos/99999")
        ).status_code == 404

    @pytest.mark.asyncio
    async def test_upload_nonexistent_plant_returns_not_404(self, ac):
        """
        BUG: Uploading a photo to a plant with ID 99999 returns a 500 error
        (PIL.UnidentifiedImageError) instead of 404 Not Found.
        The router doesn't verify the plant exists before attempting
        file operations.
        """
        from PIL import Image
        buf = BytesIO()
        img = Image.new("RGB", (10, 10), color="red")
        img.save(buf, format="PNG")
        buf.seek(0)
        resp = await ac.post(
            "/api/plants/99999/photos/",
            files={"file": ("x.png", buf, "image/png")},
        )
        # Bug fixed: now properly returns 404 for nonexistent plant
        assert resp.status_code == 404, (
            f"Got {resp.status_code}, expected 404 (plant does not exist)"
        )
        assert resp.json()["detail"] == "Plant not found"


# ============================================================
# Activity — Validation
# ============================================================

class TestActivity:
    @pytest_asyncio.fixture
    async def ac(self, client):
        async with TestSession() as db:
            user = User(
                username="acttest", display_name="Activity Test",
                hashed_password=get_password_hash("pass123"),
            )
            db.add(user)
            await db.commit()
        resp = await client.post(
            "/api/auth/token",
            data={"username": "acttest", "password": "pass123"},
        )
        assert resp.status_code == 200
        client.cookies.set("token", resp.json()["access_token"])
        return client

    @pytest_asyncio.fixture
    async def plant(self, ac):
        resp = await ac.post("/api/plants/", json={"name": "Activity Plant"})
        assert resp.status_code == 201
        return resp.json()

    @pytest.mark.asyncio
    async def test_create_no_type(self, ac, plant):
        resp = await ac.post(f"/api/plants/{plant['id']}/activity/",
                             json={"notes": "test"})
        assert resp.status_code == 422


# ============================================================
# Upcoming Tasks
# ============================================================

class TestUpcoming:
    @pytest_asyncio.fixture
    async def ac(self, client):
        async with TestSession() as db:
            user = User(
                username="upctest", display_name="Upcoming Test",
                hashed_password=get_password_hash("pass123"),
            )
            db.add(user)
            await db.commit()
        resp = await client.post(
            "/api/auth/token",
            data={"username": "upctest", "password": "pass123"},
        )
        assert resp.status_code == 200
        client.cookies.set("token", resp.json()["access_token"])
        return client

    @pytest.mark.asyncio
    async def test_empty(self, ac):
        resp = await ac.get("/api/tasks/upcoming?days=30")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_zero_days(self, ac):
        assert (await ac.get("/api/tasks/upcoming?days=0")).status_code == 200

    @pytest.mark.asyncio
    async def test_large_window(self, ac):
        assert (await ac.get("/api/tasks/upcoming?days=365")).status_code == 200


# ============================================================
# Pages + Static Serving
# ============================================================

class TestPages:
    @pytest_asyncio.fixture
    async def ac(self, client):
        async with TestSession() as db:
            user = User(
                username="pagetest", display_name="Page Test",
                hashed_password=get_password_hash("pass123"),
            )
            db.add(user)
            await db.commit()
        resp = await client.post(
            "/api/auth/token",
            data={"username": "pagetest", "password": "pass123"},
        )
        assert resp.status_code == 200
        client.cookies.set("token", resp.json()["access_token"])
        return client

    @pytest.mark.asyncio
    async def test_archive_page(self, ac):
        r = await ac.post("/api/plants/", json={"name": "Archived Plant"})
        assert r.status_code == 201
        await ac.post(f"/api/plants/{r.json()['id']}/archive")

        resp = await ac.get("/archive")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_missing_photo_file(self, ac):
        assert (await ac.get("/uploads/photos/nonexistent.png")).status_code == 404

    @pytest.mark.asyncio
    async def test_missing_thumbnail(self, ac):
        assert (await ac.get("/uploads/thumbnails/nonexistent.png")).status_code == 404


# ============================================================
# Health
# ============================================================

class TestHealth:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"