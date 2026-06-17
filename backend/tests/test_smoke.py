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


def _orderable_product(min_stock=5):
    """Find-or-create a dedicated high-stock test product so the suite never
    depletes the demo catalog. Restocks it if a prior test ran it low."""
    admin = _login("admin@wishbox.com", "admin12345")
    ah = {"Authorization": f"Bearer {admin}"}
    found = client.get("/api/v1/products?q=PytestOrderable&limit=1").json()["items"]
    if found:
        p = found[0]
        if p["stock"] < min_stock + 2:
            client.put(f"/api/v1/products/{p['id']}".replace("/products/", "/admin/products/"),
                       headers=ah, json={"stock": 999})
            p = client.get(f"/api/v1/products/{p['slug']}").json()
        return p
    leaf, _ = _find_leaf(client.get("/api/v1/categories/tree").json())
    return client.post("/api/v1/admin/products", headers=ah, json={
        "name": "PytestOrderable Gift", "price": 500, "stock": 999, "category_id": leaf["id"],
    }).json()


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
    product = _orderable_product()
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
    product = _orderable_product()
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
    product = _orderable_product()
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
    product = _orderable_product()
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
    # Reset to unverified so the flow runs fresh even on repeat runs.
    _db = SessionLocal()
    try:
        u = _db.query(models.User).filter(models.User.email == email).first()
        u.email_verified = False
        _db.commit()
    finally:
        _db.close()
    assert client.get("/api/v1/auth/profile", headers=h).json()["email_verified"] is False

    assert client.post("/api/v1/auth/verify-email/request", headers=h).status_code == 200
    vtoken = _latest_token(email, "verify_email")
    assert client.post("/api/v1/auth/verify-email/confirm", json={"token": vtoken}).status_code == 200
    assert client.get("/api/v1/auth/profile", headers=h).json()["email_verified"] is True


def test_order_invoice_gst_breakdown():
    """Invoice is generated lazily and its total equals the order total
    (GST is the embedded component, not added on top)."""
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}
    addr = client.post("/api/v1/auth/addresses", headers=h, json={
        "recipient_name": "Inv", "phone": "9999999999",
        "address_line1": "1 Inv St", "city": "Pune", "state": "MH", "postal_code": "411001",
    }).json()
    client.delete("/api/v1/cart", headers=h)
    product = _orderable_product()
    client.post("/api/v1/cart", headers=h, json={"product_id": product["id"], "quantity": 1})
    order = client.post("/api/v1/orders", headers=h, json={"address_id": addr["id"], "payment_method": "cod"}).json()

    inv = client.get(f"/api/v1/orders/{order['order_number']}/invoice", headers=h)
    assert inv.status_code == 200, inv.text
    body = inv.json()
    assert body["invoice_number"] == f"INV-{order['order_number']}"
    # MH ship state => intra-state => CGST + SGST (no IGST)
    assert float(body["cgst"]) > 0 and float(body["sgst"]) > 0
    assert float(body["igst"]) == 0
    # taxable + cgst + sgst ~= goods (subtotal - discount); total matches the order exactly
    goods = round(float(body["taxable_value"]) + float(body["cgst"]) + float(body["sgst"]), 2)
    assert abs(goods - (float(body["subtotal"]) - float(body["discount_amount"]))) < 0.05
    assert float(body["total_amount"]) == float(order["total_amount"])

    # idempotent: same invoice number on refetch
    again = client.get(f"/api/v1/orders/{order['order_number']}/invoice", headers=h).json()
    assert again["id"] == body["id"]
    client.delete("/api/v1/cart", headers=h)


def test_inter_state_invoice_uses_igst():
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}
    addr = client.post("/api/v1/auth/addresses", headers=h, json={
        "recipient_name": "KA", "phone": "9999999999",
        "address_line1": "1 KA St", "city": "Bengaluru", "state": "KA", "postal_code": "560001",
    }).json()
    client.delete("/api/v1/cart", headers=h)
    product = _orderable_product()
    client.post("/api/v1/cart", headers=h, json={"product_id": product["id"], "quantity": 1})
    order = client.post("/api/v1/orders", headers=h, json={"address_id": addr["id"], "payment_method": "cod"}).json()
    body = client.get(f"/api/v1/orders/{order['order_number']}/invoice", headers=h).json()
    assert float(body["igst"]) > 0 and float(body["cgst"]) == 0 and float(body["sgst"]) == 0
    client.delete("/api/v1/cart", headers=h)


def _wallet_balance(h):
    return float(client.get("/api/v1/wallet", headers=h).json()["balance"])


def test_wallet_loyalty_giftcard_and_redeem():
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}
    product = _orderable_product(min_stock=4)
    addr = client.post("/api/v1/auth/addresses", headers=h, json={
        "recipient_name": "W", "phone": "9999999999",
        "address_line1": "1 W St", "city": "Pune", "state": "MH", "postal_code": "411001",
    }).json()

    bal0 = _wallet_balance(h)
    # placing an order earns 2% cashback
    client.delete("/api/v1/cart", headers=h)
    client.post("/api/v1/cart", headers=h, json={"product_id": product["id"], "quantity": 1})
    o1 = client.post("/api/v1/orders", headers=h, json={"address_id": addr["id"], "payment_method": "cod"}).json()
    bal1 = _wallet_balance(h)
    assert bal1 > bal0, "order should earn wallet credit"
    assert abs((bal1 - bal0) - round(float(o1["total_amount"]) * 0.02, 2)) < 0.05

    # gift card buy + redeem tops up the wallet
    gc = client.post("/api/v1/gift-cards", headers=h, json={"amount": 500})
    assert gc.status_code == 201, gc.text
    client.post("/api/v1/gift-cards/redeem", headers=h, json={"code": gc.json()["code"]})
    bal2 = _wallet_balance(h)
    assert abs(bal2 - (bal1 + 500)) < 0.05

    # redeem wallet credit at checkout
    client.delete("/api/v1/cart", headers=h)
    client.post("/api/v1/cart", headers=h, json={"product_id": product["id"], "quantity": 1})
    o2 = client.post("/api/v1/orders", headers=h, json={
        "address_id": addr["id"], "payment_method": "cod", "wallet_redeem": 100,
    }).json()
    assert float(o2["discount_amount"]) >= 100, "wallet redemption should discount the order"
    client.delete("/api/v1/cart", headers=h)


def test_referral_rewards_both_parties():
    ref = _login("customer@wishbox.com", "customer123")
    rh = {"Authorization": f"Bearer {ref}"}
    code = client.get("/api/v1/wallet/referral", headers=rh).json()["referral_code"]
    ref_bal_before = _wallet_balance(rh)

    email = "referree@example.com"
    _db = SessionLocal()
    try:
        u = _db.query(models.User).filter(models.User.email == email).first()
        if u:
            _db.query(models.WalletTransaction).filter(models.WalletTransaction.user_id == u.id).delete()
            _db.delete(u); _db.commit()
    finally:
        _db.close()

    reg = client.post("/api/v1/auth/register", json={
        "email": email, "password": "referred12345", "full_name": "Referree", "referral_code": code,
    })
    assert reg.status_code == 201, reg.text
    nh = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    assert _wallet_balance(nh) == 100.0, "new user gets referral credit"
    assert _wallet_balance(rh) == ref_bal_before + 100.0, "referrer gets referral credit"


def test_reviews_helpful_moderation_and_qa():
    admin = _login("admin@wishbox.com", "admin12345")
    ah = {"Authorization": f"Bearer {admin}"}
    leaf, _ = _find_leaf(client.get("/api/v1/categories/tree").json())
    prod = client.post("/api/v1/admin/products", headers=ah, json={
        "name": "PytestReview Gift", "price": 350, "stock": 5, "category_id": leaf["id"],
    }).json()

    cust = _login("customer@wishbox.com", "customer123")
    ch = {"Authorization": f"Bearer {cust}"}
    rev = client.post("/api/v1/reviews", headers=ch, json={
        "product_id": prod["id"], "rating": 5, "comment": "Lovely", "image_url": "/static/x.png",
    })
    assert rev.status_code == 201, rev.text
    rid = rev.json()["id"]
    assert rev.json()["status"] == "approved"
    assert client.get(f"/api/v1/reviews/{prod['id']}").json(), "approved review is publicly visible"

    # helpful vote toggles
    v1 = client.post(f"/api/v1/reviews/{rid}/helpful", headers=ah).json()
    assert v1["helpful_count"] == 1 and v1["voted"] is True
    v2 = client.post(f"/api/v1/reviews/{rid}/helpful", headers=ah).json()
    assert v2["helpful_count"] == 0 and v2["voted"] is False

    # moderation: reject hides it from the public listing
    assert client.put(f"/api/v1/admin/reviews/{rid}", headers=ah, json={"status": "rejected"}).status_code == 200
    assert client.get(f"/api/v1/reviews/{prod['id']}").json() == []

    # Q&A: ask + staff answer
    q = client.post(f"/api/v1/products/{prod['id']}/questions", headers=ch, json={"body": "Is it giftable?"})
    assert q.status_code == 201, q.text
    qid = q.json()["id"]
    a = client.post(f"/api/v1/questions/{qid}/answers", headers=ah, json={"body": "Yes, gift-wrapped!"})
    assert a.status_code == 201 and a.json()["is_staff_answer"] is True
    qs = client.get(f"/api/v1/products/{prod['id']}/questions").json()
    assert qs[0]["answers"][0]["body"] == "Yes, gift-wrapped!"

    client.delete(f"/api/v1/admin/products/{prod['id']}", headers=ah)


def test_faq_and_support_tickets():
    admin = _login("admin@wishbox.com", "admin12345")
    ah = {"Authorization": f"Bearer {admin}"}
    faq = client.post("/api/v1/admin/faqs", headers=ah, json={
        "question": "How fast is delivery?", "answer": "Same-day in metros.", "category": "Shipping",
    })
    assert faq.status_code == 201, faq.text
    assert any(f["question"] == "How fast is delivery?" for f in client.get("/api/v1/faqs").json())

    cust = _login("customer@wishbox.com", "customer123")
    ch = {"Authorization": f"Bearer {cust}"}
    t = client.post("/api/v1/support/tickets", headers=ch, json={
        "subject": "Where is my order?", "body": "It is late.",
    })
    assert t.status_code == 201, t.text
    tid = t.json()["id"]
    assert t.json()["messages"][0]["body"] == "It is late."

    rep = client.post(f"/api/v1/admin/tickets/{tid}/reply", headers=ah, json={"body": "Shipping today!"})
    assert rep.status_code == 200 and rep.json()["status"] == "pending"

    mine = client.get("/api/v1/support/tickets", headers=ch).json()
    msgs = next(x for x in mine if x["id"] == tid)["messages"]
    assert any(m["is_staff"] and m["body"] == "Shipping today!" for m in msgs)

    assert client.put(f"/api/v1/admin/tickets/{tid}", headers=ah, json={"status": "resolved"}).status_code == 200

    client.delete(f"/api/v1/admin/faqs/{faq.json()['id']}", headers=ah)


def test_guest_checkout_and_claim():
    product = _orderable_product(min_stock=3)
    email = "guestbuyer@example.com"
    # clean slate so the claim assertion is deterministic across re-runs
    _db = SessionLocal()
    try:
        u = _db.query(models.User).filter(models.User.email == email).first()
        if u:
            _db.query(models.Order).filter(models.Order.user_id == u.id).delete()
            _db.query(models.CartItem).filter(models.CartItem.user_id == u.id).delete()
            _db.query(models.Address).filter(models.Address.user_id == u.id).delete()
            _db.delete(u)
            _db.commit()
    finally:
        _db.close()

    order = client.post("/api/v1/orders/guest", json={
        "email": email, "full_name": "Guest Buyer", "phone": "9999999999",
        "address_line1": "1 Guest St", "city": "Pune", "state": "MH", "postal_code": "411001",
        "payment_method": "cod",
        "items": [{"product_id": product["id"], "quantity": 1}],
    })
    assert order.status_code == 201, order.text
    assert order.json()["status"] == "confirmed"

    # claiming the guest account via registration works and logs in
    reg = client.post("/api/v1/auth/register", json={
        "email": email, "password": "claimed12345", "full_name": "Guest Buyer",
    })
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    # the claimed account retains its guest order history
    assert len(client.get("/api/v1/orders", headers=h).json()) >= 1

    # guest checkout against a real (non-guest) account is rejected
    blocked = client.post("/api/v1/orders/guest", json={
        "email": "customer@wishbox.com", "full_name": "X",
        "address_line1": "1 St", "city": "Pune", "state": "MH", "postal_code": "411001",
        "items": [{"product_id": product["id"], "quantity": 1}],
    })
    assert blocked.status_code == 409


def test_product_variant_purchase_flow():
    admin = _login("admin@wishbox.com", "admin12345")
    ah = {"Authorization": f"Bearer {admin}"}
    leaf, _ = _find_leaf(client.get("/api/v1/categories/tree").json())
    prod = client.post("/api/v1/admin/products", headers=ah, json={
        "name": "PytestVariant Mug", "price": 300, "stock": 0, "category_id": leaf["id"],
    }).json()
    # base product is out of stock; stock lives on variants
    big = client.post(f"/api/v1/admin/products/{prod['id']}/variants", headers=ah, json={
        "name": "Large / Red", "attributes": {"size": "L", "color": "Red"},
        "price_delta": 100, "stock": 5,
    })
    assert big.status_code == 201, big.text
    variant = big.json()

    detail = client.get(f"/api/v1/products/{prod['slug']}").json()
    assert any(v["id"] == variant["id"] for v in detail["variants"])

    cust = _login("customer@wishbox.com", "customer123")
    ch = {"Authorization": f"Bearer {cust}"}
    client.delete("/api/v1/cart", headers=ch)
    cart = client.post("/api/v1/cart", headers=ch, json={
        "product_id": prod["id"], "variant_id": variant["id"], "quantity": 2,
    })
    assert cart.status_code == 201, cart.text
    # unit price = base 300 + delta 100 = 400 -> subtotal 800
    assert float(cart.json()["subtotal"]) == 800.0

    addr = client.post("/api/v1/auth/addresses", headers=ch, json={
        "recipient_name": "V", "phone": "9999999999",
        "address_line1": "1 V St", "city": "Pune", "state": "MH", "postal_code": "411001",
    }).json()
    order = client.post("/api/v1/orders", headers=ch, json={"address_id": addr["id"], "payment_method": "cod"}).json()
    line = order["items"][0]
    assert line["variant_id"] == variant["id"]
    assert line["variant_name"] == "Large / Red"
    assert float(line["unit_price"]) == 400.0

    # variant stock decremented 5 -> 3
    vleft = client.get(f"/api/v1/admin/products/{prod['id']}/variants", headers=ah).json()[0]["stock"]
    assert vleft == 3

    client.delete("/api/v1/cart", headers=ch)
    client.delete(f"/api/v1/admin/products/{prod['id']}", headers=ah)


def test_recently_viewed_and_related_and_payment_methods():
    token = _login("customer@wishbox.com", "customer123")
    h = {"Authorization": f"Bearer {token}"}
    product = _orderable_product()

    # recently viewed
    assert client.post(f"/api/v1/recently-viewed/{product['id']}", headers=h).status_code == 204
    rv = client.get("/api/v1/recently-viewed", headers=h).json()
    assert any(x["product_id"] == product["id"] for x in rv)

    # related products (same category) responds
    rel = client.get(f"/api/v1/products/{product['slug']}/related")
    assert rel.status_code == 200 and isinstance(rel.json(), list)

    # saved payment methods
    pm = client.post("/api/v1/payment-methods", headers=h,
                     json={"label": "HDFC 4242", "method_type": "card", "last4": "4242", "is_default": True})
    assert pm.status_code == 201, pm.text
    assert any(m["last4"] == "4242" for m in client.get("/api/v1/payment-methods", headers=h).json())
    client.delete(f"/api/v1/payment-methods/{pm.json()['id']}", headers=h)


def test_back_in_stock_alert_fires_on_restock():
    cust = _login("customer@wishbox.com", "customer123")
    ch = {"Authorization": f"Bearer {cust}"}
    admin = _login("admin@wishbox.com", "admin12345")
    ah = {"Authorization": f"Bearer {admin}"}

    # make a product that is out of stock
    leaf, _ = _find_leaf(client.get("/api/v1/categories/tree").json())
    prod = client.post("/api/v1/admin/products", headers=ah, json={
        "name": "PytestBIS Gift", "price": 400, "stock": 0, "category_id": leaf["id"],
    }).json()

    # subscribe while out of stock
    assert client.post(f"/api/v1/products/{prod['id']}/notify-me", headers=ch).status_code == 204
    # subscribing to an in-stock product is rejected
    instock = _orderable_product()
    assert client.post(f"/api/v1/products/{instock['id']}/notify-me", headers=ch).status_code == 400

    # admin restocks -> worker tick should alert the subscriber
    client.put(f"/api/v1/admin/products/{prod['id']}", headers=ah, json={"stock": 10})
    tick = client.post("/api/v1/admin/worker/run-tick", headers=ah).json()
    assert tick["back_in_stock_alerts"] >= 1
    notifs = client.get("/api/v1/notifications", headers=ch).json()
    assert any("PytestBIS" in n["body"] for n in notifs if n.get("body"))

    client.delete(f"/api/v1/admin/products/{prod['id']}", headers=ah)


def test_search_autocomplete_and_relevance():
    p = _orderable_product()  # creates/returns "PytestOrderable Gift"
    ac = client.get("/api/v1/products/autocomplete?q=PytestOrder")
    assert ac.status_code == 200, ac.text
    assert any("PytestOrderable" in s["name"] for s in ac.json()["products"])

    # relevance ranking surfaces the closest name match first
    res = client.get("/api/v1/products?q=PytestOrderable&limit=5").json()
    assert res["items"], "expected at least one match"
    assert res["items"][0]["slug"] == p["slug"]

    # trending endpoint responds with a list
    tr = client.get("/api/v1/products/trending")
    assert tr.status_code == 200 and isinstance(tr.json(), list)


def test_shipment_and_return_refund_restocks():
    cust = _login("customer@wishbox.com", "customer123")
    ch = {"Authorization": f"Bearer {cust}"}
    admin = _login("admin@wishbox.com", "admin12345")
    ah = {"Authorization": f"Bearer {admin}"}

    product = _orderable_product(min_stock=5)
    addr = client.post("/api/v1/auth/addresses", headers=ch, json={
        "recipient_name": "Ret", "phone": "9999999999",
        "address_line1": "1 Ret St", "city": "Pune", "state": "MH", "postal_code": "411001",
    }).json()
    client.delete("/api/v1/cart", headers=ch)
    client.post("/api/v1/cart", headers=ch, json={"product_id": product["id"], "quantity": 2})
    order = client.post("/api/v1/orders", headers=ch, json={"address_id": addr["id"], "payment_method": "cod"}).json()
    oid, onum = order["id"], order["order_number"]

    # return before delivery is rejected
    early = client.post(f"/api/v1/orders/{onum}/returns", headers=ch,
                        json={"reason": "x", "items": [{"order_item_id": order["items"][0]["id"], "quantity": 1}]})
    assert early.status_code == 400

    # admin ships + delivers
    ship = client.post(f"/api/v1/admin/orders/{oid}/shipment", headers=ah,
                       json={"status": "in_transit", "carrier": "BlueDart", "location": "Pune Hub"})
    assert ship.status_code == 200, ship.text
    assert ship.json()["tracking_number"]
    client.put(f"/api/v1/admin/orders/{oid}", headers=ah, json={"status": "delivered"})
    assert client.get(f"/api/v1/orders/{onum}/shipment", headers=ch).status_code == 200

    # customer requests a return of 1 unit
    rr = client.post(f"/api/v1/orders/{onum}/returns", headers=ch, json={
        "kind": "return", "reason": "damaged box",
        "items": [{"order_item_id": order["items"][0]["id"], "quantity": 1}],
    })
    assert rr.status_code == 201, rr.text
    return_id = rr.json()["id"]
    assert float(rr.json()["refund_amount"]) > 0

    stock_before = client.get(f"/api/v1/products/{product['slug']}").json()["stock"]
    refunded = client.put(f"/api/v1/admin/returns/{return_id}", headers=ah, json={"status": "refunded"})
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"

    stock_after = client.get(f"/api/v1/products/{product['slug']}").json()["stock"]
    assert stock_after == stock_before + 1, "refund must restock the returned unit"
    assert client.get(f"/api/v1/orders/{onum}", headers=ch).json()["payment_status"] == "refunded"
    client.delete("/api/v1/cart", headers=ch)


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
