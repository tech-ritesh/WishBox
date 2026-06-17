# WishBox 🎁

A **local-first** gift & hamper platform — the next-generation successor to *Celebration Box*.
Order gifts and hampers for birthdays, anniversaries, weddings, festivals and corporate events,
with personalization, a smart hamper builder, scheduled delivery, wishlists, order tracking,
inventory & vendor management, an admin dashboard with analytics, and a local recommendation engine.

Everything runs on your machine. No cloud services required (SQLite database, local file uploads).

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI · SQLAlchemy 2.0 · Pydantic v2 · Alembic · JWT (access + refresh) |
| Database | SQLite (WAL mode, FK enforcement) — swap to Postgres via one env var |
| Frontend | React 18 · Vite · Tailwind CSS · Axios |
| Auth | JWT access + refresh tokens, RBAC (`customer` / `staff` / `admin`) |

## Prerequisites
- Python 3.11+
- Node.js 18+

---

## Quick start

### 1. Backend (port 8000)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then edit WISHBOX_SECRET_KEY
python seed.py                  # demo data + accounts
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Health: http://localhost:8000/api/health
- Interactive API docs (Swagger): http://localhost:8000/docs

### 2. Frontend (port 5173)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api` and `/static` to the backend.

> **Start the backend before the frontend.** If the shop is empty, the backend isn't running.

---

## Demo accounts (after `python seed.py`)

| Role | Email | Password |
|---|---|---|
| Admin | admin@wishbox.com | admin12345 |
| Staff | staff@wishbox.com | staff12345 |
| Customer | customer@wishbox.com | customer123 |

---

## Configuration (`backend/.env`)

| Var | Purpose |
|---|---|
| `WISHBOX_SECRET_KEY` | JWT signing key (**required** in production) |
| `WISHBOX_ENV` | `development` or `production` (prod refuses the default key) |
| `WISHBOX_DATABASE_URL` | defaults to `sqlite:///./wishbox.db`; set a Postgres URL to scale |
| `WISHBOX_ACCESS_TOKEN_MINUTES` / `WISHBOX_REFRESH_TOKEN_DAYS` | token lifetimes |
| `WISHBOX_CORS_ORIGINS` | comma-separated allowed origins |
| `WISHBOX_LLM_API_KEY` | optional — enables LLM gift suggestions (left blank = local engine) |

---

## Database migrations (Alembic)

For local dev the app auto-creates tables on startup. For real schema evolution use Alembic
(no hand-rolled `ALTER TABLE` like the reference project):

```powershell
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

---

## Project layout

```
WishBox/
├─ PROGRESS.md            # build status & "resume here" guide
├─ README.md              # this file
├─ docs/                  # architecture, schema, API, comparison, issues, UX, scalability
├─ backend/
│  ├─ app/
│  │  ├─ core/            # config, database, security
│  │  ├─ models/          # SQLAlchemy ORM
│  │  ├─ schemas/         # Pydantic request/response
│  │  ├─ services/        # business logic (orders, coupons, recommendations)
│  │  └─ api/routers/     # HTTP endpoints
│  ├─ seed.py
│  └─ requirements.txt
└─ frontend/
   └─ src/ (api, context, components, pages)
```

See **`docs/`** for the full architecture, database schema, API design, the Celebration Box
issues we fixed, a feature comparison, UI/UX recommendations, and scalability guidance.
See **`PROGRESS.md`** for build status and how to continue the build.
