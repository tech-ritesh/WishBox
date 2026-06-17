# WishBox — API Design

Base URL: `/api/v1` · Interactive docs (live): `http://localhost:8000/docs` (Swagger/OpenAPI, auto-generated).

## Conventions
- **Versioned** prefix `/api/v1`.
- **Auth**: `Authorization: Bearer <access_token>`. Obtain via `/auth/login-json`; refresh via `/auth/refresh`.
- **Pagination**: list endpoints accept `limit` (1–100) & `offset`; product list returns `{total, limit, offset, items}`.
- **Errors**: `{"detail": "..."}` with appropriate HTTP status (400 validation, 401 auth, 403 RBAC, 404 missing, 409 conflict/stock).
- **Money**: Decimal strings/numbers (e.g. `"749.00"`).

## Auth & profile
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | – | Create account → token pair |
| POST | `/auth/login` | – | OAuth2 form login (Swagger) |
| POST | `/auth/login-json` | – | JSON login → token pair |
| POST | `/auth/refresh` | – | Exchange refresh token for new pair |
| GET | `/auth/profile` | user | Current profile |
| PUT | `/auth/profile` | user | Update name/phone/password |
| GET/POST | `/auth/addresses` | user | List / add address |
| DELETE | `/auth/addresses/{id}` | user | Remove address |

## Catalog
| Method | Path | Purpose |
|---|---|---|
| GET | `/products` | List + filter (`category, tag, occasion, q, price_min, price_max, customizable, type, in_stock, sort, limit, offset`) |
| GET | `/products/{slug}` | Detail (images, tags, category) |
| GET | `/products/quick-delivery` | Express-eligible products |
| GET | `/categories` · `/categories/{slug}` | Categories |

## Cart & orders
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET/POST/DELETE | `/cart` | user | View / add / clear cart |
| PUT/DELETE | `/cart/{id}` | user | Update / remove line |
| POST | `/orders` | user | Place order (inventory + coupon + timeline) |
| GET | `/orders` | user | My orders |
| GET | `/orders/{order_number}` | user | Order detail + tracking history |

## Engagement
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/coupons/validate` | user | Validate coupon vs subtotal |
| GET/POST | `/reviews/{product_id}` · `/reviews` | mixed | List / create review |
| GET/POST/DELETE | `/wishlist` … | user | Wishlist |
| GET/POST/DELETE | `/reminders` … | user | Celebration reminders |
| GET/POST | `/notifications` … | user | In-app notifications |
| POST | `/recommendations/smart` | – | Gift finder (local engine) |
| GET/POST/DELETE | `/hampers` · `/hampers/templates` | mixed | Smart hamper builder |

## Storefront
| Method | Path | Purpose |
|---|---|---|
| GET | `/festivals/active` | Live festival campaigns |
| GET | `/collections/active` · `/collections/{slug}` | Homepage collections |

## Admin / staff (RBAC)
| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/admin/analytics` | staff | Revenue, by-category, monthly, by-status, low-stock |
| GET | `/admin/customers` | staff | Customers + order count/spend |
| GET/PUT | `/admin/orders` · `/admin/orders/{id}` | staff | List / update status (writes timeline + restocks on cancel) |
| POST/PUT/DELETE | `/admin/products[/{id}]` | staff/admin | Catalog CRUD (delete = soft) |
| POST/PUT/DELETE | `/admin/categories[/{id}]` | staff/admin | Category CRUD |
| GET/POST/DELETE | `/admin/coupons[/{id}]` | staff/admin | Coupon CRUD |
| GET/POST | `/admin/vendors` | staff/admin | Vendor management |
| GET | `/admin/inventory/low-stock` | staff | Low-stock report |
| POST | `/admin/upload` | staff | Validated image upload (type + 5 MB cap) |

## Example: place an order
```http
POST /api/v1/orders
Authorization: Bearer <token>
{
  "address_id": 1,
  "payment_method": "cod",
  "coupon_code": "WELCOME10",
  "is_gift": true,
  "gift_message": "Happy Birthday!",
  "scheduled_delivery_date": "2026-07-01",
  "delivery_slot": "18:00-21:00"
}
```
Response `201`: full order with `status`, `total_amount`, `items[]`, `history[]`.
