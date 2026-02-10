from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.categories import Category as CategoryModel
from app.models import User as UserModel
from app.schemas import Category as CategorySchema, CategoryCreate
from app.db_depends import get_db
from app.db_depends import get_async_db
from app.auth import get_current_admin


router = APIRouter(
    prefix="/categories",
    tags=['categories']
)


@router.get('/', response_model=list[CategorySchema])
async def get_all_categories(db: AsyncSession = Depends(get_async_db)):
    """
        Возвращает список всех активных категорий.
    """
    result = await db.scalars(select(CategoryModel).where(CategoryModel.is_active==True))
    categories = result.all()
    return categories


@router.post('/',
             response_model=CategorySchema,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(get_current_admin)])
async def create_category(category: CategoryCreate, db: AsyncSession = Depends(get_async_db)):
    """
        Создаёт новую категорию.
    """
    if category.parent_id is not None:
        stmt = select(CategoryModel).where(CategoryModel.id == category.parent_id,
                                           CategoryModel.is_active == True)
        result = await db.scalars(stmt)
        parent = result.first()
        if parent is None:
            raise HTTPException(status_code=400, detail="Parent not found")

    db_category = CategoryModel(**category.model_dump())
    # db.add() - синхронная операция
    db.add(db_category)  # добавляет объект в текущую сессию БД. Это подготавливает объект к сохранению в базе, но пока не записывает его
    await db.commit()  # фиксируем изменения в БД, сохраняя новую категорию в таблице categories. В БД создается новая запись, и сгенерированное поле id становится доступным
    # db.refresh(db_category)  # обновляем объект db_category, чтобы он содержал актуальные данные из БД, включая автоматически сгенеренное поле id и другие значения, которые устанавливаются сервером самостоятельно
    return db_category


@router.put('/{category_id}',
            response_model=CategorySchema,
            dependencies=[Depends(get_current_admin)])
async def update_category(category_id: int, category: CategoryCreate, db: AsyncSession = Depends(get_async_db)):
    """
        Обновляет категорию по её ID.
    """
    stmt = select(CategoryModel).where(CategoryModel.id == category_id,
                                       CategoryModel.is_active == True)
    result = await db.scalars(stmt)
    db_category = result.first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.parent_id is not None:
        parent_stmt = select(CategoryModel).where(CategoryModel.id == category.parent_id,
                                                  CategoryModel.is_active == True)
        parent_result = await db.scalars(parent_stmt)
        parent = parent_result.first()
        if parent is None:
            raise HTTPException(status_code=400, detail="Parent category not found")

    update_data = category.model_dump(exclude_unset=True)  # exclude_unset=True обновляет только переданные поля
    await db.execute(
        update(CategoryModel)
        .where(CategoryModel.id == category_id)
        .values(**update_data)
    )
    await db.commit()
    # db.refresh(db_category)
    return db_category


@router.delete('/{category_id}',
               status_code=status.HTTP_200_OK,
               dependencies=[Depends(get_current_admin)])
async def delete_category(category_id: int, db: AsyncSession = Depends(get_async_db)):
    """
        Логически удаляет категорию по её ID, устанавливая is_active=False.
    """
    stmt = select(CategoryModel).where(CategoryModel.id == category_id, CategoryModel.is_active == True)
    result = await db.scalars(stmt)
    category = result.first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(is_active=False))
    await db.commit()

    return {"status": "success", "message": "Category marked as inactive"}