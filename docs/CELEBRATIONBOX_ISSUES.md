# Celebration Box — Identified Issues & How WishBox Addresses Them

This is the audit of the reference project (`celebration_box`) that drove the WishBox design.

## 1. Security

| # | Issue (Celebration Box) | Risk | WishBox fix |
|---|---|---|---|
| S1 | Hardcoded default `SECRET_KEY` in `config.py`, committed to repo | Token forgery | Secret from `.env`; app **refuses to start in production** with the default |
| S2 | JWT stored in `localStorage` | XSS token theft | Short-lived access token + refresh token; documented httpOnly-cookie upgrade path |
| S3 | **First registered user silently becomes admin** | Privilege escalation | Removed; roles are explicit (`customer`/`staff`/`admin`), admin is seeded |
| S4 | No rate limiting / lockout, 7-day access tokens | Brute force | 30-min access tokens + refresh rotation; rate-limit hook documented |
| S5 | Image upload without type/size validation surfaced | Malicious upload / disk fill | Content-type allowlist + 5 MB cap + random filenames |
| S6 | Broad `except Exception: pass` swallowing errors (e.g. registration coupon) | Silent data loss | Explicit error handling; transactional integrity |

## 2. Data model

| # | Issue | Impact | WishBox fix |
|---|---|---|---|
| D1 | Money stored as `Float` | Rounding errors on currency math | `Numeric(10,2)` (Decimal) everywhere |
| D2 | `tags`/`emotions` = JSON inside a `Text` column | Can't index or query reliably | Real `tags` table + `product_tags` M2M |
| D3 | **Stock never decremented on order** | Oversell, inaccurate inventory | Stock decremented in the order transaction + `StockMovement` ledger |
| D4 | Shipping address flattened to a text blob on the order | Lost structure, can't analyze | Structured shipping snapshot columns |
| D5 | No `updated_at`, no soft-delete; cascade delete of product wipes order history | Data loss / audit gaps | `created_at`/`updated_at` everywhere; soft-delete (`is_active`) on catalog |
| D6 | No vendor/supplier, notification, scheduled-delivery, corporate models | Missing domains | Added `Vendor`, `Notification`, scheduled-delivery fields, `CorporateAccount`, `Hamper` |

## 3. Architecture & code quality

| # | Issue | Impact | WishBox fix |
|---|---|---|---|
| A1 | `AdminDashboard.jsx` is **228 KB in one file** | Unmaintainable | Modular admin pages/components |
| A2 | Business logic inline in route handlers (pricing+coupons in `orders.py`) | Hard to test/reuse | Dedicated `services/` layer |
| A3 | No Alembic; hand-rolled raw `ALTER TABLE` in `run_light_migrations()` | Fragile, irreversible | Alembic migrations |
| A4 | ~12 stray `check_*.py` / `migrate_*.py` scripts in backend root | Tech debt clutter | Single `seed.py`; clean structure |
| A5 | No automated tests, no enforced lint/CI | Regressions slip through | `pytest` smoke tests; structure ready for CI |

## 4. Functionality / UX

| # | Issue | WishBox fix |
|---|---|---|
| F1 | No pagination — `query.all()` returns everything | `limit`/`offset` pagination with totals |
| F2 | "AI" suggestions are keyword heuristics only | Cleaner tag-aware engine + documented optional LLM hook |
| F3 | Order tracking is a single status string | `OrderStatusHistory` timeline (customer-facing + audit) |
| F4 | No real scheduled delivery, corporate, or notification features | All modeled and wired |
| F5 | Inconsistent error handling, no standard envelope | Central exception handler + consistent errors |

## 5. Performance / scalability

| # | Issue | WishBox fix |
|---|---|---|
| P1 | N+1 query risk, no eager loading | `joinedload` on hot paths |
| P2 | No indexes beyond PK/unique | Indexed FKs and lookup columns |
| P3 | Synchronous only; no job queue for emails/notifications | In-app notifications now; background-worker path documented (see SCALABILITY.md) |
| P4 | SQLite default journal | WAL mode + FK enforcement enabled |
