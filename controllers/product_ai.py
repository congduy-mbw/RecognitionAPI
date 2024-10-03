from config import PROJECT_ROOT, RECOGNITION_API_KEY
from deepvision import DeepVision
from deepvision.service import ProductRecognitionService, ProductCountService
from deepvision.collections import Products, ProductCollection

deep_vision: DeepVision = DeepVision(vectordb_dir=PROJECT_ROOT)
product_recognition: ProductRecognitionService = deep_vision.init_product_recognition_service(RECOGNITION_API_KEY)
count_recognition: ProductCountService = deep_vision.init_product_count_service(RECOGNITION_API_KEY)


#Với id ảnh mà không có thì sẽ thêm mới, nếu có thì sẽ tự động cập nhật
async def add_or_update_product(collection_name: str, product_id: str, product_name: str, image_paths: list[str], image_ids: list[str]):
    products: Products = product_recognition.get_products()
    product_res = products.add(collection_name, product_id, product_name, image_ids, image_paths)
    return product_res

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
    product_collection.delete_all_examples_by_id(collection_name, product_id)

#Xóa danh mục dựa theo tên danh mục
async def delete_collection(collection_name: str):
    products: Products = product_recognition.get_products()
    products.delete_collection(collection_name)

#Đếm số lượng sản phẩm có trong ảnh
async def count_product(collection_name: str, image_paths: list[str]):
    count_product = count_recognition.count(collection_name=collection_name, image_path=image_paths)
    return count_product