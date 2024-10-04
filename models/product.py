from pydantic import BaseModel, Field
from typing import Union

class ImageInfo(BaseModel):
    id: str
    url: str

class ProductBase(BaseModel):
    collection_name: str
    product_name: str

class ProductCreateIn(ProductBase):
    image_paths: list[str]

class ProductCreateOut(ProductBase):
    product_id: str
    image_paths: list[ImageInfo]

class ProductUpdateNameIn(BaseModel):
    collection_name: str
    product_new_name: str

class ProductUpdateImageIn(BaseModel):
    collection_name: str
    product_name: str
    image_paths: list[ImageInfo]

class ProductRecognitionCountIn(BaseModel):
    collection_name: str
    image_paths: list[str]

class ProductShelfAvailibilityIn(BaseModel):
    collection_name: str
    image_paths: list[str]
    product_checks: dict
    sku_threshold: Union[float, None] = 0.7