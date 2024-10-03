from fastapi import APIRouter, HTTPException
from controllers import product_ai

router = APIRouter(
    prefix="/collections",
    tags=["Collections"]
)

@router.delete("/{collection_id}", summary="Xóa danh mục sản phẩm")
async def delete_collection(collection_id: str):
    await product_ai.delete_collection(collection_id)