from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator


def _utc_datetime(value: datetime) -> datetime:
    if value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

class Register(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)

class Login(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_admin: bool
    model_config = {"from_attributes": True}

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class ProductIn(BaseModel):
    name: str
    description: str = ""
    price: Decimal = Field(gt=0)
    image_url: str = ""
    stock: int = Field(ge=0)
    category_id: Optional[int] = None
    is_featured: bool = False

class ProductOut(ProductIn):
    id: int
    slug: str
    model_config = {"from_attributes": True}

class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    model_config = {"from_attributes": True}

class CartAdd(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)

class CartUpdate(BaseModel):
    quantity: int = Field(ge=1)

class CartItemOut(BaseModel):
    product_id: int
    name: str
    price: Decimal
    image_url: str
    quantity: int
    subtotal: Decimal

class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal

class OrderCreate(BaseModel):
    shipping_address: str = Field(min_length=1, max_length=500)

    @field_validator("shipping_address", mode="before")
    @classmethod
    def trim_shipping_address(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int

class OrderOut(BaseModel):
    id: int
    status: str
    total: Decimal
    shipping_address: str
    created_at: datetime
    items: list[OrderItemOut]
    model_config = {"from_attributes": True}

class ChatRequest(BaseModel):
    session_id: int
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message", mode="before")
    @classmethod
    def trim_message(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> datetime:
        return _utc_datetime(value)

class ChatHistoryOut(BaseModel):
    messages: list[ChatMessageOut]

class ChatSessionOut(BaseModel):
    id: int

class ChatSessionSummaryOut(BaseModel):
    id: int
    preview: str
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime) -> datetime:
        return _utc_datetime(value)

class ChatProductOut(BaseModel):
    id: int
    name: str
    description: str
    price: Decimal
    image_url: str
    stock: int
    category_name: str

class ChatReplyOut(BaseModel):
    answer: ChatMessageOut
    messages: list[ChatMessageOut]
    products: list[ChatProductOut]
