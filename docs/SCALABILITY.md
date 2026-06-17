# WishBox — Future Scalability Recommendations

WishBox is local-first by design, but the architecture is built so each piece can scale without a rewrite.

## 1. Database: SQLite → PostgreSQL
- All money is `Numeric`, models are dialect-neutral, and Alembic manages schema.
- To scale: set `WISHBOX_DATABASE_URL=postgresql+psycopg://user:pass@host/wishbox`, run `alembic upgrade head`. No code change.
- Add connection pooling (`pool_size`, `max_overflow`) for Postgres.
- **Production money**: migrate `Numeric(10,2)` → integer minor units (paise) for exact arithmetic at scale.

## 2. Caching & read scaling
- Add Redis for: product list/detail caching, session/rate-limit counters, cart for guests.
- Cache invalidation on product/category/coupon writes (event-driven via the service layer).
- Read replicas for analytics queries; precompute the admin summary into a materialized table on a schedule.

## 3. Background jobs (async work)
The service layer is already the natural seam. Introduce a worker (Celery/RQ/APScheduler) for:
- **Reminder notifications** — daily job scanning `reminders.reminder_date` → create `Notification` + email.
- **Email/SMS** — order confirmations, shipping updates (currently in-app `Notification` only).
- **Scheduled-delivery dispatch** — promote orders to "out_for_delivery" on the slot date.
- **Inventory reorder** — when stock ≤ threshold, notify the linked `Vendor`.

```
API (FastAPI) ──enqueue──> Broker (Redis) ──> Worker(s) ──> DB / Email / SMS
```

## 4. Payments
- `order.payment_method` / `payment_status` already modeled. Add `services/payments.py` with a provider adapter interface (Stripe/Razorpay), and a `payment_intents` table + webhook endpoint. Keep COD as the offline default.

## 5. AI gift suggestions (optional, opt-in)
- Hook: `services/recommendations.llm_rerank()`. When `WISHBOX_LLM_API_KEY` is set, send the parsed intent + candidate products to Claude and have it rank + explain.
- Recommended: Anthropic Claude with structured tool-use returning `{product_id, reason}`; fall back to the local engine on error/timeout so the app stays functional offline.
- Add a vector index (e.g. `sqlite-vss` locally, `pgvector` in Postgres) on product descriptions for semantic search.

## 6. API & delivery
- Stateless API → run N replicas behind a load balancer; JWT means no server session affinity.
- Rate limiting (per-IP/user) via Redis token bucket; add account lockout + CAPTCHA on repeated auth failures.
- Move JWT to httpOnly + Secure + SameSite cookies with CSRF tokens for browser clients.
- Serve `/static` uploads from object storage (S3/MinIO) + CDN once beyond a single machine.

## 7. Observability & quality
- Structured logging (request id, user id), `/metrics` (Prometheus), tracing (OpenTelemetry).
- Expand the `pytest` suite; add CI (lint + tests on PR). Contract tests against the OpenAPI schema.
- Feature flags for gradual rollout of new modules (corporate gifting, AI).

## 8. Multi-tenancy / marketplace direction
- `Vendor` + `CorporateAccount` already seed a marketplace/B2B path: per-vendor catalogs, vendor payouts, corporate bulk orders with approval workflows and invoicing.

## Scaling ladder (summary)
| Stage | Setup |
|---|---|
| Local / demo | SQLite + single uvicorn + Vite (this repo) |
| Small prod | Postgres + gunicorn/uvicorn workers + Nginx + built frontend |
| Growth | + Redis cache + background worker + object storage/CDN |
| Scale | + read replicas + LB'd API replicas + observability + optional vector search / LLM |
