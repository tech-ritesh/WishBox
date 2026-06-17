"""End-to-end smoke test of the core WishBox flow.

Run:  python -m pytest -q     (from the backend folder, after `python seed.py`)
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
