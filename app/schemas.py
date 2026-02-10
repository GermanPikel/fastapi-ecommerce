from pydantic import BaseModel, Field, ConfigDict, EmailStr
from decimal import Decimal
from datetime import datetime


class CategoryCreate(BaseModel):
    """
        Модель для создания и обновления категории.
        Используется в POST и PUT запросах.
    """
    name: str = Field(..., min_length=3, max_length=50, description="Название категории (3-50 символов)")
    parent_id: int | None = Field(default=None, description="ID родительской категории, если есть")


class Category(CategoryCreate):
    """
        Модель для ответа с данными категории.
        Используется в GET-запросах.
    """
    id: int = Field(..., description="Уникальный идентификатор категории")
    is_active: bool = Field(..., description="Активность категории")

    model_config = ConfigDict(from_attributes=True)  # Обеспечивает совместимость с ORM, \
    # позволяя преобразовывать данные из базы в JSON-ответы


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, description="Название товара (3-100 символов)")
    description: str | None = Field(default=None, max_length=500, description="Описание товара (до 500 символов)")
    price: Decimal = Field(..., gt=0, description="Цена товара (больше 0)", decimal_places=2)
    image_url: str | None = Field(default=None, max_length=200, description="URL изображения товара")
    stock: int = Field(..., ge=0, description="Количество товара на складе (0 или больше)")
    category_id: int = Field(..., description="ID категории, к которой относится товар")


class Product(ProductCreate):
    id: int = Field(..., description="Уникальный идентификатор товара")
    is_active: bool = Field(..., description="Активность товара")

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr = Field(description="Email пользователя")
    password: str = Field(min_length=8, description="Пароль (минимум 8 символов)")
    role: str = Field(default="buyer", pattern="^(buyer|seller|admin)$",
                      description="Роль: 'buyer' или 'seller' или 'admin'")


class User(BaseModel):
    id: int
    email: EmailStr
    role: str
    model_config = ConfigDict(from_attributes=True)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ReviewCreate(BaseModel):
    product_id: int = Field(...)
    comment: str | None = Field(default=None)
    grade: int = Field(ge=1, le=5)


class Review(BaseModel):
    id: int = Field(...)
    user_id: int = Field(...)
    product_id: int = Field(...)
    comment: str | None = Field(default=None)
    comment_date: datetime = Field(default_factory=datetime.now)
    grade: int = Field(ge=1, le=5)
    is_active: bool = Field(default=True)

    model_config = ConfigDict(from_attributes=True)
