"""Small shared helpers."""
import random
import re
import datetime as dt
from decimal import Decimal


def slugify(value: str) -> str:
    value = (value or "").lower().strip()
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return re.sub(r"-{2,}", "-", value).strip("-")


def unique_slug(base: str, exists_fn) -> str:
    """exists_fn(slug) -> bool. Appends -2, -3, ... until free."""
    slug = slugify(base) or "item"
    candidate = slug
    i = 2
    while exists_fn(candidate):
        candidate = f"{slug}-{i}"
        i += 1
    return candidate


def generate_order_number() -> str:
    date_str = dt.datetime.now().strftime("%Y%m%d")
    return f"WB-{date_str}-{random.randint(10000, 99999)}"


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))
