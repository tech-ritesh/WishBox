# Feature Comparison — Celebration Box vs WishBox

Legend: ✅ full · 🟡 partial/scaffolded · ❌ absent

| Feature | Celebration Box | WishBox | Notes |
|---|---|---|---|
| Product catalog + categories (tree) | ✅ | ✅ | WishBox adds soft-delete, sort order, SKU, vendor link |
| Product search & filter | ✅ | ✅ | + pagination, in-stock filter, rating sort |
| Tags / occasions | 🟡 (JSON in text) | ✅ | Real tags table + M2M, queryable |
| Cart | ✅ | ✅ | + server-computed subtotal & stock guard |
| Customization / personalization | ✅ | ✅ | gift message + custom details on cart & order |
| Checkout & orders | ✅ | ✅ | structured shipping, shipping fee, gift flags |
| **Inventory decrement on order** | ❌ | ✅ | + StockMovement ledger, oversell prevention |
| Coupons & discounts | ✅ | ✅ | flat + %, usage/per-user limits, redemption tracking |
| Coupon management (admin) | ✅ | ✅ | |
| **Order tracking timeline** | 🟡 (status string + action log) | ✅ | full status history, customer-visible |
| Wishlist | ✅ | ✅ | |
| Celebration reminders | ✅ | ✅ | + recurrence |
| **Scheduled deliveries** | ❌ | ✅ | date + slot (incl. midnight) on order |
| Reviews & ratings | ✅ | ✅ | + verified-purchase flag, rating aggregate, one-per-user |
| Customer profiles & addresses | ✅ | ✅ | structured multi-line addresses |
| Festivals / campaigns | ✅ | ✅ | |
| Homepage collections | ✅ | ✅ | |
| Admin dashboard + analytics | ✅ (monolith) | ✅ | revenue, by-category, monthly, by-status, low-stock |
| **Smart hamper builder** | 🟡 (customizer) | ✅ | composable multi-product hampers + templates |
| AI gift suggestions | 🟡 (keyword rules) | ✅ + 🟡 LLM | local tag-aware engine; optional LLM hook |
| Occasion-based recommendations | 🟡 | ✅ | tag-driven |
| **Vendor / supplier management** | ❌ | ✅ | vendor CRUD + product linkage, lead time |
| **Notification system** | ❌ | ✅ (in-app) + 🟡 email | in-app notifications built; email = documented extension |
| **Corporate gifting module** | ❌ | 🟡 | CorporateAccount model + member discount applied at checkout; bulk-order UI documented |
| Role-based access control | 🟡 (admin/customer) | ✅ | customer / staff / admin |
| Refresh tokens | ❌ | ✅ | |
| Pagination | ❌ | ✅ | |
| Migrations (Alembic) | ❌ | ✅ | |
| Automated tests | ❌ | 🟡 | smoke tests + structure |

## Net-new in WishBox
Inventory ledger · order status timeline · scheduled delivery · vendor management ·
in-app notifications · corporate accounts · smart hamper builder · refresh tokens ·
pagination · Alembic · RBAC with a staff tier · Decimal money · validated uploads.
