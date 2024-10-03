from fastapi import FastAPI
from routers import collections, products

app = FastAPI()

app.include_router(collections.router)
app.include_router(products.router)

