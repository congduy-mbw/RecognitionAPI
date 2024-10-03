from fastapi import APIRouter, HTTPException
from controllers import product_ai
from models.product import ProductCreateIn, ProductCreateOut, ImageInfo, ProductUpdateNameIn, ProductUpdateImageIn, ProductRecognitionCountIn, ProductShelfAvailibilityIn
import uuid
import base64
import os
import datetime
import cv2
import numpy as np

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)

@router.post("", response_model=ProductCreateOut, summary="Thêm ảnh sản phẩm cho mô hình")
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

@router.put("/{product_id}/name", summary="Cập nhật tên sản phẩm trong mô hình")
async def update_name_product(product_id: str, item: ProductUpdateNameIn):
    if item.collection_name is None or item.collection_name == "":
        raise HTTPException(status_code=404, detail="Collection name is not empty")
    if item.product_new_name is None or item.product_new_name == "":
        raise HTTPException(status_code=404, detail="Product name is not empty")
    await product_ai.update_name_product(item.collection_name, product_id, item.product_new_name)

@router.put("/{product_id}/images", summary="Cập nhật ảnh sản phẩm trong mô hình")
async def update_images_product(product_id: str, item: ProductUpdateImageIn):
    if item.collection_name is None or item.collection_name == "":
        raise HTTPException(status_code=404, detail="Collection name is not empty")
    if product_id is None or product_id == "":
        raise HTTPException(status_code=404, detail="Product id is not empty")
    image_paths = [item_image.url for item_image in item.image_paths]
    image_ids = [item_image.id for item_image in item.image_paths]
    await product_ai.add_or_update_product(item.collection_name, product_id, item.product_name, image_paths, image_ids)

@router.delete("/{product_id}/images", summary="Xóa toàn bộ ảnh của một sản phẩm trong mô hình")
async def delete_images_product(product_id: str, collection_name: str):
    if collection_name is None or collection_name == "":
        raise HTTPException(status_code=404, detail="Collection name is not empty")
    if product_id is None or product_id == "":
        raise HTTPException(status_code=404, detail="Product id is not empty")
    await product_ai.delete_product(collection_name, product_id)

@router.delete("/{product_id}", summary="Xóa sản phẩm khỏi mô hình")
async def delete_product(product_id: str, collection_name: str):
    if collection_name is None or collection_name == "":
        raise HTTPException(status_code=404, detail="Collection name is not empty")
    if product_id is None or product_id == "":
        raise HTTPException(status_code=404, detail="Product id is not Empty")
    await product_ai.delete_product(collection_name, product_id)

@router.post("/count_recognition", summary="Đếm số lượng sản phẩm")
async def count_recognition(item: ProductRecognitionCountIn):
    if item.collection_name is None or item.collection_name == "":
        raise HTTPException(status_code=404, detail="Collection name is not empty")
    product_count = await product_ai.count_product(item.collection_name, item.image_paths)
    if product_count["status"] == "completed":
        # UPLOAD_DIRECTORY="uploads/"
        # if not os.path.exists(UPLOAD_DIRECTORY):
        #     os.makedirs(UPLOAD_DIRECTORY)
        # current_time = datetime.datetime.now()
        # time_string = current_time.strftime("%Y%m%d_%H%M%S")
        # for result in product_count["results"]:
        #     verbose = result["results"]["verbose"]
        #     file_location = f"{UPLOAD_DIRECTORY}/image_{time_string}.png"
        #     image_data = base64.b64decode(verbose["base64_image"])
        #     with open(file_location, "wb") as file:
        #         file.write(image_data)
        #     image = cv2.imread(file_location)
        #     for locate in verbose["locates"]:
        #         label = locate["label"]
        #         points = np.array(locate["points"])
        #         points = points.astype(np.int32)
        #         points = points.reshape((-1, 1, 2))
        #         cv2.polylines(image, [points], isClosed=True, color=(0, 255, 0), thickness=2)
        #         text_position = (points[0][0][0], points[0][0][1] - 10)
        #         cv2.putText(image, label, text_position, cv2.FONT_HERSHEY_SIMPLEX, 
        #             fontScale=0.8, color=(0, 255, 0), thickness=2)
        #         cv2.imwrite(f"{UPLOAD_DIRECTORY}/image_bbox_{time_string}.png", image)
        return product_count
    else:
        raise HTTPException(status_code=500, detail="Error Server AI")

@router.post("/shelf_availibility", summary="Kiểm tra sản phẩm tồn tại dựa theo điều kiện tồn tại")
async def shelf_availibility(item: ProductShelfAvailibilityIn):
    if item.collection_name is None or item.collection_name == "":
        raise HTTPException(status_code=404, detail="Collection name is not empty")
    response = await product_ai.shelf_availability_product(item.collection_name, item.image_paths, item.product_checks, item.sku_threshold)
    if response["status"] == "completed":
        return response
    else:
        raise HTTPException(status_code=500, detail="Error Server AI")

