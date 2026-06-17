# WishBox — System Architecture

## Overview

WishBox is a **local-first**, layered full-stack application.

```
┌──────────────────────────────────────────────────────────┐
│  Browser (React 18 + Vite + Tailwind)                      │
│   pages ─ components ─ context (Auth, Cart) ─ api client   │
└───────────────┬────────────────────────────────────────────┘
                │  HTTP/JSON  (Vite proxy /api → :8000)
┌───────────────▼────────────────────────────────────────────┐
│  FastAPI app  (app/main.py)                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  api/routers/   ← HTTP layer (validation, status codes)│  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  services/      ← business logic (orders, coupons, rec)│  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  models/        ← SQLAlchemy ORM                       │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  core/          ← config, security (JWT), database     │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────┬────────────────────────────────────────────┘
                │  SQLAlchemy
┌───────────────▼────────────────────────────────────────────┐
│  SQLite (WAL, FK enforcement)  +  /static/uploads (files)   │
└──────────────────────────────────────────────────────────────┘
```

## Layering rules
1. **Routers** only parse/validate input, call a service or do a trivial query, and shape the response. No pricing/inventory logic in routers.
2. **Services** own multi-step business logic and transactions (`services/orders.py`, `coupons.py`, `recommendations.py`).
3. **Models** are persistence only. Derived helpers (e.g. `Product.effective_price`) are pure.
4. **Core** is cross-cutting: settings, DB session/engine, password hashing & JWT.

## Request flow (place order)
`POST /api/v1/orders`
→ `deps.get_current_user` (JWT) → `routers/orders.create_order`
→ `services/orders.place_order`:
  validate cart & stock → price lines → evaluate coupon (`services/coupons`) →
  apply corporate discount → create `Order` + `OrderItem`s → **decrement stock + StockMovement** →
  write `OrderStatusHistory` → record `CouponRedemption` → create `Notification` → clear cart → commit.

## Authentication & authorization
- Login issues an **access token** (30 min) and a **refresh token** (14 days), both JWT.
- `POST /auth/refresh` exchanges a valid refresh token for a new pair.
- RBAC via `User.role` enum: `customer` < `staff` < `admin`.
  - `require_staff` guards catalog/order management.
  - `require_admin` guards destructive ops (delete, vendor create, coupon delete).

## Configuration & secrets
- `app/core/config.py` reads `WISHBOX_*` env vars (prefix) from `.env`.
- Production startup **fails** if `SECRET_KEY` is still the placeholder.

## Local-first guarantees
- SQLite file DB, local filesystem uploads, no outbound calls by default.
- The only optional external dependency is an LLM key for richer gift suggestions — off unless `WISHBOX_LLM_API_KEY` is set; the local engine is always the fallback.

## Extension points
- **Migrations**: Alembic (`alembic/`), autogenerate from models.
- **Background jobs**: `services/` functions are queue-ready; see SCALABILITY.md for the worker pattern (reminders → notifications, email).
- **Payments**: `order.payment_method`/`payment_status` already modeled; plug a gateway adapter in a `services/payments.py`.
- **LLM suggestions**: `services/recommendations.llm_rerank()` is the hook.
