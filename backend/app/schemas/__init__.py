"""Pydantic v2 request/response schemas for WishBox."""
import datetime as dt
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ORM = ConfigDict(from_attributes=True)


# --- Auth & Users ------------------------------------------------------------
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1)
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)


class UserOut(BaseModel):
    model_config = ORM
    id: int
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    email_verified: bool = False
    created_at: dt.datetime


class MessageResponse(BaseModel):
    detail: str


class EmailRequest(BaseModel):
    email: EmailStr


class TokenConfirm(BaseModel):
    token: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class AdminCustomerOut(BaseModel):
    model_config = ORM
    id: int
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    created_at: dt.datetime
    order_count: int = 0
    total_spent: Decimal = Decimal(0)


# --- Addresses ---------------------------------------------------------------
class AddressBase(BaseModel):
    title: str = "Home"
    recipient_name: str
    phone: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str = "India"
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressOut(AddressBase):
    model_config = ORM
    id: int


# --- Catalog -----------------------------------------------------------------
class TagOut(BaseModel):
    model_config = ORM
    id: int
    name: str
    kind: str


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    occasion_group: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0
    mega_menu_group: Optional[str] = None
    is_badge_new: bool = False


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    occasion_group: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    mega_menu_group: Optional[str] = None
    is_badge_new: Optional[bool] = None


class CategoryOut(CategoryBase):
    model_config = ORM
    id: int
    slug: str
    is_active: bool


class CategoryTreeOut(BaseModel):
    model_config = ORM
    id: int
    name: str
    slug: str
    parent_id: Optional[int] = None
    occasion_group: Optional[str] = None
    mega_menu_group: Optional[str] = None
    is_badge_new: bool = False
    children: List["CategoryTreeOut"] = []


CategoryTreeOut.model_rebuild()


class ProductImageOut(BaseModel):
    model_config = ORM
    id: int
    image_url: str
    sort_order: int = 0


class ProductOut(BaseModel):
    model_config = ORM
    id: int
    sku: Optional[str] = None
    name: str
    slug: str
    description: Optional[str] = None
    price: Decimal
    discount_price: Optional[Decimal] = None
    currency: str = "INR"
    image_url: Optional[str] = None
    stock: int
    category_id: int
    vendor_id: Optional[int] = None
    is_customizable: bool
    type: str
    is_quick_delivery: bool = False
    is_active: bool = True
    rating_avg: Decimal = Decimal(0)
    rating_count: int = 0
    created_at: dt.datetime


class ProductDetailOut(ProductOut):
    category: CategoryOut
    images: List[ProductImageOut] = []
    tags: List[TagOut] = []


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    discount_price: Optional[Decimal] = None
    image_url: Optional[str] = None
    stock: int = 0
    category_id: int
    vendor_id: Optional[int] = None
    sku: Optional[str] = None
    is_customizable: bool = False
    type: str = "hamper"
    is_quick_delivery: bool = False
    tags: List[str] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    discount_price: Optional[Decimal] = None
    image_url: Optional[str] = None
    stock: Optional[int] = None
    category_id: Optional[int] = None
    vendor_id: Optional[int] = None
    is_customizable: Optional[bool] = None
    type: Optional[str] = None
    is_quick_delivery: Optional[bool] = None
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None


class PaginatedProducts(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ProductOut]


class AutocompleteSuggestion(BaseModel):
    name: str
    slug: str


class AutocompleteResponse(BaseModel):
    products: List[AutocompleteSuggestion] = []
    categories: List[AutocompleteSuggestion] = []


# --- Cart --------------------------------------------------------------------
class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)
    customization_details: Optional[Dict[str, Any]] = None


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)
    customization_details: Optional[Dict[str, Any]] = None


class CartItemOut(BaseModel):
    model_config = ORM
    id: int
    product_id: int
    quantity: int
    customization_details: Optional[Dict[str, Any]] = None
    product: ProductOut


class CartSummary(BaseModel):
    items: List[CartItemOut]
    subtotal: Decimal
    item_count: int


# --- Orders ------------------------------------------------------------------
class OrderItemOut(BaseModel):
    model_config = ORM
    id: int
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    customization_details: Optional[Dict[str, Any]] = None


class OrderStatusHistoryOut(BaseModel):
    model_config = ORM
    id: int
    status: str
    note: Optional[str] = None
    created_at: dt.datetime


class OrderCreate(BaseModel):
    address_id: int
    payment_method: str = "cod"
    coupon_code: Optional[str] = None
    is_gift: bool = False
    gift_message: Optional[str] = None
    scheduled_delivery_date: Optional[dt.date] = None
    delivery_slot: Optional[str] = None


class OrderOut(BaseModel):
    model_config = ORM
    id: int
    order_number: str
    subtotal: Decimal
    discount_amount: Decimal
    shipping_fee: Decimal
    total_amount: Decimal
    recipient_name: str
    recipient_phone: Optional[str] = None
    ship_address_line1: str
    ship_city: str
    ship_state: str
    ship_postal_code: str
    is_gift: bool
    gift_message: Optional[str] = None
    scheduled_delivery_date: Optional[dt.date] = None
    delivery_slot: Optional[str] = None
    payment_method: str
    payment_status: str
    status: str
    tracking_code: Optional[str] = None
    coupon_code: Optional[str] = None
    created_at: dt.datetime
    items: List[OrderItemOut] = []
    history: List[OrderStatusHistoryOut] = []


class InvoiceOut(BaseModel):
    model_config = ORM
    id: int
    order_id: int
    invoice_number: str
    seller_gstin: Optional[str] = None
    place_of_supply: Optional[str] = None
    gst_percent: Decimal
    subtotal: Decimal
    discount_amount: Decimal
    shipping_fee: Decimal
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    total_amount: Decimal
    created_at: dt.datetime


class OrderStatusUpdate(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None
    tracking_code: Optional[str] = None
    note: Optional[str] = None


# --- Shipping ----------------------------------------------------------------
class ShipmentEventOut(BaseModel):
    model_config = ORM
    id: int
    status: str
    location: Optional[str] = None
    note: Optional[str] = None
    created_at: dt.datetime


class ShipmentOut(BaseModel):
    model_config = ORM
    id: int
    order_id: int
    carrier: str
    tracking_number: Optional[str] = None
    status: str
    estimated_delivery: Optional[dt.date] = None
    shipped_at: Optional[dt.datetime] = None
    delivered_at: Optional[dt.datetime] = None
    events: List[ShipmentEventOut] = []


class ShipmentUpdate(BaseModel):
    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    status: Optional[str] = None          # label_created|in_transit|out_for_delivery|delivered|failed
    estimated_delivery: Optional[dt.date] = None
    location: Optional[str] = None
    note: Optional[str] = None


# --- Returns / exchanges -----------------------------------------------------
class ReturnItemIn(BaseModel):
    order_item_id: int
    quantity: int = Field(default=1, ge=1)


class ReturnCreate(BaseModel):
    kind: str = "return"                  # return | exchange
    reason: str
    items: List[ReturnItemIn] = []


class ReturnItemOut(BaseModel):
    model_config = ORM
    id: int
    order_item_id: int
    quantity: int


class ReturnOut(BaseModel):
    model_config = ORM
    id: int
    order_id: int
    user_id: int
    kind: str
    reason: str
    status: str
    refund_amount: Decimal
    resolution_note: Optional[str] = None
    created_at: dt.datetime
    items: List[ReturnItemOut] = []


class ReturnUpdate(BaseModel):
    status: Optional[str] = None          # approved|rejected|picked_up|refunded|completed
    resolution_note: Optional[str] = None


# --- Payments ----------------------------------------------------------------
class PaymentCreateRequest(BaseModel):
    order_number: str


class PaymentCreateResponse(BaseModel):
    provider: str
    provider_order_id: str
    amount: int           # minor units (paise)
    currency: str = "INR"
    order_number: str
    key_id: str
    mock: Optional[Dict[str, str]] = None  # mock gateway hands back a valid payment_id+signature


class PaymentVerifyRequest(BaseModel):
    provider_order_id: str
    provider_payment_id: str
    provider_signature: str


# --- Coupons -----------------------------------------------------------------
class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str = "percentage"
    discount_value: Decimal
    max_discount: Optional[Decimal] = None
    min_order_value: Decimal = Decimal(0)
    expiry_date: Optional[dt.datetime] = None
    usage_limit: Optional[int] = None
    per_user_limit: Optional[int] = None
    active: bool = True


class CouponOut(BaseModel):
    model_config = ORM
    id: int
    code: str
    description: Optional[str] = None
    discount_type: str
    discount_value: Decimal
    max_discount: Optional[Decimal] = None
    min_order_value: Decimal
    expiry_date: Optional[dt.datetime] = None
    usage_limit: Optional[int] = None
    per_user_limit: Optional[int] = None
    times_used: int = 0
    active: bool


class CouponValidateRequest(BaseModel):
    code: str
    subtotal: Decimal


class CouponValidateResponse(BaseModel):
    valid: bool
    discount: Decimal = Decimal(0)
    message: str


# --- Reviews -----------------------------------------------------------------
class ReviewCreate(BaseModel):
    product_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class ReviewOut(BaseModel):
    model_config = ORM
    id: int
    user_id: int
    product_id: int
    rating: int
    comment: Optional[str] = None
    verified_purchase: bool = False
    helpful_count: int = 0
    created_at: dt.datetime
    user_name: Optional[str] = None


# --- Wishlist / Reminders / Notifications ------------------------------------
class WishlistItemOut(BaseModel):
    model_config = ORM
    id: int
    product_id: int
    created_at: dt.datetime
    product: ProductOut


class ReminderCreate(BaseModel):
    title: str
    occasion: Optional[str] = None
    recipient_name: Optional[str] = None
    reminder_date: dt.date
    recurrence: str = "yearly"
    notes: Optional[str] = None


class ReminderOut(BaseModel):
    model_config = ORM
    id: int
    title: str
    occasion: Optional[str] = None
    recipient_name: Optional[str] = None
    reminder_date: dt.date
    recurrence: str
    notes: Optional[str] = None
    created_at: dt.datetime


class NotificationOut(BaseModel):
    model_config = ORM
    id: int
    type: str
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    is_read: bool
    created_at: dt.datetime


# --- Discovery ---------------------------------------------------------------
class RecentlyViewedOut(BaseModel):
    model_config = ORM
    id: int
    product_id: int
    viewed_at: dt.datetime
    product: ProductOut


class SavedPaymentMethodCreate(BaseModel):
    label: str
    method_type: str = "card"
    last4: Optional[str] = None
    is_default: bool = False


class SavedPaymentMethodOut(BaseModel):
    model_config = ORM
    id: int
    label: str
    method_type: str
    last4: Optional[str] = None
    is_default: bool
    created_at: dt.datetime


# --- Vendors -----------------------------------------------------------------
class VendorCreate(BaseModel):
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    lead_time_days: int = 2


class VendorOut(BaseModel):
    model_config = ORM
    id: int
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    lead_time_days: int
    is_active: bool


# --- Recommendations / Smart Finder ------------------------------------------
class SmartFinderRequest(BaseModel):
    message: Optional[str] = None
    occasion: Optional[str] = None
    relationship: Optional[str] = None
    budget: Optional[float] = None
    emotion: Optional[str] = None


class SmartFinderResponse(BaseModel):
    assistant_message: str
    insight_tags: List[str] = []
    products: List[ProductOut] = []
    parsed_intent: Optional[dict] = None
    source: str = "local-engine"  # "local-engine" | "llm"


# --- Hamper builder ----------------------------------------------------------
class HamperItemIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class HamperCreate(BaseModel):
    name: str = "My Hamper"
    occasion: Optional[str] = None
    box_style: Optional[str] = None
    gift_message: Optional[str] = None
    items: List[HamperItemIn] = []


class HamperItemOut(BaseModel):
    model_config = ORM
    id: int
    product_id: int
    quantity: int
    product: ProductOut


class HamperOut(BaseModel):
    model_config = ORM
    id: int
    name: str
    occasion: Optional[str] = None
    box_style: Optional[str] = None
    gift_message: Optional[str] = None
    is_template: bool
    items: List[HamperItemOut] = []


# --- Outbox ------------------------------------------------------------------
class OutboxMessageOut(BaseModel):
    model_config = ORM
    id: int
    channel: str
    to_address: str
    subject: Optional[str] = None
    body: str
    status: str
    error: Optional[str] = None
    created_at: dt.datetime
    sent_at: Optional[dt.datetime] = None


# --- Admin analytics ---------------------------------------------------------
class AdminSummaryOut(BaseModel):
    total_revenue: Decimal
    total_orders: int
    total_products: int
    total_users: int
    low_stock_count: int
    sales_by_category: Dict[str, float]
    monthly_sales: Dict[str, float]
    orders_by_status: Dict[str, int]
    recent_orders: List[OrderOut]
