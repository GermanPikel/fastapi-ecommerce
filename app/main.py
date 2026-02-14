from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from loguru import logger
from uuid import uuid4
from fastapi.responses import JSONResponse

from app.routers import categories, products, users, reviews, cart, orders

logger.add("info.log", format="Log: [{extra[log_id]}:{time} - {level} - {message}]", level="INFO", enqueue=True)

app = FastAPI(
    title="FastAPI интернет-магазин",
    version="0.1.0",
)


@app.middleware("http")
async def log_middleware(request: Request, call_next):
    log_id = str(uuid4())
    with logger.contextualize(log_id=log_id):
        try:
            response = await call_next(request)
            if response.status_code in [401, 402, 403, 404]:
                logger.warning(f"Request to {request.url.path} failed")
            else:
                logger.info("Successfully accessed " + request.url.path)
        except Exception as ex:
            logger.error(f"Request to {request.url.path} failed: {ex}")
            response = JSONResponse(content={"succcess": False}, status_code=500)
        return response


app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(categories.router)
app.include_router(products.router)
app.include_router(users.router)
app.include_router(reviews.router)
app.include_router(cart.router)
app.include_router(orders.router)


@app.get('/')
async def root():
    """
    Корневой маршрут, подтверждающий, что API работает.
    """
    return {'message': 'Добро пожаловать в API интернет магазин!'}