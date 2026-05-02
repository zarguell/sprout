# AGENTS.md — Best Practices for AI-Assisted Development

This document captures conventions, patterns, and workflows for AI agents (and
humans) working on the Sprout codebase. It grows as the team learns what works
and what doesn't.

## Philosophy

- **Test-driven development (TDD).** Red → Green → Refactor. Always.
  Write a failing test first, make it pass, then clean up. This catches
  misunderstandings before they become bugs.
- **Prefer substance over ceremony.** Don't add abstractions before they're
  needed.
- **Favor small, focused commits.** Each commit should represent one logical
  change.
- **Be explicit over magic.** If a pattern is surprising, document it.

## Development Setup

### Prerequisites

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Tailwind CSS requires a one-time setup:

```sh
npm install
npm run build:css          # production build (minified)
npm run dev:css            # watch mode during development
```

Tailwind scans `templates/**/*.html` for utility classes to include in the
output. See `tailwind.config.js`.

### Running the app

```sh
uvicorn app.main:app --reload
```

The app uses SQLite by default (`data/db/sprout.db`). Set `DATABASE_URL` to
override.

### Running tests

```sh
pytest tests/ -v --tb=short          # all tests
pytest tests/test_api.py             # API integration tests only
pytest tests/test_smoke.py           # smoke tests only
```

Tests use an in-memory SQLite database and are fully isolated. No external
dependencies needed.

## Coding Conventions

### Python

- Type hints everywhere. Every function signature must have them.
- Async-first. The app uses `async def` + `asyncio` throughout.
- `ruff` for linting. See `.ruff.toml` (if one exists) for config.

### Tailwind CSS

- Build output goes to `static/css/output.css` (gitignored).
- Do **not** hand-write CSS. Use Tailwind utility classes exclusively.
- The Dockerfile has a multi-stage build (`css-build`) that generates CSS.
  When modifying templates, ensure the CSS build still works — the `css-build`
  stage copies the `templates/` directory so Tailwind can scan it.

## Architecture

### Project structure

```
app/
├── main.py               # FastAPI app, middleware, CORS
├── models.py             # SQLAlchemy ORM models
├── schemas.py            # Pydantic request/response schemas
├── database.py           # DB engine, session dependency
├── dependencies.py       # Custom FastAPI dependencies
├── auth.py               # Auth helpers (JWT, password hash)
├── images.py             # Photo/image handling
├── background.py         # Background task scheduling
├── cli.py                # CLI commands
├── routers/
│   ├── plants.py         # Plant CRUD
│   ├── tasks.py          # Task management
│   ├── activity.py       # Activity log
│   ├── photos.py         # Photo uploads
│   └── users.py          # User profile + auth (login, token)
templates/                # Jinja2 templates (no JinjaX components)
static/
  css/
    output.css            # Generated Tailwind CSS (gitignored)
tests/
  test_api.py             # API integration tests
  test_smoke.py           # Basic smoke tests
```

### Database

- SQLAlchemy async with `aiosqlite`. Migrations via Alembic.
- Each test run creates + destroys its own in-memory database.
- Schema migrations live in `alembic/versions/`.

## API Design

### JSON vs. Form Data

**All POST/PUT endpoints accept both JSON and form-encoded data.** The UI
submits forms as `application/x-www-form-urlencoded` (via `URLSearchParams`
and `FormData`), while programmatic clients use `application/json`.

This is handled by the `form_or_json()` dependency in `app/dependencies.py`:

```python
from app.dependencies import form_or_json

@router.post("/api/plants/")
async def create_plant(
    data: PlantCreate = Depends(form_or_json(PlantCreate)),
    ...
):
```

Use `Depends(form_or_json(Schema))` instead of a plain body parameter for any
endpoint called from HTML forms.

#### Important: trailing slashes

Form-encoded POST requests **require** a trailing slash in the URL. Without
it, Starlette issues a 307 redirect and the form data is lost. JSON POSTs don't
have this problem.

✅ `POST /api/plants/` — works with both JSON and form data
❌ `POST /api/plants` — works with JSON, 307 with form data

#### Endpoints using form_or_json

| Method | Path | Schema |
|--------|------|--------|
| POST | `/api/plants/` | `PlantCreate` |
| PUT | `/api/plants/{id}/` | `PlantUpdate` |
| POST | `/api/plants/{id}/archive` | `PlantArchive` |
| POST | `/api/plants/{pid}/tasks/` | `TaskCreate` |
| POST | `/api/plants/{pid}/tasks/{tid}/complete` | `TaskComplete` |
| POST | `/api/plants/{pid}/activity/` | `ActivityCreate` |

The `TaskComplete` schema has no required fields (empty body). The
`form_or_json` dependency handles this gracefully.

### Auth

- JWT-based. Token returned on login at `POST /api/auth/token` (OAuth2 password flow).
- Login endpoint uses FastAPI's `OAuth2PasswordRequestForm` (form data only,
  by design — it's called from the Swagger UI and the HTML login form).
- Protected endpoints use `Depends(get_current_user)`.
- The `AuthRedirectMiddleware` converts 401 responses to 302 redirects for
  HTML requests (browser users get sent to the login page instead of seeing
  JSON errors).

## Testing

### Structure

Tests live in `tests/`. Two test files:

- **`test_api.py`** — Integration tests against the live API using `httpx`
  `AsyncClient` + `ASGITransport`. Full CRUD flows, auth flows, edge cases.
  Uses an in-memory SQLite database reset per test.
- **`test_smoke.py`** — Lightweight smoke tests. Fast sanity checks.

### Fixtures

```python
# In tests/test_api.py — shared fixtures
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provides an authenticated test client with a fresh DB."""
    ...

async def auth_headers() -> dict:
    """Returns {'Authorization': 'Bearer <test-token>'}."""
    ...
```

### Guidelines

1. **No mocking** the database. Use the in-memory SQLite setup — it's fast
   enough and catches real SQL issues.
2. **Test both JSON and form data** for endpoints that accept both. Form data
   tests must include a trailing slash.
3. **Use descriptive test names.** A passing test suite should read like a
   changelog of capabilities.
4. **One assertion per logical concern.** Don't cram unrelated checks into
   one test.
5. **Don't test the framework.** Test your logic, not FastAPI/SQLAlchemy
   internals.

### CI

Every push/PR to `main` and `dev` runs:

1. **Compile check** — `python -m py_compile` on all app modules
2. **Tests** — `pytest tests/ -v --tb=short`
3. **Docker build** — Only if tests pass. Builds and pushes the image.

CI runs on GitHub Actions (`.github/workflows/test.yml`).

## Docker

### Multi-stage build

The Dockerfile has two stages:

1. **`css-build`** (Node.js) — Builds Tailwind CSS. Copies `package.json`,
   `tailwind.config.js`, `src/input.css`, and critically **`templates/`** so
   Tailwind can detect used utility classes. If templates are missing, the
   output CSS will be minimal (reset only).
2. **Runtime** (Python) — Runs the app via uvicorn.

### Volume mounts

Runtime-created directories (`/app/data/db`, `/app/data/photos`) are created
by `entrypoint.sh` because volume mounts overlay the image filesystem.

## Common Pitfalls

### CSS build produces minimal output

If the rendered app is unstyled but CSS loads without errors, the `output.css`
probably has only the Tailwind reset. This happens when:

- `templates/` is missing during the `css-build` Docker stage (Tailwind can't
  scan templates → no utility classes are generated).
- You forgot to run `npm run build:css` after adding new Tailwind classes to
  templates.

### 422 Unprocessable Entity on form submissions

The UI submits forms as `application/x-www-form-urlencoded`. If an endpoint
uses a plain Pydantic body parameter (JSON-only), you'll get a 422. Fix:
use `Depends(form_or_json(Schema))`.

### 307 Redirect on form POST

Starlette redirects POST requests without a trailing slash to add it. Form
data is lost in the redirect. Always include a trailing slash in form-POST
URLs.

---

*Last updated: 2026-05-02*