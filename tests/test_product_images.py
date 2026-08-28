"""
Test cho 3 tính năng mới (2026-08-28): cập nhật ảnh trả về id+url+status song song,
xóa 1 ảnh theo id, lấy danh sách ảnh theo sản phẩm.

Các test này KHÔNG gọi ra DeepVision SDK/mạng thật (product_recognition được
monkeypatch bằng object giả) — chỉ kiểm tra logic của app: routing, validate input,
tổng hợp kết quả song song, và cách map status/error của SDK sang HTTP response.

Chạy: pytest tests/test_product_images.py -v
"""
import types

from fastapi.testclient import TestClient

import main
from controllers import product_ai

client = TestClient(main.app)


def fake_recognition_with_collection(collection):
    return types.SimpleNamespace(get_product_collection=lambda: collection)


# ---------- PUT /products/{id}/images : trả id/url/status theo từng ảnh ----------

def test_update_images_returns_status_per_image_and_preserves_given_id(monkeypatch):
    def fake_add(collection_name, image_id, image_path, product_id, product_name, options={}):
        if image_path.endswith("bad.png"):
            return {"status": "failed", "result": "No product found in the photo."}
        return {"status": "completed", "result": {
            "product_id": product_id, "product_name": product_name, "image_id": image_id
        }}

    fake_collection = types.SimpleNamespace(add=fake_add)
    monkeypatch.setattr(product_ai, "product_recognition", fake_recognition_with_collection(fake_collection))

    payload = {
        "collection_name": "danh_muc_1",
        "product_name": "Ca Trung",
        "image_paths": [
            {"id": "existing-id-1", "url": "https://example.com/good.png"},
            {"url": "https://example.com/bad.png"},
        ],
    }
    resp = client.put("/products/prod-1/images", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["product_id"] == "prod-1"
    assert len(body["image_paths"]) == 2

    good = next(i for i in body["image_paths"] if i["url"].endswith("good.png"))
    bad = next(i for i in body["image_paths"] if i["url"].endswith("bad.png"))

    # ảnh có id sẵn -> giữ nguyên id (case "cập nhật")
    assert good["id"] == "existing-id-1"
    assert good["status"] == "completed"
    assert good["error"] is None

    # ảnh không có id -> tự sinh id mới (case "thêm mới"), và báo đúng lỗi từ SDK
    assert bad["id"] and bad["id"] != "existing-id-1"
    assert bad["status"] == "failed"
    assert "No product found" in bad["error"]


def test_add_or_update_product_image_timeout_does_not_hang_whole_request(monkeypatch):
    # SDK gọi requests.get/post không có timeout -> 1 ảnh mạng chậm/server treo có thể
    # treo vô thời hạn (bug thực tế gặp 2026-08-28 với 60 ảnh, POST /products bị treo).
    # add_or_update_product phải tự giới hạn thời gian mỗi ảnh (IMAGE_PROCESSING_TIMEOUT_SECONDS)
    # để các ảnh còn lại vẫn trả về đúng hạn, ảnh bị treo báo status "failed".
    import time

    monkeypatch.setattr(product_ai, "IMAGE_PROCESSING_TIMEOUT_SECONDS", 0.05)

    def fake_add(collection_name, image_id, image_path, product_id, product_name, options={}):
        if image_path.endswith("stuck.png"):
            time.sleep(0.3)  # mô phỏng request HTTP treo do SDK không có timeout
        return {"status": "completed", "result": {
            "product_id": product_id, "product_name": product_name, "image_id": image_id
        }}

    fake_collection = types.SimpleNamespace(add=fake_add)
    monkeypatch.setattr(product_ai, "product_recognition", fake_recognition_with_collection(fake_collection))

    payload = {
        "collection_name": "danh_muc_1",
        "product_name": "Ca Trung",
        "image_paths": ["https://example.com/ok.png", "https://example.com/stuck.png"],
    }
    resp = client.post("/products", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    ok = next(i for i in body["image_paths"] if i["url"].endswith("ok.png"))
    stuck = next(i for i in body["image_paths"] if i["url"].endswith("stuck.png"))
    assert ok["status"] == "completed"
    assert stuck["status"] == "failed"
    assert "Timeout" in stuck["error"]


def test_update_images_requires_collection_name():
    resp = client.put("/products/prod-1/images", json={
        "collection_name": "",
        "product_name": "Ca Trung",
        "image_paths": [{"url": "https://example.com/a.png"}],
    })
    assert resp.status_code == 404


# ---------- POST /products : cũng dùng chung logic song song ở trên ----------

def test_create_product_returns_status_per_image(monkeypatch):
    def fake_add(collection_name, image_id, image_path, product_id, product_name, options={}):
        return {"status": "completed", "result": {
            "product_id": product_id, "product_name": product_name, "image_id": image_id
        }}

    fake_collection = types.SimpleNamespace(add=fake_add)
    monkeypatch.setattr(product_ai, "product_recognition", fake_recognition_with_collection(fake_collection))

    payload = {
        "collection_name": "danh_muc_1",
        "product_name": "Ca Trung",
        "image_paths": ["https://example.com/a.png", "https://example.com/b.png"],
    }
    resp = client.post("/products", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["image_paths"]) == 2
    assert all(i["status"] == "completed" for i in body["image_paths"])
    # mỗi ảnh có 1 id khác nhau được tự sinh
    ids = {i["id"] for i in body["image_paths"]}
    assert len(ids) == 2


# ---------- DELETE /products/images/{image_id} ----------

def test_delete_image_by_id_success(monkeypatch):
    fake_collection = types.SimpleNamespace(
        delete=lambda collection_name, image_id: {"status": "completed", "result": {"image_id": image_id}}
    )
    monkeypatch.setattr(product_ai, "product_recognition", fake_recognition_with_collection(fake_collection))

    resp = client.delete("/products/images/img-1", params={"collection_name": "danh_muc_1"})
    assert resp.status_code == 200
    assert resp.json()["result"]["image_id"] == "img-1"


def test_delete_image_by_id_reports_error_even_when_sdk_status_says_completed(monkeypatch):
    # Lưu ý: SDK (ProductClient.remove_example) có "quirk" là luôn trả status="completed"
    # kể cả khi collection không tồn tại hoặc lỗi exception — chỉ phân biệt được qua key "error".
    fake_collection = types.SimpleNamespace(
        delete=lambda collection_name, image_id: {
            "status": "completed", "error": "Collection %s does not exists" % collection_name
        }
    )
    monkeypatch.setattr(product_ai, "product_recognition", fake_recognition_with_collection(fake_collection))

    resp = client.delete("/products/images/img-1", params={"collection_name": "missing_collection"})
    assert resp.status_code == 500


def test_delete_image_by_id_requires_collection_name():
    resp = client.delete("/products/images/img-1", params={"collection_name": ""})
    assert resp.status_code == 404


# ---------- GET /products/{id}/images ----------

def test_get_images_by_product_filters_by_product_id(monkeypatch):
    fake_collection = types.SimpleNamespace(list=lambda collection_name: {
        "status": "completed",
        "result": [
            {"image_id": "img-1", "product_id": "prod-1", "product_name": "Ca Trung"},
            {"image_id": "img-2", "product_id": "prod-2", "product_name": "Ca Kho"},
            {"image_id": "img-3", "product_id": "prod-1", "product_name": "Ca Trung"},
        ],
    })
    monkeypatch.setattr(product_ai, "product_recognition", fake_recognition_with_collection(fake_collection))

    resp = client.get("/products/prod-1/images", params={"collection_name": "danh_muc_1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["product_id"] == "prod-1"
    assert body["total"] == 2
    assert {i["image_id"] for i in body["images"]} == {"img-1", "img-3"}


def test_get_images_by_product_dedupes_augmented_vectors_of_same_image(monkeypatch):
    # SDK: mỗi ảnh khi add có thể sinh nhiều vector embedding tăng cường (data augmentation)
    # dùng chung image_id -> list_examples() trả nhiều dòng cho cùng 1 ảnh (bug thực tế gặp
    # phải 2026-08-28: 60 ảnh add vào nhưng list ra 236 dòng, mỗi image_id lặp lại 4 lần).
    duplicated_rows = []
    for n in range(1, 4):  # 3 ảnh khác nhau
        image_id = "img-%d" % n
        for _ in range(4):  # mỗi ảnh có 4 vector tăng cường, cùng image_id
            duplicated_rows.append({"image_id": image_id, "product_id": "prod-1", "product_name": "Milk_Ema"})
    # xen thêm ảnh của sản phẩm khác để chắc chắn không lẫn
    duplicated_rows.append({"image_id": "img-other", "product_id": "prod-2", "product_name": "Khac"})

    fake_collection = types.SimpleNamespace(list=lambda collection_name: {
        "status": "completed",
        "result": duplicated_rows,
    })
    monkeypatch.setattr(product_ai, "product_recognition", fake_recognition_with_collection(fake_collection))

    resp = client.get("/products/prod-1/images", params={"collection_name": "danh_muc_1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["product_id"] == "prod-1"
    assert body["total"] == 3
    assert {i["image_id"] for i in body["images"]} == {"img-1", "img-2", "img-3"}


def test_get_images_by_product_missing_collection(monkeypatch):
    fake_collection = types.SimpleNamespace(
        list=lambda collection_name: {"status": "failed", "error": "Collection does not exists"}
    )
    monkeypatch.setattr(product_ai, "product_recognition", fake_recognition_with_collection(fake_collection))

    resp = client.get("/products/prod-1/images", params={"collection_name": "missing"})
    assert resp.status_code == 404


def test_get_images_by_product_requires_collection_name():
    resp = client.get("/products/prod-1/images", params={"collection_name": ""})
    assert resp.status_code == 404
