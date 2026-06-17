"""SQLAlchemy ORM models for WishBox.

Improvements over the Celebration Box reference:
  * Money is Numeric(10,2) (Decimal), never float.
  * Tags are a real table + M2M (not JSON stuffed in a Text column).
  * Inventory is tracked with a StockMovement ledger; stock decremented in-transaction.
  * Order lifecycle is captured in OrderStatusHistory (customer timeline + audit trail).
  * created_at / updated_at on every table; soft-delete via is_active where it matters.
  * New domains: Vendor, Notification, CorporateAccount, Hamper (smart builder).
"""
import datetime as dt
import enum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, Table,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


# --- Enums -------------------------------------------------------------------
class UserRole(str, enum.Enum):
    customer = "customer"
    staff = "staff"
    admin = "admin"


class OrderStatus(str, enum.Enum):
    pending = "pending"           # created, awaiting payment
    confirmed = "confirmed"       # paid / COD accepted
    packed = "packed"
    shipped = "shipped"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    cancelled = "cancelled"
    refunded = "refunded"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


# --- Association tables ------------------------------------------------------
product_tags = Table(
    "product_tags",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


# --- Identity ----------------------------------------------------------------
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.customer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)  # checkout-only shadow account
    referral_code: Mapped[str] = mapped_column(String, nullable=True, unique=True, index=True)
    # App-enforced reference (no DB FK to avoid SQLite ALTER-FK rebuilds).
    referred_by_id: Mapped[int] = mapped_column(Integer, nullable=True)
    last_login_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=True)
    corporate_account_id: Mapped[int] = mapped_column(ForeignKey("corporate_accounts.id"), nullable=True)

    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")
    wishlist_items = relationship("WishlistItem", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    corporate_account = relationship("CorporateAccount", back_populates="members")


class Address(Base, TimestampMixin):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String, default="Home")
    recipient_name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    address_line1: Mapped[str] = mapped_column(String, nullable=False)
    address_line2: Mapped[str] = mapped_column(String, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    postal_code: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String, default="India")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="addresses")


# --- Catalog -----------------------------------------------------------------
class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Names repeat across the tree (e.g. "Best Sellers" under several parents); slug is the unique key.
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    occasion_group: Mapped[str] = mapped_column(String, nullable=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Mega-menu grouping of sub-categories (e.g. 'must-haves', 'prime-picks', 'unique')
    mega_menu_group: Mapped[str] = mapped_column(String, nullable=True)
    is_badge_new: Mapped[bool] = mapped_column(Boolean, default=False)

    products = relationship("Product", back_populates="category")
    children = relationship("Category", backref="parent", remote_side=[id])


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String, default="general")  # occasion | emotion | recipient | general

    products = relationship("Product", secondary=product_tags, back_populates="tags")


class Vendor(Base, TimestampMixin):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    contact_email: Mapped[str] = mapped_column(String, nullable=True)
    contact_phone: Mapped[str] = mapped_column(String, nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    products = relationship("Product", back_populates="vendor")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    discount_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String, default="INR")
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    is_customizable: Mapped[bool] = mapped_column(Boolean, default=False)
    type: Mapped[str] = mapped_column(String, default="hamper")  # hamper | addon | personalized | combo
    is_quick_delivery: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rating_avg: Mapped[float] = mapped_column(Numeric(3, 2), default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)

    category = relationship("Category", back_populates="products")
    vendor = relationship("Vendor", back_populates="products")
    tags = relationship("Tag", secondary=product_tags, back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")

    @property
    def effective_price(self):
        return self.discount_price if self.discount_price is not None else self.price


class ProductVariant(Base, TimestampMixin):
    """A purchasable variation of a product (e.g. Size: Large / Color: Red).

    Variant-less products keep using Product.stock and Product.price exactly as
    before — variants are entirely opt-in.
    """
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)          # display label, e.g. "Large / Red"
    attributes: Mapped[dict] = mapped_column(JSON, nullable=True)      # {"size": "L", "color": "Red"}
    price_delta: Mapped[float] = mapped_column(Numeric(10, 2), default=0)  # +/- on the base effective price
    stock: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product = relationship("Product", back_populates="variants")


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    image_url: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product = relationship("Product", back_populates="images")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    change: Mapped[int] = mapped_column(Integer, nullable=False)  # negative = sale, positive = restock
    reason: Mapped[str] = mapped_column(String, nullable=False)   # order | restock | adjustment | cancel
    reference: Mapped[str] = mapped_column(String, nullable=True)  # e.g. order number
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


# --- Cart & Hampers ----------------------------------------------------------
class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(Integer, nullable=True)  # app-enforced FK
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    customization_details: Mapped[dict] = mapped_column(JSON, nullable=True)

    user = relationship("User", back_populates="cart_items")
    product = relationship("Product")
    variant = relationship(
        "ProductVariant",
        primaryjoin="foreign(CartItem.variant_id) == ProductVariant.id",
        viewonly=True, uselist=False,
    )


class Hamper(Base, TimestampMixin):
    """Smart hamper builder: a user-composed bundle of products."""
    __tablename__ = "hampers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String, default="My Hamper")
    occasion: Mapped[str] = mapped_column(String, nullable=True)
    box_style: Mapped[str] = mapped_column(String, nullable=True)
    gift_message: Mapped[str] = mapped_column(Text, nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)  # curated starter templates

    items = relationship("HamperItem", back_populates="hamper", cascade="all, delete-orphan")


class HamperItem(Base):
    __tablename__ = "hamper_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    hamper_id: Mapped[int] = mapped_column(ForeignKey("hampers.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    hamper = relationship("Hamper", back_populates="items")
    product = relationship("Product")


# --- Orders ------------------------------------------------------------------
class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    order_number: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    shipping_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Structured shipping snapshot (not a flattened text blob like the reference)
    recipient_name: Mapped[str] = mapped_column(String, nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String, nullable=True)
    ship_address_line1: Mapped[str] = mapped_column(String, nullable=False)
    ship_address_line2: Mapped[str] = mapped_column(String, nullable=True)
    ship_city: Mapped[str] = mapped_column(String, nullable=False)
    ship_state: Mapped[str] = mapped_column(String, nullable=False)
    ship_postal_code: Mapped[str] = mapped_column(String, nullable=False)
    ship_country: Mapped[str] = mapped_column(String, default="India")

    # Gifting / scheduling
    is_gift: Mapped[bool] = mapped_column(Boolean, default=False)
    gift_message: Mapped[str] = mapped_column(Text, nullable=True)
    scheduled_delivery_date: Mapped[dt.date] = mapped_column(Date, nullable=True)
    delivery_slot: Mapped[str] = mapped_column(String, nullable=True)  # e.g. "10:00-13:00", "midnight"

    payment_method: Mapped[str] = mapped_column(String, default="cod")
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending)
    tracking_code: Mapped[str] = mapped_column(String, nullable=True)
    coupon_code: Mapped[str] = mapped_column(String, nullable=True)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    history = relationship(
        "OrderStatusHistory", back_populates="order",
        cascade="all, delete-orphan", order_by="OrderStatusHistory.created_at",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(Integer, nullable=True)  # app-enforced FK
    product_name: Mapped[str] = mapped_column(String, nullable=False)  # snapshot
    variant_name: Mapped[str] = mapped_column(String, nullable=True)   # snapshot
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    customization_details: Mapped[dict] = mapped_column(JSON, nullable=True)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class OrderStatusHistory(Base):
    """Order lifecycle timeline — powers customer tracking AND the admin audit trail."""
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str] = mapped_column(String, nullable=True)
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    order = relationship("Order", back_populates="history")


# --- Payments ----------------------------------------------------------------
class Payment(Base, TimestampMixin):
    """Gateway transaction record. One order may have several attempts."""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String, default="mock")  # mock | razorpay
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, default="INR")
    # Provider identifiers (Razorpay: order_id / payment_id / signature)
    provider_order_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    provider_payment_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    provider_signature: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending)
    error_reason: Mapped[str] = mapped_column(String, nullable=True)

    order = relationship("Order")


# --- Promotions --------------------------------------------------------------
class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    discount_type: Mapped[str] = mapped_column(String, default="percentage")  # percentage | flat
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_discount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    min_order_value: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    expiry_date: Mapped[dt.datetime] = mapped_column(DateTime, nullable=True)
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=True)       # global cap
    per_user_limit: Mapped[int] = mapped_column(Integer, nullable=True)    # per-user cap
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    redemptions = relationship("CouponRedemption", back_populates="coupon", cascade="all, delete-orphan")


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=True)
    redeemed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    coupon = relationship("Coupon", back_populates="redemptions")


class FestivalCampaign(Base, TimestampMixin):
    __tablename__ = "festival_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    banner_image_url: Mapped[str] = mapped_column(String, nullable=True)
    theme_color: Mapped[str] = mapped_column(String, default="#7C3AED")
    start_date: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    discount_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    coupon_code: Mapped[str] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class HomepageCollection(Base, TimestampMixin):
    __tablename__ = "homepage_collections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    product_ids: Mapped[list] = mapped_column(JSON, nullable=True)


# --- Engagement --------------------------------------------------------------
class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_review_user_product"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    verified_purchase: Mapped[bool] = mapped_column(Boolean, default=False)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="approved")  # approved | rejected | pending

    user = relationship("User", back_populates="reviews")
    product = relationship("Product", back_populates="reviews")


class ReviewVote(Base):
    __tablename__ = "review_votes"
    __table_args__ = (UniqueConstraint("user_id", "review_id", name="uq_reviewvote_user_review"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)


class ProductQuestion(Base, TimestampMixin):
    __tablename__ = "product_questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    answers = relationship("ProductAnswer", back_populates="question", cascade="all, delete-orphan")


class ProductAnswer(Base, TimestampMixin):
    __tablename__ = "product_answers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("product_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_staff_answer: Mapped[bool] = mapped_column(Boolean, default=False)

    question = relationship("ProductQuestion", back_populates="answers")


class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="wishlist_items")
    product = relationship("Product")


class Reminder(Base, TimestampMixin):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    occasion: Mapped[str] = mapped_column(String, nullable=True)
    recipient_name: Mapped[str] = mapped_column(String, nullable=True)
    reminder_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    recurrence: Mapped[str] = mapped_column(String, default="yearly")  # none | yearly | monthly
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="reminders")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, default="info")  # order | promo | reminder | info
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=True)
    link: Mapped[str] = mapped_column(String, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="notifications")


# --- Discovery ---------------------------------------------------------------
class RecentlyViewed(Base):
    __tablename__ = "recently_viewed"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_recent_user_product"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    viewed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    product = relationship("Product")


class BackInStockSubscription(Base):
    __tablename__ = "back_in_stock_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_bis_user_product"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    product = relationship("Product")
    user = relationship("User")


class SavedPaymentMethod(Base):
    """Non-sensitive saved payment preference (no PAN/card data stored)."""
    __tablename__ = "saved_payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String, nullable=False)   # e.g. "HDFC •••• 4242", "UPI: name@bank"
    method_type: Mapped[str] = mapped_column(String, default="card")  # card | upi | netbanking | cod
    last4: Mapped[str] = mapped_column(String, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


# --- Wallet (loyalty points / store credit / gift-card redemption) -----------
class WalletTransaction(Base):
    """A single credit/debit on a user's wallet. Balance = SUM(amount).

    amount is in rupees; positive = credit (earned/refunded/gift card),
    negative = debit (redeemed at checkout).
    """
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)  # earn|redeem|giftcard|referral|refund|adjust
    reference: Mapped[str] = mapped_column(String, nullable=True)  # order number / gift card code
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class GiftCard(Base, TimestampMixin):
    __tablename__ = "gift_cards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    initial_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    balance: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    purchaser_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    recipient_email: Mapped[str] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# --- Corporate gifting -------------------------------------------------------
class CorporateAccount(Base, TimestampMixin):
    __tablename__ = "corporate_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    gst_number: Mapped[str] = mapped_column(String, nullable=True)
    billing_email: Mapped[str] = mapped_column(String, nullable=True)
    credit_limit: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    discount_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    members = relationship("User", back_populates="corporate_account")


# --- Shipping ----------------------------------------------------------------
class Shipment(Base, TimestampMixin):
    """Carrier shipment for an order, with its own event timeline."""
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"),
                                          nullable=False, unique=True, index=True)
    carrier: Mapped[str] = mapped_column(String, default="WishBox Express")
    tracking_number: Mapped[str] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, default="label_created")  # label_created|in_transit|out_for_delivery|delivered|failed
    estimated_delivery: Mapped[dt.date] = mapped_column(Date, nullable=True)
    shipped_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=True)

    order = relationship("Order")
    events = relationship("ShipmentEvent", back_populates="shipment",
                          cascade="all, delete-orphan", order_by="ShipmentEvent.created_at")


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=True)
    note: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    shipment = relationship("Shipment", back_populates="events")


# --- Returns / exchanges -----------------------------------------------------
class ReturnRequest(Base, TimestampMixin):
    __tablename__ = "return_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, default="return")   # return | exchange
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="requested")  # requested|approved|rejected|picked_up|refunded|completed
    refund_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    resolution_note: Mapped[str] = mapped_column(String, nullable=True)

    order = relationship("Order")
    items = relationship("ReturnItem", back_populates="return_request", cascade="all, delete-orphan")


class ReturnItem(Base):
    __tablename__ = "return_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    return_request = relationship("ReturnRequest", back_populates="items")
    order_item = relationship("OrderItem")


# --- Invoices ----------------------------------------------------------------
class Invoice(Base):
    """GST tax invoice for an order. Generated lazily; one per order."""
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"),
                                          nullable=False, unique=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    seller_gstin: Mapped[str] = mapped_column(String, nullable=True)
    place_of_supply: Mapped[str] = mapped_column(String, nullable=True)
    gst_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    # Money breakdown (taxable_value + gst == goods total; +shipping -discount == order total)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    shipping_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    taxable_value: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    cgst: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    sgst: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    igst: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    order = relationship("Order")


# --- Outbox (email / SMS) ----------------------------------------------------
class OutboxMessage(Base):
    """Queued outbound email/SMS. Dispatched by the background worker.

    Default mode prints to the console (fully offline) and marks the row sent;
    if SMTP / Twilio creds are configured the worker sends for real.
    """
    __tablename__ = "outbox_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    channel: Mapped[str] = mapped_column(String, default="email")  # email | sms
    to_address: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)  # queued | sent | failed
    error: Mapped[str] = mapped_column(String, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=True)


# --- Auth tokens (email verification / password reset) -----------------------
class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # verify_email | reset_password
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)


# --- Support (FAQ + tickets) -------------------------------------------------
class FaqEntry(Base, TimestampMixin):
    __tablename__ = "faq_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question: Mapped[str] = mapped_column(String, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, default="General")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SupportTicket(Base, TimestampMixin):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    order_number: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")  # open|pending|resolved|closed
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    messages = relationship("TicketMessage", back_populates="ticket",
                            cascade="all, delete-orphan", order_by="TicketMessage.created_at")


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)

    ticket = relationship("SupportTicket", back_populates="messages")


# --- Audit -------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity: Mapped[str] = mapped_column(String, nullable=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_utcnow)
