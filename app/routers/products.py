from datetime import datetime
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import Product as ProductSchema, ProductCreate, Review as ReviewSchema, ProductList
from app.models.products import Product as ProductModel
from app.models.categories import Category as CategoryModel
from app.db_depends import get_async_db
from app.models.users import User as UserModel
from app.models.reviews import Review as ReviewModel
from app.auth import get_current_seller


BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media" / "products"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2 097 152 байт


router = APIRouter(
    prefix='/products',
    tags=['products']
)


async def save_product_image(file: UploadFile) -> str:
    """
    Сохраняет изображение товара и возвращает относительный URL.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only JPG, PNG or WebP images are allowed")

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image is too large")

    extension = Path(file.filename or "").suffix.lower() or ".jpg"
    file_name = f"{uuid.uuid4()}{extension}"
    file_path = MEDIA_ROOT / file_name
    file_path.write_bytes(content)

    return f"/media/products/{file_name}"


def remove_product_image(url: str | None) -> None:
    """
    Удаляет файл изображения, если он существует.
    """
    if not url:
        return
    relative_path = url.lstrip("/")
    file_path = BASE_DIR / relative_path
    if file_path.exists():
        file_path.unlink()


@router.get('/', response_model=ProductList, status_code=status.HTTP_200_OK)
async def get_all_products(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        category_id: int | None = Query(default=None, description="Id категории для фильтрации"),
        search: str | None = Query(None, min_length=1, description="Поиск по названию товара"),
        min_price: float | None = Query(default=None, ge=0, description="Минимальная цена товара"),
        max_price: float | None = Query(default=None, ge=0, description="Максимальная цена товара"),
        in_stock: bool | None = Query(default=None,
                                      description="true — только товары в наличии, false — только без остатка"),
        seller_id: int | None = Query(None, description="ID продавца для фильтрации"),
        created_at: datetime | None = Query(default=None, description="Фильтр по дате создания товара"),
        db: AsyncSession = Depends(get_async_db)
):
    """
    Возвращает список всех активных товаров с поддержкой фильтров.
    """

    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price не может быть больше max_price",
        )

    filters = [ProductModel.is_active == True]

    if category_id is not None:
        filters.append(ProductModel.category_id == category_id)
    if search is not None:
        search_value = search.strip()
        if search_value:
            filters.append(func.lower(ProductModel.name).like(f"%{search_value.lower()}%"))
    if min_price is not None:
        filters.append(ProductModel.price >= min_price)
    if max_price is not None:
        filters.append(ProductModel.price <= max_price)
    if in_stock is not None:
        filters.append(ProductModel.stock > 0 if in_stock else ProductModel.stock == 0)
    if seller_id is not None:
        filters.append(ProductModel.seller_id == seller_id)
    if created_at is not None:
        filters.append(ProductModel.created_at >= created_at)

    total_stmt = select(func.count()).select_from(ProductModel).where(*filters)

    rank_col = None
    # TODO: tsv
    # if search:
    #     search_value = search.strip()
    #     if search_value:
    #         ts_query = func.websearch_to_tsquery('english', search_value)
    #         filters.append(ProductModel.tsv.op('@@')(ts_query))
    #         rank_col = func.ts_rank_cd(ProductModel.tsv, ts_query).label("rank")
    #         # total с учётом полнотекстового фильтра
    #         total_stmt = select(func.count()).select_from(ProductModel).where(*filters)

    total = await db.scalar(total_stmt) or 0

    if rank_col is not None:
        products_stmt = (
            select(ProductModel, rank_col)
            .where(*filters)
            .order_by(desc(rank_col), ProductModel.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(products_stmt)
        rows = result.all()
        items = [row[0] for row in rows]
    else:
        products_stmt = (
            select(ProductModel)
            .where(*filters)
            .order_by(ProductModel.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = (await db.scalars(products_stmt)).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.post('/', response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
async def create_product(
        product_create: ProductCreate = Depends(ProductCreate.as_form),
        image: UploadFile | None = File(None),
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_seller)
):
    """
        Эндпоинт для создания товара
    """
    stmt = select(CategoryModel).where(CategoryModel.id == product_create.category_id,
                                       CategoryModel.is_active == True)
    tmp = await db.scalars(stmt)
    find_category = tmp.first()
    if find_category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")

    image_url = await save_product_image(image) if image else None

    db_product = ProductModel(
        **product_create.model_dump(),
        seller_id=current_user.id,
        image_url=image_url
    )

    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product


@router.get('/category/{category_id}', response_model=list[ProductSchema], status_code=status.HTTP_200_OK)
async def get_products_by_category(category_id: int, db: AsyncSession = Depends(get_async_db)):
    """
        Эндпоинт для получения товаров из определенной категории
    """
    query = select(CategoryModel).where(CategoryModel.id == category_id,
                                        CategoryModel.is_active == True)
    tmp = await db.scalars(query)
    result = tmp.first()
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found or inactive")

    query = select(ProductModel).where(ProductModel.category_id == category_id,
                                       ProductModel.is_active == True)
    tmp2 = await db.scalars(query)
    products = tmp2.all()

    return products


@router.get('/{product_id}', response_model=ProductSchema, status_code=status.HTTP_200_OK)
async def get_product(product_id: int, db: AsyncSession = Depends(get_async_db)):
    """
        Эндпоинт для получения информации о товаре
    """
    query = select(ProductModel).where(ProductModel.id == product_id,
                                       ProductModel.is_active == True)
    tmp = await db.scalars(query)
    product = tmp.first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    tmp = await db.scalars(
        select(CategoryModel).where(CategoryModel.id == product.category_id,
                                    CategoryModel.is_active == True)
    )
    category = tmp.first()
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Category not found or inactive")

    return product


@router.put("/{product_id}", response_model=ProductSchema, status_code=status.HTTP_200_OK)
async def update_product(
        product_id: int,
        product: ProductCreate = Depends(ProductCreate.as_form),
        image: UploadFile | None = File(None),
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_seller)):
    """
        Эндпоинт для обновления товара
    """
    query = select(ProductModel).where(ProductModel.id == product_id,
                                       ProductModel.is_active == True)
    tmp = await db.scalars(query)
    db_product = tmp.first()
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")
    if db_product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own products")

    query2 = select(CategoryModel).where(CategoryModel.id == product.category_id,
                                         CategoryModel.is_active == True)
    tmp2 = await db.scalars(query2)
    result2 = tmp2.first()
    if result2 is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")

    update_data = product.model_dump(exclude_unset=True)
    await db.execute(
        update(ProductModel)
        .where(ProductModel.id == product_id)
        .values(**update_data)
    )
    if image:
        remove_product_image(db_product.image_url)
        db_product.image_url = await save_product_image(image)
    await db.commit()
    await db.refresh(db_product)
    return db_product


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_product(
        product_id: int,
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_seller)
):
    """
        Эндпоинт для удаления товара
    """
    query = select(ProductModel).where(ProductModel.id == product_id,
                                       ProductModel.is_active == True)
    tmp = await db.scalars(query)
    product = tmp.first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found or inactive")
    if product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your products")

    await db.execute(
        update(ProductModel)
        .where(ProductModel.id == product_id)
        .values(is_active=False)
    )
    # product.is_active = False  # TODO: можно так создавать логическое удаление
    remove_product_image(product.image_url)
    await db.commit()
    await db.refresh(product)
    return {"status": "success", "message": "Product marked as inactive"}


@router.get('/{product_id}/reviews', response_model=list[ReviewSchema], status_code=status.HTTP_200_OK)
async def get_product_reviews(product_id: int, db: AsyncSession = Depends(get_async_db)):
    """
        Эндпоинт для просмотра отзывов о товаре
    """
    product_stmt = select(ProductModel).where(ProductModel.id == product_id,
                                              ProductModel.is_active)
    product = await db.scalar(product_stmt)

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    reviews_stmt = select(ReviewModel).where(ReviewModel.product_id == product_id,
                                             ReviewModel.is_active == True)
    reviews = (await db.scalars(reviews_stmt)).all()
    return reviews
