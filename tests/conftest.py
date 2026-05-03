"""Shared test fixtures for Sprout. Auto-discovered by pytest.

Imports shared infrastructure from test_shared and defines fixtures at
conftest level so both test_api.py and test_gaps.py can use them."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.models import Base, User
from app.main import app
from app.auth import get_password_hash
from test_shared import _test_engine, TestSession, setup_db


@pytest_asyncio.fixture
async def client():
    async with setup_db():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def auth_client(client):
    """Client with a default user created and authenticated."""
    async with TestSession() as db:
        user = User(
            username="default_user",
            display_name="Default User",
            hashed_password=get_password_hash("pass123"),
        )
        db.add(user)
        await db.commit()

    resp = await client.post(
        "/api/auth/token",
        data={"username": "default_user", "password": "pass123"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code}: {resp.text}"
    client.cookies.set("token", resp.json()["access_token"])
    return client