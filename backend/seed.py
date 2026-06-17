"""Seed WishBox with demo users, a full 3-level category hierarchy, generated
catalog products, coupons, a festival and a hamper template.

Run from the backend folder:  python seed.py

This performs a CATALOG RESET each run (categories, products, tags, hampers,
stock, collections AND demo orders/carts/wishlists/reviews that reference them)
so the hierarchy rebuilds deterministically. Users, coupons and festivals are kept.
"""
import datetime as dt

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app import models
from app.services.common import slugify, unique_slug

Base.metadata.create_all(bind=engine)


# --- The category hierarchy (mirrors Celebration Box, 3 levels) --------------
# parent -> {occasion_group, subs: {sub_name -> {mega, new(optional), leaves: [...]}}}
HIERARCHY = {
    "Birthday": {"occasion_group": "personal-relationships", "subs": {
        "Featured Picks": {"mega": "must-haves", "new": ["Gifts in 60 Mins"], "leaves": [
            "Gifts in 60 Mins", "All Birthday Gifts", "Best Sellers", "New Arrivals",
            "Premium Gifts", "Personalized Gifts", "Gift Hampers", "Greeting Cards"]},
        "Gift By Recipient": {"mega": "prime-picks", "leaves": [
            "For Her", "For Him", "For Kids", "For Friends", "For Wife", "For Husband",
            "For Girlfriend", "For Boyfriend", "For Mother", "For Father"]},
        "Gift By Interest": {"mega": "personal-picks", "leaves": [
            "Plant Lover", "Foodies", "Music Lover", "Fashion Lover", "Pet Lover"]},
        "Age Based Gifts": {"mega": "personal-picks", "leaves": [
            "1st Birthday", "10th Birthday", "18th Birthday", "21st Birthday",
            "25th Birthday", "50th Birthday"]},
        "Combo Gifts": {"mega": "unique", "leaves": [
            "Flowers & Cakes", "Flowers & Chocolates", "Gift Combos", "Luxury Gifts"]},
        "Unique Gifts": {"mega": "unique", "new": ["Balloon Decoration"], "leaves": [
            "Jewelry", "Electronics", "Toys & Games", "Experiential Gifts", "Balloon Decoration"]},
        "Price Range": {"mega": "price-wise", "leaves": [
            "Under ₹500", "₹500 - ₹1000", "₹1000 - ₹2000", "Above ₹2000"]},
    }},
    "Anniversary": {"occasion_group": "personal-relationships", "subs": {
        "Featured Picks": {"mega": "must-haves", "leaves": [
            "All Anniversary Gifts", "Best Sellers", "New Arrivals", "Premium Gifts", "Luxury Gifts"]},
        "Gift By Recipient": {"mega": "prime-picks", "leaves": [
            "For Husband", "For Wife", "For Couples", "For Parents"]},
        "Milestone Anniversaries": {"mega": "personal-picks", "leaves": [
            "1st Anniversary", "5th Anniversary", "10th Anniversary", "25th Anniversary", "50th Anniversary"]},
        "Popular Categories": {"mega": "prime-picks", "leaves": [
            "Cakes", "Flowers", "Personalized Gifts", "Chocolates", "Hampers", "Jewelry", "Home Decor"]},
        "Combo Gifts": {"mega": "unique", "leaves": [
            "Flowers & Cakes", "Flowers & Chocolates", "Anniversary Combos"]},
        "Special Gifts": {"mega": "unique", "leaves": [
            "Romantic Gifts", "Photo Frames", "Experiential Gifts", "Decorations"]},
        "Wedding Gifts": {"mega": "personal-picks", "leaves": [
            "For Bride", "For Groom", "For Relatives", "For Friends"]},
    }},
    "Occasions": {"occasion_group": "family-life-moments", "subs": {
        "Congratulations": {"mega": "must-haves", "leaves": [
            "Graduation Gifts", "Promotion Gifts", "Achievement Gifts"]},
        "Housewarming": {"mega": "prime-picks", "leaves": ["Plants", "Home Decor", "Gift Hampers"]},
        "Love & Romance": {"mega": "prime-picks", "leaves": [
            "Romantic Flowers", "Personalized Gifts", "Chocolates"]},
        "Wedding": {"mega": "personal-picks", "leaves": ["Wedding Gifts", "Couple Gifts", "Decor"]},
        "Baby Shower": {"mega": "personal-picks", "leaves": [
            "Baby Gift Sets", "Toys", "Personalized Gifts"]},
        "Farewell": {"mega": "unique", "leaves": ["Memory Gifts", "Customized Frames"]},
        "Condolence": {"mega": "unique", "leaves": ["Sympathy Flowers", "Support Gifts"]},
        "Thank You": {"mega": "must-haves", "leaves": ["Appreciation Gifts", "Corporate Appreciation"]},
    }},
    "Flowers": {"occasion_group": "care-luxury", "subs": {
        "Flower Types": {"mega": "must-haves", "leaves": [
            "Roses", "Carnations", "Lilies", "Orchids", "Gerberas", "Sunflowers",
            "Mixed Flowers", "Exotic Flowers", "Daisies"]},
        "Occasion Flowers": {"mega": "prime-picks", "leaves": [
            "Birthday Flowers", "Anniversary Flowers", "Wedding Flowers",
            "Congratulations Flowers", "Romantic Flowers"]},
        "Arrangements": {"mega": "prime-picks", "leaves": [
            "Flower Bouquets", "Flower Baskets", "Flower Arrangements", "Luxury Flowers"]},
        "Flower Combos": {"mega": "unique", "leaves": [
            "Flowers & Cakes", "Flowers & Chocolates", "Flower Hampers"]},
        "Color Based Flowers": {"mega": "price-wise", "leaves": [
            "Red", "Pink", "Yellow", "White", "Purple", "Pastel"]},
    }},
    "Festive Sale": {"occasion_group": "care-luxury", "subs": {
        "Diwali": {"mega": "must-haves", "new": ["Diwali Hampers"], "leaves": [
            "Diwali Hampers", "Diyas", "Dry Fruits", "Sweets"]},
        "Christmas": {"mega": "prime-picks", "leaves": ["Christmas Gifts", "Decorations", "Cakes"]},
        "New Year": {"mega": "prime-picks", "leaves": ["New Year Gift Sets", "Party Hampers"]},
        "Raksha Bandhan": {"mega": "personal-picks", "leaves": ["Rakhi", "Rakhi Combos", "Sweets"]},
        "Valentine's Day": {"mega": "personal-picks", "leaves": ["Romantic Gifts", "Roses", "Chocolates"]},
        "Mother's Day": {"mega": "unique", "leaves": ["Gifts For Mother", "Flowers", "Personalized Gifts"]},
        "Father's Day": {"mega": "unique", "leaves": ["Gifts For Father", "Grooming Kits"]},
        "Holi": {"mega": "price-wise", "leaves": ["Holi Hampers", "Organic Colors"]},
    }},
    "Corporate": {"occasion_group": "achievement-success", "subs": {
        "Employee Gifts": {"mega": "must-haves", "leaves": [
            "Joining Kits", "Welcome Kits", "Reward Gifts"]},
        "Client Gifts": {"mega": "prime-picks", "leaves": ["Premium Hampers", "Luxury Gifts"]},
        "Festival Gifting": {"mega": "prime-picks", "leaves": ["Diwali Hampers", "New Year Hampers"]},
        "Branding & Merchandise": {"mega": "unique", "new": ["Customized Bottles"], "leaves": [
            "Customized Mugs", "Customized Bottles", "T-Shirts", "Diaries"]},
        "Bulk Orders": {"mega": "price-wise", "leaves": ["Bulk Hampers", "Bulk Gift Boxes"]},
        "Corporate Occasions": {"mega": "personal-picks", "leaves": [
            "Work Anniversary Gifts", "Employee Birthday Gifts", "Achievement Awards"]},
    }},
}

# Map each parent to a primary occasion tag + an emotion pool for generated products
PARENT_TAG = {
    "Birthday": "birthday", "Anniversary": "anniversary", "Occasions": "occasions",
    "Flowers": "flowers", "Festive Sale": "festival", "Corporate": "corporate",
}
EMOTIONS = ["romantic", "luxury", "thoughtful", "cute", "professional", "festive"]
SUFFIXES = ["Gift Box", "Hamper", "Surprise", "Combo", "Deluxe Set"]


def reset_catalog(db):
    """Delete catalog + dependent demo rows so the hierarchy rebuilds cleanly."""
    for model in (
        models.OrderStatusHistory, models.OrderItem, models.CouponRedemption, models.Order,
        models.CartItem, models.WishlistItem, models.Review,
        models.HamperItem, models.Hamper, models.StockMovement, models.ProductImage,
        models.HomepageCollection, models.Product, models.Tag, models.Category,
    ):
        db.query(model).delete()
    db.commit()


def get_or_make_tag(db, cache, name, kind="general"):
    key = name.lower()
    if key in cache:
        return cache[key]
    t = models.Tag(name=name, kind=kind)
    db.add(t)
    db.flush()
    cache[key] = t
    return t


def run():
    db = SessionLocal()
    try:
        # --- Users (kept across re-seeds) ---
        if db.query(models.User).count() == 0:
            db.add_all([
                models.User(email="admin@wishbox.com", password_hash=hash_password("admin12345"),
                            full_name="WishBox Admin", role=models.UserRole.admin, email_verified=True),
                models.User(email="staff@wishbox.com", password_hash=hash_password("staff12345"),
                            full_name="Store Staff", role=models.UserRole.staff, email_verified=True),
                models.User(email="customer@wishbox.com", password_hash=hash_password("customer123"),
                            full_name="Demo Customer", role=models.UserRole.customer, email_verified=True),
            ])
            db.commit()

        # --- Vendor ---
        vendor = db.query(models.Vendor).first()
        if not vendor:
            vendor = models.Vendor(name="Artisan Gifts Co.", contact_email="supply@artisan.example", lead_time_days=2)
            db.add(vendor)
            db.commit()

        # --- Catalog reset + rebuild ---
        reset_catalog(db)

        slug_seen = set()
        def uslug(name):
            s = unique_slug(name, lambda x: x in slug_seen)
            slug_seen.add(s)
            return s

        leaf_categories = []  # (leaf_obj, parent_name)
        order = 0
        for p_name, p_def in HIERARCHY.items():
            order += 1
            parent = models.Category(
                name=p_name, slug=uslug(p_name), occasion_group=p_def["occasion_group"],
                sort_order=order, description=f"{p_name} gifts and hampers for every celebration.",
            )
            db.add(parent)
            db.flush()
            s_order = 0
            for s_name, s_def in p_def["subs"].items():
                s_order += 1
                sub = models.Category(
                    name=s_name, slug=uslug(f"{p_name} {s_name}"), parent_id=parent.id,
                    occasion_group=p_def["occasion_group"], mega_menu_group=s_def.get("mega"),
                    sort_order=s_order,
                )
                db.add(sub)
                db.flush()
                new_set = set(s_def.get("new", []))
                l_order = 0
                for leaf_name in s_def["leaves"]:
                    l_order += 1
                    leaf = models.Category(
                        name=leaf_name, slug=uslug(f"{p_name} {s_name} {leaf_name}"),
                        parent_id=sub.id, occasion_group=p_def["occasion_group"],
                        is_badge_new=leaf_name in new_set, sort_order=l_order,
                    )
                    db.add(leaf)
                    db.flush()
                    leaf_categories.append((leaf, p_name))
        db.commit()

        # --- Generate ~50-60 products spread across leaves (every other leaf) ---
        tag_cache = {}
        created = []
        idx = 0
        for i, (leaf, p_name) in enumerate(leaf_categories):
            if i % 2 != 0:  # roughly half the leaves get a product
                continue
            idx += 1
            suffix = SUFFIXES[idx % len(SUFFIXES)]
            base_name = f"{leaf.name} {suffix}"
            price = 399 + (idx % 13) * 250          # ₹399 .. ₹3399
            has_disc = idx % 3 == 0
            disc = round(price * 0.85, 2) if has_disc else None
            pname = base_name
            pslug = unique_slug(base_name, lambda x: db.query(models.Product).filter(models.Product.slug == x).first() is not None)
            product = models.Product(
                name=pname, slug=pslug, description=f"A thoughtfully curated {leaf.name.lower()} for {p_name.lower()}.",
                price=price, discount_price=disc, stock=20 + (idx % 15), low_stock_threshold=5,
                category_id=leaf.id, vendor_id=vendor.id, type="hamper",
                sku=f"WB-{pslug[:10].upper()}-{idx:03d}",
                is_quick_delivery=("60 Mins" in leaf.name) or idx % 6 == 0,
                is_customizable=idx % 4 == 0,
            )
            db.add(product)
            db.flush()
            product.tags.append(get_or_make_tag(db, tag_cache, PARENT_TAG[p_name], "occasion"))
            product.tags.append(get_or_make_tag(db, tag_cache, EMOTIONS[idx % len(EMOTIONS)], "emotion"))
            db.add(models.StockMovement(product_id=product.id, change=product.stock, reason="restock", reference="seed"))
            created.append(product)
        db.commit()

        # --- Hamper template + homepage collection referencing real products ---
        if created:
            tmpl = models.Hamper(name="Starter Birthday Hamper", occasion="birthday", is_template=True, box_style="kraft")
            db.add(tmpl)
            db.flush()
            for p in created[:3]:
                db.add(models.HamperItem(hamper_id=tmpl.id, product_id=p.id, quantity=1))
            db.add(models.HomepageCollection(
                title="Best Sellers", slug="best-sellers", description="Customer favourites",
                display_order=1, product_ids=[p.id for p in created[:6]],
            ))
            db.commit()

        # --- Coupons (kept) ---
        if db.query(models.Coupon).count() == 0:
            db.add_all([
                models.Coupon(code="WELCOME10", description="10% off first order", discount_type="percentage",
                              discount_value=10, max_discount=200, min_order_value=0, per_user_limit=1, active=True),
                models.Coupon(code="FLAT250", description="Flat ₹250 off above ₹1500", discount_type="flat",
                              discount_value=250, min_order_value=1500, active=True),
            ])
            db.commit()

        # --- Festival (kept) ---
        if db.query(models.FestivalCampaign).count() == 0:
            now = dt.datetime.utcnow()
            db.add(models.FestivalCampaign(
                name="Diwali Dhamaka", slug="diwali-dhamaka", description="Festive savings on hampers",
                theme_color="#F59E0B", start_date=now - dt.timedelta(days=1),
                end_date=now + dt.timedelta(days=30), discount_percentage=15, coupon_code="WELCOME10", active=True,
            ))
            db.commit()

        print("Seed complete.")
        print(f"  Categories: {db.query(models.Category).count()} "
              f"(parents={db.query(models.Category).filter(models.Category.parent_id.is_(None)).count()})")
        print(f"  Products:   {db.query(models.Product).count()}")
        print("  Admin:    admin@wishbox.com / admin12345")
        print("  Staff:    staff@wishbox.com / staff12345")
        print("  Customer: customer@wishbox.com / customer123")
    finally:
        db.close()


if __name__ == "__main__":
    run()
