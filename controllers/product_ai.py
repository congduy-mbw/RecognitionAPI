import asyncio
from config import PROJECT_ROOT, RECOGNITION_API_KEY
from deepvision import DeepVision
from deepvision.service import ProductRecognitionService, ProductCountService, OnShelfAvailabilityService, ProductDetectionService
from deepvision.collections import Products, ProductCollection

deep_vision: DeepVision = DeepVision(vectordb_dir=PROJECT_ROOT)
product_recognition: ProductRecognitionService = deep_vision.init_product_recognition_service(RECOGNITION_API_KEY)
count_recognition: ProductCountService = deep_vision.init_product_count_service(RECOGNITION_API_KEY)

#Lấy danh sách sản phẩm theo tên danh mục
async def get_products_by_collection(collection_name: str):
    products: Products = product_recognition.get_products()
    return products.list(collection_name=collection_name)

#SDK gọi requests.get/requests.post không có timeout -> 1 ảnh mạng chậm/server treo có thể
#treo vô thời hạn. Giới hạn thời gian xử lý mỗi ảnh để không kéo treo cả request.
IMAGE_PROCESSING_TIMEOUT_SECONDS = 90

#Với id ảnh mà không có thì sẽ thêm mới, nếu có thì sẽ tự động cập nhật
#Xử lý song song từng ảnh một để biết chính xác ảnh nào thành công/thất bại
async def add_or_update_product(collection_name: str, product_id: str, product_name: str, image_paths: list[str], image_ids: list[str]):
    product_collection: ProductCollection = product_recognition.get_product_collection()

    async def add_one_image(image_id: str, image_path: str) -> dict:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(product_collection.add, collection_name, image_id, image_path, product_id, product_name),
                timeout=IMAGE_PROCESSING_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            return {
                "id": None, "url": image_path, "status": "failed",
                "error": "Timeout sau %ds khi gọi DeepVision (tải ảnh hoặc embedding không phản hồi)" % IMAGE_PROCESSING_TIMEOUT_SECONDS
            }
        status = result.get("status", "failed")
        error = None if status == "completed" else str(result.get("error") or result.get("result"))
        #id chỉ được trả về khi thêm/cập nhật thành công, vì SDK yêu cầu app tự sinh id trước
        #khi gọi (không phải id do SDK cấp sau khi lưu xong) nên id không có ý nghĩa khi thất bại
        return {"id": image_id if status == "completed" else None, "url": image_path, "status": status, "error": error}

    return await asyncio.gather(*[
        add_one_image(image_id, image_path)
        for image_id, image_path in zip(image_ids, image_paths)
    ])

#Xóa một ảnh sản phẩm theo image_id
async def delete_image_by_id(collection_name: str, image_id: str):
    product_collection: ProductCollection = product_recognition.get_product_collection()
    return product_collection.delete(collection_name, image_id)

#Lấy danh sách ảnh (image_id) đã lưu cho một sản phẩm trong danh mục
#Lưu ý: mỗi ảnh khi add có thể sinh nhiều vector embedding tăng cường (data augmentation)
#dùng chung image_id trong vector DB, nên list_examples() trả nhiều dòng/1 ảnh -> phải gộp theo image_id
async def get_images_by_product(collection_name: str, product_id: str):
    product_collection: ProductCollection = product_recognition.get_product_collection()
    result = product_collection.list(collection_name)
    if result.get("status") != "completed":
        return result
    images = {}
    for item in result.get("result", []):
        if item.get("product_id") == product_id and item.get("image_id") not in images:
            images[item.get("image_id")] = item
    return {"status": "completed", "result": list(images.values())}

#Cập nhật thông tin tên của sản phẩm
async def update_name_product(collection_name: str, product_id: str, new_name: str):
    products: Products = product_recognition.get_products()
    products.update_by_id(collection_name, product_id, new_name)

#Xóa một sản phẩm trong danh mục
async def delete_product(collection_name: str, product_id: str):
    products: Products = product_recognition.get_products()
    products.delete_product_by_id(collection_name, product_id)

#Xóa tất cả ảnh của một sản phẩm
async def delete_all_images_product(collection_name: str, product_id: str):
    product_collection: ProductCollection = product_recognition.get_product_collection()
    product_collection.delete_all_by_id(collection_name, product_id)

#Xóa danh mục dựa theo tên danh mục
async def delete_collection(collection_name: str):
    products: Products = product_recognition.get_products()
    products.delete_collection(collection_name)

#Đếm số lượng sản phẩm có trong ảnh
async def count_product(collection_name: str, image_paths: list[str]):
    count_product = count_recognition.count(collection_name=collection_name, image_path=image_paths)
    return count_product

#Kiểm tra sản phẩm tồn tại trên gian hàng
async def shelf_availability_product(collection_name: str, image_paths: list[str], product_checks: dict, sku_threshold: float):
    deep_vision_audit: DeepVision = DeepVision(vectordb_dir=PROJECT_ROOT, sku_threshold=sku_threshold)
    on_shelf_availibility: OnShelfAvailabilityService = deep_vision_audit.init_on_shelf_availability_service(RECOGNITION_API_KEY)
    availibility_res = on_shelf_availibility.run(collection_name, image_paths, product_checks)
    return availibility_res

#Lấy vùng bao sản phẩm từ ảnh
async def detect_product_from_image(image_path: str):
    deep_vision_detection: DeepVision = DeepVision(vectordb_dir=PROJECT_ROOT, options={})
    detection: ProductDetectionService = deep_vision_detection.init_product_detection_service(RECOGNITION_API_KEY)
    detection_product = detection.detect(image_path)
    return detection_product