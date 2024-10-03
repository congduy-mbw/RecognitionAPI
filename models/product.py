from pydantic import BaseModel

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

class ProductRecognitionCount(BaseModel):
    collection_name: str
    image_paths: list[str]