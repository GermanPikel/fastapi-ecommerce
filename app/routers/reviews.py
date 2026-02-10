from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.sql import func

from app.db_depends import get_async_db
from app.schemas import Review as ReviewSchema, ReviewCreate
from app.models.reviews import Review as ReviewModel
from app.models.products import Product as ProductModel
from app.models.users import User as UserModel
from app.auth import get_current_buyer, get_current_user


async def update_product_rating(db: AsyncSession, product_id: int):
    result = await db.execute(
        select(func.avg(ReviewModel.grade)).where(
            ReviewModel.product_id == product_id,
            ReviewModel.is_active == True
        )
    )
    avg_rating = result.scalar() or 0.0
    product = await db.get(ProductModel, product_id)
    product.rating = avg_rating
    await db.commit()

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"]
)


@router.get('/', response_model=list[ReviewSchema], status_code=status.HTTP_200_OK)
async def get_all_reviews(db: AsyncSession = Depends(get_async_db)):
    """
        Эндпоинт для просмотра всех активных отзывов о товарах
    """
    reviews_stmt = select(ReviewModel).where(ReviewModel.is_active == True)
    reviews = await db.scalars(reviews_stmt)
    return reviews.all()


@router.post('/', response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_new_review(review_create: ReviewCreate,
                          db: AsyncSession = Depends(get_async_db),
                          current_user: UserModel = Depends(get_current_buyer)):
    """
        Эндпоинт для создания отзыва о товаре
    """
    product_stmt = select(ProductModel).where(ProductModel.id == review_create.product_id,
                                              ProductModel.is_active == True)
    product = await db.scalar(product_stmt)

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    if review_create.grade < 1 or review_create.grade > 5:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Grade must be in range [1, 5]")

    review = ReviewModel(**review_create.model_dump(), user_id=current_user.id)
    db.add(review)
    await db.commit()
    await db.refresh(review)

    await update_product_rating(db, product_id=review.product_id)

    return review


@router.delete('/{review_id}', status_code=status.HTTP_200_OK)
async def delete_review(review_id: int,
                        db: AsyncSession = Depends(get_async_db),
                        current_user: UserModel = Depends(get_current_user)):
    """
        Эндпоинт для удаления отзыва о товаре
    """
    review_stmt = select(ReviewModel).where(ReviewModel.id == review_id,
                                            ReviewModel.is_active == True)
    review = await db.scalar(review_stmt)

    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review is not found or inactive")

    if not (current_user.role == "admin" or review.user_id == current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only admins and review's creator can delete this review")

    await db.execute(
        update(ReviewModel)
        .where(ReviewModel.id == review_id)
        .values(is_active=False)
    )
    await db.commit()
    await db.refresh(review)

    await update_product_rating(db, product_id=review.product_id)

    return {"message": "Review deleted"}
