# WishBox — Database Schema

SQLite (local) / Postgres-compatible. Money is `Numeric(10,2)`. Timestamps on every core table.
Source of truth: `backend/app/models/__init__.py`.

## Entity overview

```
User ─┬─< Address
      ├─< Order ─┬─< OrderItem >── Product
      │          └─< OrderStatusHistory
      ├─< CartItem >── Product
      ├─< Review >── Product
      ├─< WishlistItem >── Product
      ├─< Reminder
      ├─< Notification
      ├─< Hamper ─< HamperItem >── Product
      └── CorporateAccount (many users → one account)

Category ─< Category (self-ref tree)
Category ─< Product >── Vendor
Product  >─< Tag        (product_tags M2M)
Product  ─< ProductImage
Product  ─< StockMovement
Coupon   ─< CouponRedemption
FestivalCampaign · HomepageCollection · AuditLog
```

## Tables

### users
`id, email (uniq), password_hash, full_name, phone, role(enum: customer/staff/admin), is_active, email_verified, last_login_at, corporate_account_id→corporate_accounts, created_at, updated_at`

### addresses
`id, user_id→users, title, recipient_name, phone, address_line1, address_line2, city, state, postal_code, country, is_default`

### categories  (self-referential 3-level tree: parent → sub-category → leaf)
`id, name(indexed; NOT unique — names repeat across the tree), slug(uniq), description, image_url, occasion_group, parent_id→categories, sort_order, is_active, mega_menu_group (groups sub-cats in the mega-menu), is_badge_new`
Seeded hierarchy: 6 parents (Birthday, Anniversary, Occasions, Flowers, Festive Sale, Corporate) → ~37 sub-categories → ~160 leaf categories. `GET /categories/tree` returns it nested; product filtering by any node includes all descendants.

### tags  /  product_tags (M2M)
`tags: id, name(uniq), kind(occasion/emotion/recipient/general)` · `product_tags: product_id, tag_id`

### vendors
`id, name(uniq), contact_email, contact_phone, lead_time_days, is_active`

### products
`id, sku(uniq), name, slug(uniq), description, price(Numeric), discount_price(Numeric), currency, image_url, stock, low_stock_threshold, category_id→categories, vendor_id→vendors, is_customizable, type(hamper/addon/personalized/combo), is_quick_delivery, is_active, rating_avg, rating_count, view_count`

### product_images
`id, product_id→products, image_url, sort_order`

### stock_movements  (inventory ledger)
`id, product_id→products, change(±int), reason(order/restock/adjustment/cancel), reference, created_at`

### cart_items
`id, user_id→users, product_id→products, quantity, customization_details(JSON)`

### hampers / hamper_items  (smart builder)
`hampers: id, user_id→users(nullable for templates), name, occasion, box_style, gift_message, is_template`
`hamper_items: id, hamper_id→hampers, product_id→products, quantity`

### orders
`id, user_id→users, order_number(uniq), subtotal, discount_amount, shipping_fee, total_amount, recipient_name, recipient_phone, ship_address_line1/2, ship_city, ship_state, ship_postal_code, ship_country, is_gift, gift_message, scheduled_delivery_date, delivery_slot, payment_method, payment_status(enum), status(enum), tracking_code, coupon_code`

`status` enum: pending → confirmed → packed → shipped → out_for_delivery → delivered (· cancelled · refunded)

### order_items
`id, order_id→orders, product_id→products, product_name(snapshot), unit_price, quantity, customization_details(JSON)`

### order_status_history  (tracking timeline + audit)
`id, order_id→orders, status, note, changed_by_id→users, created_at`

### coupons / coupon_redemptions
`coupons: id, code(uniq), description, discount_type(percentage/flat), discount_value, max_discount, min_order_value, expiry_date, usage_limit, per_user_limit, times_used, active`
`coupon_redemptions: id, coupon_id→coupons, user_id→users, order_id→orders, redeemed_at`

### reviews
`id, user_id→users, product_id→products, rating(1-5), comment, verified_purchase, helpful_count` — UNIQUE(user_id, product_id)

### wishlist_items
`id, user_id, product_id` — UNIQUE(user_id, product_id)

### reminders
`id, user_id→users, title, occasion, recipient_name, reminder_date, recurrence(none/yearly/monthly), notes, notified`

### notifications
`id, user_id→users, type(order/promo/reminder/info), title, body, link, is_read, created_at`

### corporate_accounts
`id, company_name(uniq), gst_number, billing_email, credit_limit, discount_percentage, is_active`

### festival_campaigns
`id, name, slug(uniq), description, banner_image_url, theme_color, start_date, end_date, discount_percentage, coupon_code, active`

### homepage_collections
`id, title, slug(uniq), description, image_url, display_order, is_active, product_ids(JSON)`

### audit_logs
`id, actor_id→users, action, entity, entity_id, detail(JSON), created_at`

## Indexing
PKs, all `slug`/`code`/`email`/`order_number` unique columns, and FK columns on hot paths (`products.category_id`, `orders.user_id`, `order_status_history.order_id`, `notifications.user_id`) are indexed.

## Production note
For high-volume money correctness, store integer **minor units** (paise) instead of `Numeric`.
`Numeric(10,2)` is the pragmatic local-first choice and already eliminates the float bug from the reference project.
