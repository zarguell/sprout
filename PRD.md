# Sprout — Product Requirements Document

## Overview

A self-hosted, collaborative plant care management application built on FastAPI, SQLite, and flat-file photo storage. The system provides a shared dashboard for two or more users to track plants, assign care tasks, and surface reminders via a REST API consumed by an external orchestration agent. The threat model is authentication-only: all authenticated users share equal access to all resources.

***

## Goals & Non-Goals

### Goals

- Allow authenticated users to create, view, edit, and delete plant profiles
- Track recurring care tasks (watering, fertilizing, repotting) with due-date scheduling
- Store and serve plant photos from local flat-file storage with auto-generated thumbnails
- Maintain a photo history per plant with the ability to delete individual photos
- Archive plants (soft-delete) so dead or retired plants remain visible historically
- Expose a full REST API for external integration
- Provide a web dashboard suitable for casual daily use by non-technical users
- Run as a single Docker container on a homelab host

### Non-Goals

- Resource-level authorization (any authenticated user can act on any plant or task)
- Push notifications (handled externally via the REST API)
- Public-facing access or multi-tenant isolation
- Mobile-native app (responsive web only)
- Plant identification or external database lookup
- Weather integration

***

## Users & Roles

There is a single access tier: **authenticated user**. All authenticated users have full read/write access to all plants, tasks, and photos. User accounts are created by an admin bootstrap process (no self-registration). The initial deployment targets two users.

***

## Architecture

### Stack

| Layer | Technology | Rationale |
|---|---|---|
| API | FastAPI (Python 3.12+) | Async, typed, automatic OpenAPI docs |
| Database | SQLite via SQLAlchemy (async) | Zero-ops, sufficient for 2-user homelab scale |
| Photo storage | Local filesystem (`./data/photos/`) | No object store dependency; served via authenticated endpoints |
| Thumbnails | Pillow | Auto-generated on upload; stored alongside originals |
| Scheduling | asyncio background task (lifespan) | Single nightly job; no external scheduler state needed |
| Auth | JWT (PyJWT) + bcrypt password hashing | Stateless tokens, no external auth dependency |
| Frontend | Jinja2 templates + Alpine.js + Tailwind CSS (built) | Server-rendered with lightweight interactivity; Tailwind build for purged CSS |
| Migrations | Alembic | Schema versioning from day one; baseline revision at init |
| Containerization | Docker + Docker Compose | Single-container deployment |

### Directory Layout

```
sprout/
├── app/
│   ├── main.py               # FastAPI app, lifespan, router registration
│   ├── models.py             # SQLAlchemy ORM models
│   ├── schemas.py            # Pydantic request/response models
│   ├── database.py           # Async engine, session factory
│   ├── auth.py               # JWT creation, verification, bcrypt helpers
│   ├── background.py         # asyncio lifespan background task (nightly job)
│   ├── images.py             # Pillow thumbnail generation helper
│   ├── cli.py                # User management CLI
│   └── routers/
│       ├── plants.py
│       ├── tasks.py
│       ├── photos.py
│       ├── activity.py
│       └── users.py
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── archive.html
│       ├── plant_detail.html
│       ├── upcoming_tasks.html
│       └── login.html
├── static/
│   └── css/
│       └── output.css        # Tailwind-built CSS (purged)
├── data/
│   ├── db/sprout.db
│   └── photos/
│       └── {plant_id}/
│           ├── {uuid}.jpg         # Original
│           └── {uuid}_thumb.jpg   # Thumbnail (400px wide)
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py
├── alembic.ini
├── tailwind.config.js          # Tailwind configuration
├── package.json                # npm for Tailwind build
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

***

## Data Models

### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `username` | TEXT UNIQUE NOT NULL | |
| `display_name` | TEXT | Shown in dashboard |
| `hashed_password` | TEXT NOT NULL | bcrypt |
| `created_at` | DATETIME | |

### `revoked_tokens`

| Column | Type | Notes |
|---|---|---|
| `jti` | TEXT PK | JWT ID claim (UUID); indexed |
| `revoked_at` | DATETIME NOT NULL | |
| `expires_at` | DATETIME NOT NULL | Original token expiry; used for pruning |
| `revoked_by` | INTEGER FK → users.id | User who triggered revocation |

JWTs include a `jti` (UUID v4) claim at creation time. `get_current_user` checks the `jti` against this table on every request after signature verification. A match returns 401. The nightly background task deletes rows where `expires_at < now()` to keep the table small — expired tokens are harmless regardless of revocation status.

### `plants`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT NOT NULL | User-given name (e.g., "Big Monstera") |
| `species` | TEXT | Optional scientific/common name |
| `location` | TEXT | Room or zone label |
| `notes` | TEXT | Free-text |
| `primary_photo_id` | INTEGER FK → photos.id ON DELETE SET NULL | Cover photo; nullable |
| `archived` | BOOLEAN DEFAULT FALSE | Soft-delete flag |
| `archived_at` | DATETIME | Set when archived |
| `archived_by` | INTEGER FK → users.id | |
| `archive_reason` | TEXT | Optional: "deceased", "given away", etc. |
| `created_by` | INTEGER FK → users.id | |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### `tasks`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `plant_id` | INTEGER FK → plants.id CASCADE DELETE | |
| `type` | TEXT | `CHECK(type IN ('water','fertilize','repot','custom'))` |
| `label` | TEXT | Used when type = `custom` |
| `interval_days` | INTEGER | Recurrence period; NULL = one-shot |
| `due_date` | DATETIME NOT NULL | Next due timestamp |
| `last_completed_at` | DATETIME | |
| `last_completed_by` | INTEGER FK → users.id | |
| `is_active` | BOOLEAN DEFAULT TRUE | Soft-disable without deletion |
| `created_by` | INTEGER FK → users.id | User who created the task |
| `notes` | TEXT | |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

Archived plants retain their tasks in the database but tasks are excluded from due-task queries and the scheduler.

### `photos`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `plant_id` | INTEGER FK → plants.id CASCADE DELETE | |
| `original_path` | TEXT NOT NULL | Relative path to full-size file |
| `thumbnail_path` | TEXT NOT NULL | Relative path to thumbnail (400px wide) |
| `uploaded_by` | INTEGER FK → users.id | |
| `uploaded_at` | DATETIME | |
| `updated_at` | DATETIME | |
| `caption` | TEXT | Optional user note on this photo |

On upload, Pillow generates the thumbnail immediately before writing the DB record. Both paths are stored. If thumbnail generation fails, the upload is rejected.

Deleting a photo record also deletes both files from disk. If the deleted photo is the `primary_photo_id` on its plant, `primary_photo_id` is set to null (the dashboard falls back to a placeholder).

### `plant_activity`

A rolling, append-only activity log per plant. Entries are created but never edited or deleted (no UPDATE/DELETE API). This gives partners a shared, read-only history — "moved to sunnier window", "repotted with fresh soil", "looking droopy after road trip" — without the weight of a full journaling system.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `plant_id` | INTEGER FK → plants.id CASCADE DELETE | |
| `user_id` | INTEGER FK → users.id | Author of the note |
| `content` | TEXT NOT NULL | Free-text note |
| `created_at` | DATETIME NOT NULL | Set at insertion time; used for sorting |

No `updated_at` — entries are immutable once written. No `type` column in v1; all entries are plain notes. A future version could add typed events (auto-generated from task completions, photo uploads, etc.) distinguished by a nullable `type` column with a `NULL` type meaning "user note".

***

## API Specification

### Authentication

All routes require a valid JWT Bearer token except `POST /auth/token` and CSS static assets.

**`POST /auth/token`** — OAuth2 password flow. Returns `access_token` (JWT, 24h expiry) and `token_type: bearer`.

**`POST /auth/revoke`** — Revokes the current token by inserting its `jti` into `revoked_tokens`. Accepts the token via cookie or `Authorization: Bearer` header (same extraction as `get_current_user`). Returns 204. Use this to invalidate a browser session on logout or rotate a compromised service token.

The frontend stores the token in an httpOnly, SameSite=Strict cookie set by the server on successful login.

***

### Plants

| Method | Path | Description |
|---|---|---|
| `GET` | `/plants` | List active (non-archived) plants; supports `?location=` filter |
| `GET` | `/plants/archived` | List archived plants |
| `POST` | `/plants` | Create plant |
| `GET` | `/plants/{id}` | Plant detail with tasks and photos |
| `PUT` | `/plants/{id}` | Update plant fields |
| `DELETE` | `/plants/{id}` | Hard delete plant (cascades to tasks and photos on disk) |
| `POST` | `/plants/{id}/archive` | Archive plant (soft delete) |
| `POST` | `/plants/{id}/unarchive` | Restore plant to active |

**Create/Update plant body:**
```json
{
  "name": "Big Monstera",
  "species": "Monstera deliciosa",
  "location": "Living Room",
  "notes": "Likes indirect light"
}
```

**Archive body:**
```json
{
  "reason": "deceased"
}
```

`GET /plants` never returns archived plants. `GET /plants/archived` returns only archived plants, sorted by `archived_at` descending. `GET /plants/{id}` returns any plant regardless of archive status (so direct links to archived plants remain valid).

***

### Tasks

| Method | Path | Description |
|---|---|---|
| `GET` | `/plants/{id}/tasks` | List tasks for a plant (active and inactive) |
| `POST` | `/plants/{id}/tasks` | Create task |
| `PUT` | `/tasks/{id}` | Update task (interval, due date, label, notes) |
| `POST` | `/tasks/{id}/complete` | Mark complete; advance behavior controlled by request body |
| `DELETE` | `/tasks/{id}` | Delete task |
| `GET` | `/tasks/due` | All tasks due now across all active plants; returns `Last-Modified` header |
| `GET` | `/tasks/upcoming` | Tasks due within `?days=N` (default 3) across all active plants |

**Create task body:**
```json
{
  "type": "water",
  "interval_days": 7,
  "due_date": "2026-05-05T08:00:00",
  "notes": "Check soil first"
}
```

**Complete task body:**
```json
{
  "notes": "Used rainwater",
  "advance": true,
  "next_due_date": null
}
```

- `advance` (boolean, default `true`): if `true` and `interval_days` is set, `due_date` is advanced to now() + `interval_days`. If `false`, the task remains due and no date change occurs — caller must supply `next_due_date` or update the task separately.
- `next_due_date` (ISO datetime, optional): if provided, overrides the interval calculation and sets `due_date` explicitly. Useful for irregular tasks like repotting where the next date is judgment-based.
- If `interval_days` is null and `advance` is true: `is_active` is set to false (one-shot task consumed).

On completion, always sets: `last_completed_at` = now(), `last_completed_by` = current user.

`GET /tasks/due` and `GET /tasks/upcoming` exclude tasks belonging to archived plants.

**Empty-result `Last-Modified` behavior:** When no tasks are currently due, `Last-Modified` is set to `datetime.now(timezone.utc)` rather than omitted. This ensures the next poll with `If-Modified-Since` doesn't falsely return 304 when tasks were cleared between polls.

**Conditional request support on `/tasks/due`:** The response includes a `Last-Modified` header set to `MAX(due_date)` across currently due tasks. The integration agent should send `If-Modified-Since` on subsequent polls; the server returns `304 Not Modified` with no body if no new tasks have become due since the last request. This prevents redundant processing on the agent side.

**`GET /tasks/due` response shape:**
```json
[
  {
    "task_id": 12,
    "plant_id": 3,
    "plant_name": "Big Monstera",
    "location": "Living Room",
    "type": "water",
    "label": null,
    "due_date": "2026-05-02T08:00:00",
    "days_overdue": 0
  }
]
```

***

### Photos

| Method | Path | Description |
|---|---|---|
| `POST` | `/plants/{id}/photos` | Upload photo; generates thumbnail on server |
| `GET` | `/plants/{id}/photos` | List all photos for a plant, newest first; supports `?limit=N` (default 50) and `?offset=N` for pagination |
| `GET` | `/plants/{plant_id}/photos/{photo_id}/file` | Serve original photo file (authenticated; returns `FileResponse`) |
| `GET` | `/plants/{plant_id}/photos/{photo_id}/thumbnail` | Serve thumbnail file (authenticated; returns `FileResponse`) |
| `DELETE` | `/photos/{id}` | Delete photo record and both files from disk |
| `POST` | `/plants/{id}/photos/{photo_id}/set-primary` | Set as cover photo |

**Upload** — `multipart/form-data` with fields:
- `file` (required): image file, JPEG/PNG/WebP, max 10 MB
- `caption` (optional): text

**Server-side on upload:**
1. Validate MIME type and size
2. Generate UUID filename
3. Save original to `./data/photos/{plant_id}/{uuid}.jpg`
4. Use Pillow to generate thumbnail: resize to 400px wide (or image's natural width if smaller), maintain aspect ratio, save as `{uuid}_thumb.jpg`
5. Write DB record with both paths

**Thumbnail behavior:**
- Width fixed at 400px; height auto-scaled to maintain aspect ratio
- If original image is narrower than 400px, no upscaling occurs (thumbnail = original dimensions)
- This preserves the full composition for both portrait (whole plant) and landscape (close-up) photos

**`GET /plants/{id}/photos` response shape:**
```json
[
  {
    "id": 7,
    "plant_id": 3,
    "original_url": "/plants/3/photos/7/file",
    "thumbnail_url": "/plants/3/photos/7/thumbnail",
    "uploaded_by": "alice",
    "uploaded_at": "2026-04-15T10:22:00",
    "caption": "New leaf emerging",
    "is_primary": true
  }
]
```

Photo deletion: if the photo is the plant's `primary_photo_id`, that field is set to null. Files are deleted from disk before the DB record is removed; if file deletion fails, the DB record is still removed (orphaned files are acceptable, recoverable by a cleanup script).

***

### Plant Activity

| Method | Path | Description |
|---|---|---|
| `GET` | `/plants/{id}/activity` | List activity entries, newest first; supports `?limit=N` (default 50) and `?offset=N` |
| `POST` | `/plants/{id}/activity` | Add a new activity note |

No `PUT` or `DELETE` routes — entries are append-only and immutable.

**Create activity body:**
```json
{
  "content": "Moved to sunnier window, leaves perking up already"
}
```

**`GET /plants/{id}/activity` response shape:**
```json
[
  {
    "id": 5,
    "plant_id": 3,
    "user_id": 1,
    "username": "alice",
    "display_name": "Alice",
    "content": "Moved to sunnier window, leaves perking up already",
    "created_at": "2026-05-01T14:30:00"
  }
]
```

Activity entries are included in `GET /plants/{id}` (plant detail) response alongside tasks and photos.

***

### Users

| Method | Path | Description |
|---|---|---|
| `GET` | `/users/me` | Current user profile |
| `PUT` | `/users/me` | Update display name or password |
| `GET` | `/users` | List all users |

User creation is handled via CLI only (`python -m app.cli create-user --username alice --display-name "Alice"`), preventing open registration.

**CLI commands:**

| Command | Description |
|---|---|
| `python -m app.cli create-user` | Bootstrap a new user account |
| `python -m app.cli create-token` | Generate a long-lived service token |
| `python -m app.cli cleanup-orphans [--dry-run]` | Walk `./data/photos/` and delete files with no corresponding DB record. `--dry-run` prints matches without deleting. |

`cleanup-orphans` cross-references every file path under `./data/photos/` against `photos.original_path` and `photos.thumbnail_path` in SQLite. Files with no DB record are considered orphaned and removed. Run manually or as a weekly cron on the host.

***

## Scheduling (asyncio Background Task)

A single asyncio background task runs inside the FastAPI `lifespan()` context manager. It fires nightly at 02:00, computing the exact sleep duration on each wake so it is restart-safe and wall-clock aligned. No external scheduler library is used — this avoids APScheduler's additional state and startup complexity for a single job.

**Nightly job logic:**
1. Set `is_active = false` on tasks belonging to archived plants (idempotent cleanup)
2. Prune `revoked_tokens` rows where `expires_at < now()` (token table hygiene)
3. No other scheduled work — task due dates are computed on-demand by `/tasks/due` and `/tasks/upcoming`

The external integration agent polls `/tasks/due` at whatever cadence it chooses. No webhook or push mechanism is implemented in v1. The API-first design intentionally omits notification integrations (email, push, etc.) — users can script their own automation via the REST API.

**Restart-safe scheduling:** The background task computes `seconds_until_next_run` on each wake rather than sleeping a flat interval. A container restart at 11 PM sleeps ~3 hours to the next 2 AM target, not 24 hours.

```python
async def nightly_maintenance(db_session_factory):
    from datetime import timezone
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        async with db_session_factory() as db:
            await db.execute(
                text("UPDATE tasks SET is_active = false "
                     "WHERE plant_id IN (SELECT id FROM plants WHERE archived = true) "
                     "AND is_active = true")
            )
            await db.execute(
                text("DELETE FROM revoked_tokens WHERE expires_at < :now"),
                {"now": datetime.now(timezone.utc)}
            )
            await db.commit()
```

***

## Frontend (Dashboard)

Server-rendered Jinja2 templates with Alpine.js for interactivity (modals, inline fetches, photo gallery). Tailwind CSS built with purge for optimized CSS.

### Tailwind Build

Tailwind is built via npm during Docker image build:

- `package.json` includes `tailwindcss` as a dev dependency
- `tailwind.config.js` configures content paths for template scanning
- `static/css/output.css` is the purged production CSS
- Dockerfile runs `npm run build:css` during image build

For local development, `npm run dev:css` watches for changes. The app serves `/static/css/output.css` via FastAPI's `StaticFiles`.

### Pages

| Route | Template | Description |
|---|---|---|
| `GET /` | `dashboard.html` | Card grid of active plants, overdue badges, recent activity |
| `GET /archive` | `archive.html` | Grid of archived plants, sortable by archive date |
| `GET /plants/{id}` | `plant_detail.html` | Full plant detail: photo history, task list, notes |
| `GET /tasks` | `upcoming_tasks.html` | Tasks grouped by urgency (overdue, today, this week, later) |
| `GET /login` | `login.html` | Login form |

### Dashboard (`/`)

- Plant cards: thumbnail, name, location, next due task type + date
- Overdue task count badge (amber ≥1, red ≥3)
- Quick-add plant modal
- Recent activity feed: last 10 task completions with username and timestamp
- Link to Archive page in nav

### Archive Page (`/archive`)

- Same card layout as dashboard using thumbnails
- Cards show archive date and reason
- "Restore" button on each card (calls `POST /plants/{id}/unarchive`)
- Archive cards display plant metadata and cover photo only — no task information

### Plant Detail (`/plants/{id}`)

- Photo gallery: scrollable row of thumbnails, click to view full size in a lightbox
- Upload photo button → file picker → immediate upload with caption field
- Delete photo button on each thumbnail (confirmation prompt); primary photo badge
- Set primary photo button
- Task list: type icon, due date, interval badge, complete / edit / delete actions
- Add task form (collapsible inline)
- Activity log: chronological list of notes with author, timestamp, and content; "Add note" input at the top
- Edit plant metadata (inline form)
- Archive plant button (with reason field) — replaces Delete for day-to-day use
- Hard delete button (destructive, confirmation modal, removes all data and files)
- Archived plant banner with archive date and reason
- Restore button shown instead of Archive/Archive button
- Task list hidden entirely for archived plants

***

## Authentication & Security

The threat model is **perimeter auth only**. Any valid JWT grants full application access. Ownership fields (`created_by`, `uploaded_by`, `archived_by`) are recorded for display and audit purposes, not for access control enforcement.

### Implementation

- Passwords hashed with bcrypt (cost factor 12)
- JWT signed with HS256; secret from `JWT_SECRET` environment variable
- Browser session tokens: 24-hour expiry
- Service/integration tokens: configurable long expiry via `JWT_SERVICE_EXPIRY_DAYS` env var (default 365); generated via CLI (`python -m app.cli create-token --username svc-agent`)
- Frontend stores token in httpOnly, SameSite=Strict cookie
- All API routes protected via FastAPI `Depends(get_current_user)`
- `get_current_user` extracts credentials via two paths in order: (1) httpOnly cookie (browser sessions), (2) `Authorization: Bearer` header (agent/CLI tokens). Returns 401 if neither is present. OpenAPI docs annotate browser routes with cookie auth and agent-facing routes with `HTTPBearer` security scheme.
- HTTPS termination handled by the homelab reverse proxy; app runs HTTP internally

### SQLite Configuration

WAL mode must be set explicitly at connection time. aiosqlite does not enable it by default, and concurrent reads from the polling agent alongside active browser sessions will cause locking errors without it.

```python
from sqlalchemy import event

@event.listens_for(engine.sync_engine, "connect")
def set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA synchronous=NORMAL")
```

### Known Security Gaps (v1)

- No rate limiting on `/auth/token`. Acceptable for a homelab behind a reverse proxy with network-level access controls.
- Token revocation via `POST /auth/revoke` is supported in v1. The `revoked_tokens` table is checked on every authenticated request; pruned nightly.
- No CORS middleware configured. The server-rendered frontend and API share the same origin, so CORS is unnecessary for normal use. If cross-origin API access is needed (scripts, dashboards), add `CORSMiddleware` in `main.py`.
- ~~**Photo URLs are unauthenticated.**~~ Plant photos are served via an authenticated endpoint (`GET /plants/{plant_id}/photos/{photo_id}/file`) that reads from disk and returns a `FileResponse`. The `StaticFiles` mount is removed. This ensures photos require a valid JWT (via httpOnly cookie or Bearer header) to access.

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET` | Yes | Random 256-bit secret |
| `DATABASE_URL` | No | Defaults to `sqlite+aiosqlite:///./data/db/sprout.db` |
| `PHOTO_STORAGE_PATH` | No | Defaults to `./data/photos` |
| `JWT_SERVICE_EXPIRY_DAYS` | No | Service token lifetime (default 365) |

***

## Docker Compose

```yaml
services:
  sprout:
    build: .
    restart: unless-stopped
    ports:
      - "8090:8000"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"]
      interval: 30s
      timeout: 5s
      retries: 3
```

The `./data` bind mount persists both the SQLite database and all photo files across container rebuilds.

***

## v1 Scope Summary

| Feature | v1 |
|---|---|
| Plant CRUD + archive/unarchive | ✅ |
| Recurring task scheduling | ✅ |
| Photo upload with thumbnail generation | ✅ |
| Photo history per plant (multiple photos) | ✅ |
| Photo deletion (record + files) | ✅ |
| Authenticated photo serving (FileResponse) | ✅ |
| Plant activity log (append-only notes) | ✅ |
| Primary photo selection | ✅ |
| REST API (tasks/due, tasks/upcoming, full CRUD) | ✅ |
| Web dashboard with archive page | ✅ |
| JWT auth (perimeter only) | ✅ |
| CLI user + service token creation | ✅ |
| `cleanup-orphans` CLI command | ✅ |
| Alembic migrations (baseline) | ✅ |
| SQLite WAL mode | ✅ |
| `Last-Modified` / 304 on `/tasks/due` | ✅ |
| Token revocation (`POST /auth/revoke`, `revoked_tokens` table) | ✅ |

### Post-v1 Candidates

- Auto-generated activity entries (task completions, photo uploads, plant creation) with typed `activity.type` column
- Plant health journal / timeline view (curated from activity log)
- Image resizing beyond thumbnail (multiple sizes)
- Bulk CSV import
- Webhook push on task due (instead of poll-only)
- CORS middleware (if cross-origin API access is needed)

***

## Resolved Design Decisions

1. **Task completion advance behavior** — `advance` and `next_due_date` are parameters on `POST /tasks/{id}/complete`. Default `advance: true` covers routine tasks (watering); callers pass `advance: false` + explicit `next_due_date` for irregular tasks like repotting.
2. **Archived plant photo storage** — Photos are retained on disk and remain accessible via their static URLs. No file cleanup occurs on archive.
3. **Archive page task display** — Archive cards and archived plant detail views show only plant metadata and photo history. The task list is hidden entirely for archived plants.
4. **Scheduling** — APScheduler replaced with a bare asyncio background task in the lifespan context. Single nightly job does not warrant an external scheduler.
5. **File/DB atomicity on photo delete** — DB record is removed even if file deletion fails (pragmatic). `cleanup-orphans` CLI command recovers orphaned files and ships in v1.
6. **Conditional polling** — `/tasks/due` returns `Last-Modified` header; agent uses `If-Modified-Since` / 304 to skip redundant processing.
7. **Token revocation** — `revoked_tokens` table with `jti` PK; `POST /auth/revoke` ships in v1. Nightly job prunes expired rows.
8. **Background task restart safety** — nightly job computes wall-clock `seconds_until_2am` on each iteration rather than sleeping a flat 86400s. Restart-safe and aligned regardless of container start time.

