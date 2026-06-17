# WishBox — Build Progress & Continuation Guide

> **This is the master "resume here" document.** Open it first in any new session.
> It records what is DONE, what is PENDING, and exactly where to continue + file locations.

**Project root:** `C:\WishBox`
**Reference project:** `C:\Users\USER\.gemini\antigravity\scratch\celebration_box` (read-only reference)
**Stack:** FastAPI + SQLAlchemy 2.0 + SQLite (backend), React 18 + Vite + Tailwind (frontend). Local-first.

**STATUS: Backend + Frontend are COMPLETE and VERIFIED runnable.** Backend: 5/5 pytest pass + live
HTTP confirmed. Frontend: production build passes (1564 modules, exit 0). A short list of optional /
deferred items remains (see "Remaining work").

---

## How to run

```powershell
# Backend (terminal 1)
cd C:\WishBox\backend
.\.venv\Scripts\Activate.ps1          # venv already created & deps installed
python seed.py                        # demo data (already seeded once)
uvicorn app.main:app --reload --port 8000
#   docs: http://localhost:8000/docs   health: http://localhost:8000/api/health

# Frontend (terminal 2)
cd C:\WishBox\frontend
npm run dev                           # http://localhost:5173  (node_modules installed)
```
Demo accounts: admin@wishbox.com/admin12345 · staff@wishbox.com/staff12345 · customer@wishbox.com/customer123

---

## How to resume / continue the build
Tell the assistant:
> "Continue building WishBox from `C:\WishBox\PROGRESS.md`. Start at the first unchecked item under 'Remaining work'."

---

## Roadmap / Status
Legend: `[x]` done & verified · `[~]` partial/scaffolded · `[ ]` not started

### Phase 0 — Docs ✅ COMPLETE
- [x] PROGRESS.md · README.md
- [x] docs/ARCHITECTURE.md · DATABASE_SCHEMA.md · API_DESIGN.md
- [x] docs/FEATURE_COMPARISON.md · CELEBRATIONBOX_ISSUES.md · UIUX_RECOMMENDATIONS.md · SCALABILITY.md

### Phase 1 — Backend ✅ COMPLETE & VERIFIED (5/5 tests pass, live HTTP confirmed)
- [x] core: config (refuses insecure secret in prod), database (WAL+FK), security (access+refresh JWT)
- [x] models — all 24 entities · schemas (pydantic v2)
- [x] services — common, coupons, orders+inventory, recommendations
- [x] api/deps (RBAC: require_staff/require_admin)
- [x] routers — auth, products, categories, cart, orders, engagement, hampers, storefront, admin
- [x] main.py · seed.py · requirements.txt · .env.example · tests/test_smoke.py

### Phase 2 — Frontend ✅ COMPLETE (build passes)
- [x] vite/tailwind/postcss config, package.json, index.html
- [x] api client (auto-refresh interceptor), AuthContext, CartContext
- [x] pages: Home, Shop, ProductDetails, Cart, Checkout, Login, Register, Account, Orders, OrderTracking, Wishlist, GiftFinder, HamperBuilder
- [x] admin: AdminLayout, AdminDashboard, AdminProducts, AdminOrders, AdminCoupons
- [x] route guards, spinners, empty states

### Phase 3 — Enhanced modules
- [x] Occasion-based recommendations · Gift personalization/messages · Smart hamper builder
- [x] Wishlist · Scheduled deliveries · Order tracking timeline · Customer profiles
- [x] Coupon management · Admin dashboard+analytics · Inventory ledger · Vendor management
- [x] Notifications (in-app) · Reviews & ratings · AI gift suggestions (local engine)
- [~] Corporate gifting (model + checkout discount done; admin UI + bulk-order flow pending)

---

## Remaining work (START HERE next session, in priority order)
1. [ ] **Alembic migrations** — backend currently auto-creates tables via `Base.metadata.create_all`
   in `main.py`. To add: `cd backend; alembic init alembic`; point `alembic/env.py` at
   `app.core.database.Base.metadata` and `settings.DATABASE_URL`; `alembic revision --autogenerate`.
2. [ ] **Corporate gifting admin UI + bulk orders** — model `CorporateAccount` exists and its discount
   is applied in `services/orders.place_order`. TODO: admin CRUD endpoints for corporate accounts,
   a bulk/multi-recipient order endpoint, and a frontend corporate page.
3. [ ] **Email/SMS notifications** — in-app `Notification` works; wire a background worker (see
   docs/SCALABILITY.md §3) for email/SMS on order + reminder events.
4. [ ] **LLM gift suggestions** — implement `services/recommendations.llm_rerank()` (hook exists,
   returns None unless `WISHBOX_LLM_API_KEY` set). Use Claude structured output; fall back to local engine.
5. [ ] **Payments** — add `services/payments.py` adapter (Stripe/Razorpay) + webhook; fields already modeled.
6. [ ] **Frontend polish** — toast system, skeleton loaders, `React.lazy` admin code-split, product image gallery.
7. [ ] **Cleanup (non-blocking)** — replace remaining `datetime.utcnow()` with timezone-aware calls;
   `Query.get()` → `Session.get()`. Harmless deprecation warnings only.
8. [ ] **More tests** — expand pytest beyond the smoke suite; add CI.

---

## Deliverables checklist (from the brief) — ALL DELIVERED
- [x] System architecture → docs/ARCHITECTURE.md
- [x] Database schema → docs/DATABASE_SCHEMA.md
- [x] Feature comparison → docs/FEATURE_COMPARISON.md
- [x] Identified issues in Celebration Box → docs/CELEBRATIONBOX_ISSUES.md
- [x] Improved UI/UX recommendations → docs/UIUX_RECOMMENDATIONS.md
- [x] Complete source code structure → this repo (backend/ + frontend/)
- [x] API design → docs/API_DESIGN.md (+ live Swagger at /docs)
- [x] Local database implementation → SQLite (Alembic = item 1 above)
- [x] Installation & setup guide → README.md
- [x] Future scalability recommendations → docs/SCALABILITY.md

---

## Key design decisions (keep consistent across sessions)
1. **Layered**: `api/` (HTTP) → `services/` (logic) → `models/` (ORM). No business logic in routers.
2. **Money**: `Numeric(10,2)` Decimal, never float. Prod rec: integer minor units.
3. **Auth**: access + refresh JWT; RBAC enum customer/staff/admin. No auto-admin-on-first-user.
4. **Secrets**: `SECRET_KEY` from `.env`; prod refuses the placeholder.
5. **Migrations**: Alembic (no hand-rolled ALTER).
6. **Tags**: real `tags` table + `product_tags` M2M.
7. **Inventory**: stock decremented in the order transaction + `StockMovement` ledger.
8. **Order tracking**: `OrderStatusHistory` = customer timeline + audit trail.
9. **API**: `/api/v1`, paginated lists, consistent `{detail}` errors.

## Session log
- Session 4 (2026-06-17): **Admin product edit + customizable visibility.**
  - Fixed regression: admin products page hung on "Loading…" because it fetched `limit:200`
    (backend cap is 100). Now `limit:100` + graceful `.catch`.
  - `AdminProducts.jsx`: added **Edit** (pencil) per row → pre-fills the form (incl. category cascade)
    and saves via `PUT /admin/products/{id}`; added a **Customizable** toggle to the form and a
    "Custom" column to the table.
  - Customer clarity on customizable: **"✨ Customizable" badge** on `ProductCard` + a labelled
    section on `ProductDetails` with an optional **personal message** that flows into the cart item
    and order item (shown in Cart + OrderTracking).
  - Tests: added `test_admin_can_edit_existing_product` + `test_customization_message_flows_to_cart`
    → **10/10 pytest pass**. Build passes; live dev server serves all updated modules.
- Session 3 (2026-06-17): **Admin product form now shows category + sub-category.**
  - `frontend/src/pages/admin/AdminProducts.jsx`: replaced the flat alphabetical category dropdown
    with **cascading selects (Category → Sub-category → Item)** driven by `/categories/tree`; shows
    the resolved full path; product table now shows the full category path. Frontend-only change —
    no data/categories/backend logic removed.
  - Added pytest `test_admin_create_product_under_leaf_category` (8/8 pass): proves a product assigned
    to a leaf lands on that leaf and surfaces under its top-level parent; self-cleans.
  - Verified: build passes, both servers live, demo store unchanged (Birthday=21).
- Session 2 (2026-06-17): **Added full category hierarchy** (user noted WishBox lacked CB's
  categories/sub-categories). Now mirrors Celebration Box:
  - `Category` model: added `mega_menu_group` + `is_badge_new`; made `name` non-unique (slug is the
    unique key) so sub-category names can repeat across the tree.
  - New `GET /api/v1/categories/tree` (nested parent→sub→leaf). `CategoryTreeOut` schema added.
  - `seed.py` rebuilt: catalog reset + 3-level hierarchy (6 parents → 37 subs → ~160 leaves = 207
    categories) + 80 generated products spread across leaves. Re-seed clears demo orders too.
  - Frontend: Navbar mega-menu, new `CategoryLanding` page (`/category/:slug` with sub-cat sidebar),
    Shop parent+sub-category dropdowns, Home occasion chips → `/category/:slug`.
  - Verified: 7/7 pytest pass; frontend build passes; live tree + descendant filtering (Birthday→21
    products, Flowers→13). Both servers running (8000 / 5173).
- Session 1 (2026-06-17):
  - Analyzed Celebration Box end-to-end; wrote all 8 docs.
  - Built & verified full backend (24 models, services, all routers) — 5/5 pytest pass + live HTTP OK.
  - Built & verified full frontend (storefront + admin) — production build passes.
  - Seeded demo data. venv + node_modules installed.
  - Remaining: see "Remaining work" (Alembic, corporate UI, email/LLM/payments, polish).
