"""End-to-end smoke test of the core WishBox flow.

Run:  python -m pytest -q     (from the backend folder, after `python seed.py`)
"""
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app import models

client = TestClient(app)


def _latest_token(email, kind):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        row = (
            db.query(models.AuthToken)
            .filter(models.AuthToken.user_id == user.id, models.AuthToken.kind == kind)
            .order_by(models.AuthToken.id.desc())
            .first()
        )
        return row.token
    finally:
        db.close()


def _login(email, password):
    r = client.post("/api/v1/auth/login-json", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_products_paginated():
    r = client.get("/api/v1/products?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body and "items" in body
    assert body["total"] >= 1


def test_customer_order_flow():
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}

    # add an address
    addr = client.post("/api/v1/auth/addresses", headers=h, json={
        "recipient_name": "Test", "phone": "9999999999",
        "address_line1": "1 Test St", "city": "Pune", "state": "MH", "postal_code": "411001",
    })
    assert addr.status_code == 201, addr.text
    address_id = addr.json()["id"]

    # pick a product, add to cart
    product = client.get("/api/v1/products?limit=1").json()["items"][0]
    cart = client.post("/api/v1/cart", headers=h, json={"product_id": product["id"], "quantity": 2})
    assert cart.status_code == 201, cart.text
    assert cart.json()["item_count"] == 2

    # stock before
    stock_before = product["stock"]

    # place order
    order = client.post("/api/v1/orders", headers=h, json={
        "address_id": address_id, "payment_method": "cod",
        "is_gift": True, "gift_message": "Happy Birthday!",
    })
    assert order.status_code == 201, order.text
    o = order.json()
    assert o["status"] == "confirmed"
    assert len(o["history"]) >= 1
    assert o["items"][0]["quantity"] == 2

    # stock decremented
    after = client.get(f"/api/v1/products/{product['slug']}").json()
    assert after["stock"] == stock_before - 2


def test_admin_analytics_requires_staff():
    assert client.get("/api/v1/admin/analytics").status_code == 401
    token = _login("admin@wishbox.com", "admin12345")
    r = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert "total_revenue" in r.json()


def test_customer_cannot_access_admin():
    token = _login("customer@wishbox.com", "customer123")
    r = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_category_tree_is_nested():
    r = client.get("/api/v1/categories/tree")
    assert r.status_code == 200, r.text
    roots = r.json()
    assert len(roots) >= 1
    # at least one root has children, and at least one child has its own children (3 levels)
    parent = next(c for c in roots if c["children"])
    assert parent["children"]
    sub = next((c for c in parent["children"] if c["children"]), None)
    assert sub is not None and sub["children"], "expected a 3-level hierarchy"


def test_products_filter_includes_descendants():
    # 'birthday' is a top-level parent; products live in its descendant leaf categories.
    r = client.get("/api/v1/products?category=birthday&limit=100")
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1, "parent category should surface products from descendant leaves"


def _find_leaf(tree):
    """Return the first leaf node (no children) and its top-level parent slug."""
    for parent in tree:
        for sub in parent.get("children", []):
            for leaf in sub.get("children", []):
                return leaf, parent["slug"]
    return None, None


def test_admin_create_product_under_leaf_category():
    """Mirrors the admin cascade form: assign a product to a leaf category and
    confirm it lands on that leaf AND shows up when browsing the top-level parent."""
    token = _login("admin@wishbox.com", "admin12345")
    h = {"Authorization": f"Bearer {token}"}

    tree = client.get("/api/v1/categories/tree").json()
    leaf, parent_slug = _find_leaf(tree)
    assert leaf and parent_slug, "expected a 3-level hierarchy with a leaf"

    before = client.get(f"/api/v1/products?category={parent_slug}&limit=100").json()["total"]

    created = client.post("/api/v1/admin/products", headers=h, json={
        "name": "Pytest Cascade Product", "price": 599, "stock": 7,
        "category_id": leaf["id"], "tags": ["test"],
    })
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["category_id"] == leaf["id"], "product must be assigned to the chosen leaf"

    after = client.get(f"/api/v1/products?category={parent_slug}&limit=100").json()["total"]
    assert after == before + 1, "new leaf product must appear under its top-level parent"

    # cleanup (soft delete) so the demo store stays unchanged
    assert client.delete(f"/api/v1/admin/products/{body['id']}", headers=h).status_code == 204
    final = client.get(f"/api/v1/products?category={parent_slug}&limit=100").json()["total"]
    assert final == before


def test_admin_can_edit_existing_product():
    """Covers the new admin edit form: PUT updates name, price and is_customizable."""
    token = _login("admin@wishbox.com", "admin12345")
    h = {"Authorization": f"Bearer {token}"}
    leaf, _ = _find_leaf(client.get("/api/v1/categories/tree").json())

    created = client.post("/api/v1/admin/products", headers=h, json={
        "name": "Editable Product", "price": 500, "stock": 5,
        "category_id": leaf["id"], "is_customizable": False,
    }).json()
    slug = created["slug"]

    upd = client.put(f"/api/v1/admin/products/{created['id']}", headers=h, json={
        "name": "Edited Product Name", "price": 777, "is_customizable": True,
    })
    assert upd.status_code == 200, upd.text

    detail = client.get(f"/api/v1/products/{slug}").json()
    assert detail["name"] == "Edited Product Name"
    assert float(detail["price"]) == 777.0
    assert detail["is_customizable"] is True

    client.delete(f"/api/v1/admin/products/{created['id']}", headers=h)


def test_customization_message_flows_to_cart():
    """A personal message on a customizable product is stored on the cart item."""
    admin = _login("admin@wishbox.com", "admin12345")
    ah = {"Authorization": f"Bearer {admin}"}
    leaf, _ = _find_leaf(client.get("/api/v1/categories/tree").json())
    prod = client.post("/api/v1/admin/products", headers=ah, json={
        "name": "Personalizable Gift", "price": 600, "stock": 10,
        "category_id": leaf["id"], "is_customizable": True,
    }).json()

    cust = _login("customer@wishbox.com", "customer123")
    ch = {"Authorization": f"Bearer {cust}"}
    client.delete("/api/v1/cart", headers=ch)  # start clean
    cart = client.post("/api/v1/cart", headers=ch, json={
        "product_id": prod["id"], "quantity": 1,
        "customization_details": {"message": "Happy Birthday!"},
    })
    assert cart.status_code == 201, cart.text
    line = next(i for i in cart.json()["items"] if i["product_id"] == prod["id"])
    assert line["customization_details"]["message"] == "Happy Birthday!"

    client.delete("/api/v1/cart", headers=ch)
    client.delete(f"/api/v1/admin/products/{prod['id']}", headers=ah)


def test_online_payment_flow_mock_gateway():
    """Online order is created pending, then the mock gateway confirms it on verify."""
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}

    addr = client.post("/api/v1/auth/addresses", headers=h, json={
        "recipient_name": "Pay Test", "phone": "9999999999",
        "address_line1": "9 Pay St", "city": "Pune", "state": "MH", "postal_code": "411001",
    }).json()

    client.delete("/api/v1/cart", headers=h)
    product = client.get("/api/v1/products?limit=1").json()["items"][0]
    client.post("/api/v1/cart", headers=h, json={"product_id": product["id"], "quantity": 1})

    order = client.post("/api/v1/orders", headers=h, json={
        "address_id": addr["id"], "payment_method": "upi",
    }).json()
    assert order["status"] == "pending", "online orders start pending until paid"
    assert order["payment_status"] == "pending"

    created = client.post("/api/v1/payments/create", headers=h,
                          json={"order_number": order["order_number"]})
    assert created.status_code == 200, created.text
    pay = created.json()
    assert pay["provider"] == "mock" and pay["mock"], "mock gateway should return a payable handle"

    verified = client.post("/api/v1/payments/verify", headers=h, json={
        "provider_order_id": pay["provider_order_id"],
        "provider_payment_id": pay["mock"]["payment_id"],
        "provider_signature": pay["mock"]["signature"],
    })
    assert verified.status_code == 200, verified.text
    confirmed = verified.json()
    assert confirmed["payment_status"] == "paid"
    assert confirmed["status"] == "confirmed"

    client.delete("/api/v1/cart", headers=h)


def test_payment_verify_rejects_bad_signature():
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}
    addr = client.post("/api/v1/auth/addresses", headers=h, json={
        "recipient_name": "Bad Sig", "phone": "9999999999",
        "address_line1": "1 X St", "city": "Pune", "state": "MH", "postal_code": "411001",
    }).json()
    client.delete("/api/v1/cart", headers=h)
    product = client.get("/api/v1/products?limit=1").json()["items"][0]
    client.post("/api/v1/cart", headers=h, json={"product_id": product["id"], "quantity": 1})
    order = client.post("/api/v1/orders", headers=h, json={
        "address_id": addr["id"], "payment_method": "card",
    }).json()
    pay = client.post("/api/v1/payments/create", headers=h,
                      json={"order_number": order["order_number"]}).json()
    bad = client.post("/api/v1/payments/verify", headers=h, json={
        "provider_order_id": pay["provider_order_id"],
        "provider_payment_id": "mock_pay_000000",
        "provider_signature": "deadbeef",
    })
    assert bad.status_code == 400
    client.delete("/api/v1/cart", headers=h)


def test_order_queues_email_and_worker_dispatches():
    """Placing an order queues a confirmation email; the worker tick sends it."""
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}
    addr = client.post("/api/v1/auth/addresses", headers=h, json={
        "recipient_name": "Mail", "phone": "9999999999",
        "address_line1": "1 Mail St", "city": "Pune", "state": "MH", "postal_code": "411001",
    }).json()
    client.delete("/api/v1/cart", headers=h)
    product = client.get("/api/v1/products?limit=1").json()["items"][0]
    client.post("/api/v1/cart", headers=h, json={"product_id": product["id"], "quantity": 1})
    client.post("/api/v1/orders", headers=h, json={"address_id": addr["id"], "payment_method": "cod"})

    admin = _login("admin@wishbox.com", "admin12345")
    ah = {"Authorization": f"Bearer {admin}"}
    queued = client.get("/api/v1/admin/outbox?status=queued", headers=ah).json()
    assert any(m["channel"] == "email" for m in queued), "order should queue a confirmation email"

    tick = client.post("/api/v1/admin/worker/run-tick", headers=ah)
    assert tick.status_code == 200, tick.text
    assert tick.json()["messages_sent"] >= 1
    assert client.get("/api/v1/admin/outbox?status=queued", headers=ah).json() == []
    client.delete("/api/v1/cart", headers=h)


def test_due_reminder_fires_notification():
    import datetime as _dt
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}
    yesterday = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
    rem = client.post("/api/v1/reminders", headers=h, json={
        "title": "Pytest Birthday", "reminder_date": yesterday, "recurrence": "yearly",
    }).json()

    admin = _login("admin@wishbox.com", "admin12345")
    ah = {"Authorization": f"Bearer {admin}"}
    tick = client.post("/api/v1/admin/worker/run-tick", headers=ah).json()
    assert tick["reminders_fired"] >= 1

    notifs = client.get("/api/v1/notifications", headers=h).json()
    assert any(n["type"] == "reminder" and "Pytest Birthday" in n["title"] for n in notifs)

    # yearly reminder rolled forward to a future date
    after = client.get("/api/v1/reminders", headers=h).json()
    mine = next(r for r in after if r["id"] == rem["id"])
    assert mine["reminder_date"] > yesterday
    client.delete(f"/api/v1/reminders/{rem['id']}", headers=h)


def test_forgot_and_reset_password():
    email = "resettest@wishbox.com"
    client.post("/api/v1/auth/register", json={  # ignore if it already exists
        "email": email, "password": "origpass123", "full_name": "Reset Tester",
    })
    r = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert r.status_code == 200  # generic response, no enumeration
    # also returns 200 for an unknown email
    assert client.post("/api/v1/auth/forgot-password", json={"email": "nobody@nowhere.com"}).status_code == 200

    token = _latest_token(email, "reset_password")
    done = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "brandnew12345"})
    assert done.status_code == 200, done.text
    # new password works
    assert client.post("/api/v1/auth/login-json", json={"email": email, "password": "brandnew12345"}).status_code == 200
    # token cannot be reused
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "another12345"}).status_code == 400


def test_email_verification_flow():
    email = "verifytest@wishbox.com"
    reg = client.post("/api/v1/auth/register", json={
        "email": email, "password": "verifypass123", "full_name": "Verify Tester",
    })
    token = reg.json().get("access_token") or _login(email, "verifypass123")
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/profile", headers=h).json()["email_verified"] is False

    assert client.post("/api/v1/auth/verify-email/request", headers=h).status_code == 200
    vtoken = _latest_token(email, "verify_email")
    assert client.post("/api/v1/auth/verify-email/confirm", json={"token": vtoken}).status_code == 200
    assert client.get("/api/v1/auth/profile", headers=h).json()["email_verified"] is True


def test_address_can_be_edited():
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}
    addr = client.post("/api/v1/auth/addresses", headers=h, json={
        "recipient_name": "Edit Me", "phone": "9999999999",
        "address_line1": "1 Old St", "city": "Pune", "state": "MH", "postal_code": "411001",
    }).json()
    upd = client.put(f"/api/v1/auth/addresses/{addr['id']}", headers=h, json={
        "recipient_name": "Edited", "phone": "8888888888",
        "address_line1": "2 New Rd", "city": "Mumbai", "state": "MH", "postal_code": "400001",
    })
    assert upd.status_code == 200, upd.text
    assert upd.json()["city"] == "Mumbai" and upd.json()["recipient_name"] == "Edited"
    client.delete(f"/api/v1/auth/addresses/{addr['id']}", headers=h)
