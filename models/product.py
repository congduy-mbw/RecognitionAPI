from pydantic import BaseModel
from typing import Union

class ImageInfo(BaseModel):
    id: Union[str, None] = None
    url: str

class ProductBase(BaseModel):
    collection_name: str
    product_name: str

class ProductInfo(BaseModel):
    product_name: str

class ProductByCollectionOut(BaseModel):
    total: int
    products: list[ProductInfo]

class ProductCreateIn(ProductBase):
    image_paths: list[str]

class ImageResultInfo(BaseModel):
    id: str
    url: str
    status: str
    error: Union[str, None] = None

class ProductCreateOut(ProductBase):
    product_id: str
    image_paths: list[ImageResultInfo]

class ProductUpdateNameIn(BaseModel):
    collection_name: str
    product_new_name: str

class ProductUpdateImageIn(BaseModel):
    collection_name: str
    product_name: str
    image_paths: list[ImageInfo]

class ProductUpdateImageOut(BaseModel):
    collection_name: str
    product_name: str
    product_id: str
    image_paths: list[ImageResultInfo]

class ProductImageInfo(BaseModel):
    image_id: str
    product_name: str

class ProductImagesByProductOut(BaseModel):
    product_id: str
    total: int
    images: list[ProductImageInfo]

class ProductRecognitionCountIn(BaseModel):
    collection_name: str
    image_paths: list[str]

class ProductShelfAvailibilityIn(BaseModel):
    collection_name: str
    image_paths: list[str]
    product_checks: dict
    sku_threshold: Union[float, None] = 0.7