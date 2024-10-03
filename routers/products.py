from fastapi import APIRouter, HTTPException
from controllers import product_ai
from models.product import ProductCreateIn, ProductCreateOut, ImageInfo, ProductRecognitionCount
import uuid

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)

@router.post("", response_model=ProductCreateOut)
async def create_product(item: ProductCreateIn):
    if item.collection_name is None or item.collection_name == "":
        raise HTTPException(status_code=404, detail="Collection name is not empty")
    if item.product_name is None or item.product_name == "":
        raise HTTPException(status_code=404, detail="Product name is not empty")
    product_id = str(uuid.uuid4())
    image_ids: list[str] = []
    images_info: list[ImageInfo] = []
    for image_path in item.image_paths:
        image_id = str(uuid.uuid4())
        image_ids.append(image_id)
        image_info: ImageInfo = ImageInfo(id=image_id, url=image_path)
        images_info.append(image_info)
    await product_ai.add_or_update_product(item.collection_name, product_id, item.product_name, item.image_paths, image_ids)
    return ProductCreateOut(
        collection_name = item.collection_name,
        product_id = product_id,
        product_name = item.product_name,
        image_paths = images_info
    )  

@router.post("/count_recognition")
async def count_recognition(item: ProductRecognitionCount):
    product_count = await product_ai.count_product(item.collection_name, item.image_paths)
    if product_count["status"] == "completed":
        return product_count["sum_count"]
    else:
        raise HTTPException(status_code=500, detail="Error Server AI")

