# 🌱 Sprout

A plant care tracker for the homelab. Track watering, fertilizing, repotting schedules, photo growth logs, and notes — for you and your household.

Built with FastAPI, SQLite, Tailwind CSS, and Alpine.js. Single Docker container, minimal setup.

## Features

- **Plant management** — Add, edit, archive, and delete plants with species, location, and notes
- **Task scheduling** — Recurring care tasks (water, fertilize, repot, custom) with due date tracking
- **Photo gallery** — Upload photos with auto-generated thumbnails, set a primary photo, lightbox viewer
- **Activity log** — Append-only notes per plant with timestamps
- **Overdue alerts** — Dashboard badges highlight overdue tasks (amber < 3 days, red ≥ 3 days)
- **Background scheduler** — Hourly check for due tasks
- **Integration API** — Poll `/api/tasks/due` with `Last-Modified`/`If-Modified-Since` for external automations
- **Multi-user** — JWT auth with httpOnly cookies (browser) and Bearer tokens (agents/CLI)
- **Service tokens** — Long-lived tokens for integrations, generated via CLI

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/zarguell/sprout.git
cd sprout
cp .env.example .env
```

Generate a JWT secret and set it in `.env`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Run with Docker Compose

```bash
docker compose up -d
```

### 3. Create a user

```bash
docker compose exec sprout python -m app.cli create-user --username admin --password yourpassword
```

### 4. Open the app

Visit `http://localhost:8090` and sign in.

## API

All API routes are under `/api/`. Full docs at `/docs` (Swagger UI) when the app is running.

### Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/token` | Login (sets httpOnly cookie) |
| `POST` | `/api/auth/revoke` | Logout |
| `GET` | `/api/plants/` | List plants (paginated) |
| `POST` | `/api/plants/` | Create plant |
| `GET` | `/api/plants/{id}` | Get plant details |
| `PUT` | `/api/plants/{id}` | Update plant |
| `POST` | `/api/plants/{id}/archive` | Archive plant |
| `POST` | `/api/plants/{id}/unarchive` | Restore plant |
| `DELETE` | `/api/plants/{id}` | Hard delete |
| `POST` | `/api/plants/{id}/tasks/` | Create task |
| `POST` | `/api/plants/{id}/tasks/{id}/complete` | Complete task (advances recurring) |
| `POST` | `/api/plants/{id}/photos/` | Upload photo |
| `GET` | `/api/plants/{id}/photos/{id}/file` | Get full photo (authenticated) |
| `GET` | `/api/plants/{id}/photos/{id}/thumbnail` | Get thumbnail (authenticated) |
| `POST` | `/api/plants/{id}/activity/` | Add activity note |
| `GET` | `/api/tasks/due` | Poll due tasks (supports `If-Modified-Since`) |
| `GET` | `/health` | Health check |

### Integration polling

For home automation or notification bots:

```
GET /api/tasks/due
If-Modified-Since: <last poll timestamp>
```

Returns `304 Not Modified` if nothing changed, otherwise JSON with all tasks due within 7 days.

### Generate a service token

```bash
docker compose exec sprout python -m app.cli create-token --username admin
```

Use the token as `Authorization: Bearer <token>` header.

## Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy (async), Alembic
- **Database**: SQLite with WAL mode
- **Frontend**: Jinja2 templates, Tailwind CSS, Alpine.js
- **Auth**: PyJWT + bcrypt
- **Scheduler**: APScheduler
- **Deployment**: Docker, Docker Compose

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | ✅ | — | 256-bit hex string for signing tokens |
| `JWT_SERVICE_EXPIRY_DAYS` | No | `365` | Service token expiry |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./data/db/sprout.db` | Database connection string |

## License

[MIT](LICENSE)
