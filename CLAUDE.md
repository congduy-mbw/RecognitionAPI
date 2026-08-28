# RecognitionAPI — Context cho AI

> File này được sinh ra từ một lượt quét toàn bộ codebase (2026-08-28) để AI không phải quét lại từ đầu ở các phiên làm việc sau. Khi có thay đổi kiến trúc/endpoint/service, hãy cập nhật file này và ghi lại yêu cầu tương ứng trong [docs/requests-log.md](docs/requests-log.md).

## 1. Ứng dụng này là gì

RecognitionAPI là một lớp phủ (overlay/wrapper) bằng FastAPI đặt trên **DeepVision Python SDK** (`git+https://github.com/EOV-Solutions/deepvision_python_sdk`, gói cài đặt tên `deepvision-sdk`, import là `deepvision`). Mục đích nghiệp vụ: **chấm điểm / kiểm tra trưng bày sản phẩm tại gian hàng** (nhận diện sản phẩm, đếm số lượng, kiểm tra tồn tại đúng SKU trên kệ, khoanh vùng sản phẩm trong ảnh).

Ứng dụng không tự chứa mô hình AI — nó gọi qua SDK, SDK gọi tới dịch vụ DeepVision (`domain` mặc định trong SDK: `https://vision.ekgis.vn`) và lưu vector DB cục bộ (Chroma) tại `vectordb_dir` do app truyền vào.

## 2. Kiến trúc & vai trò từng file

```
main.py                    FastAPI app, include_router(collections, products). Không có uvicorn.run() — chạy bằng `fastapi dev main.py` / `fastapi run` (từ fastapi[standard]).
config.py                  PROJECT_ROOT (dùng làm vectordb_dir), RECOGNITION_API_KEY (hardcode, xem mục 5.1 ⚠).
controllers/product_ai.py  Lớp nghiệp vụ, khởi tạo DeepVision + các service SDK, expose các hàm async cho router gọi.
models/product.py          Pydantic schemas (request/response) cho router products.
routers/collections.py     Endpoint xoá danh mục.
routers/products.py        Endpoint CRUD sản phẩm + 3 dịch vụ AI (count, shelf availability, detection).
utils/handle_response.py   remove_base64(): đệ quy xoá field "base64_image" khỏi response trước khi trả về.
```

### controllers/product_ai.py — chi tiết

Khởi tạo ở module-level (singleton, dùng chung mọi request):
- `deep_vision = DeepVision(vectordb_dir=PROJECT_ROOT)`
- `product_recognition = deep_vision.init_product_recognition_service(RECOGNITION_API_KEY)`
- `count_recognition = deep_vision.init_product_count_service(RECOGNITION_API_KEY)`

Khởi tạo **mới mỗi lần gọi** (per-request), vì cần custom `sku_threshold`/`options`:
- `shelf_availability_product()` → tạo `DeepVision(sku_threshold=...)` rồi `init_on_shelf_availability_service`
- `detect_product_from_image()` → tạo `DeepVision(options={})` rồi `init_product_detection_service`

Các hàm nghiệp vụ: `get_products_by_collection`, `add_or_update_product`, `update_name_product`, `delete_product`, `delete_all_images_product`, `delete_collection`, `count_product`, `shelf_availability_product`, `detect_product_from_image`.

## 3. Bảng endpoint hiện có

| Method | Path | Mô tả | Controller function |
|---|---|---|---|
| DELETE | `/collections/{collection_id}` | Xoá danh mục sản phẩm | `product_ai.delete_collection` |
| GET | `/products?collection_name=` | Lấy danh sách sản phẩm theo danh mục | `product_ai.get_products_by_collection` |
| POST | `/products` | Thêm sản phẩm mới (tự sinh product_id, image_id; xử lý từng ảnh song song, trả status/error riêng từng ảnh) | `product_ai.add_or_update_product` |
| PUT | `/products/{product_id}/name` | Đổi tên sản phẩm | `product_ai.update_name_product` |
| PUT | `/products/{product_id}/images` | Cập nhật/thêm ảnh sản phẩm (id có sẵn = ghi đè/cập nhật, không có id = thêm mới); xử lý song song từng ảnh, trả `{id, url, status, error}` cho từng ảnh | `product_ai.add_or_update_product` |
| DELETE | `/products/{product_id}/images?collection_name=` | Xoá toàn bộ ảnh của 1 sản phẩm | `product_ai.delete_all_images_product` |
| DELETE | `/products/images/{image_id}?collection_name=` | Xoá 1 ảnh theo `image_id` (xoá trong toàn collection, không kiểm tra thuộc đúng product_id) | `product_ai.delete_image_by_id` |
| GET | `/products/{product_id}/images?collection_name=` | Lấy danh sách `image_id` đã lưu của 1 sản phẩm (SDK không lưu URL ảnh gốc nên không trả được url) | `product_ai.get_images_by_product` |
| DELETE | `/products/{product_id}?collection_name=` | Xoá sản phẩm | `product_ai.delete_product` |
| POST | `/products/count_recognition` | Đếm số lượng sản phẩm trong ảnh | `product_ai.count_product` |
| POST | `/products/shelf_availibility` | Kiểm tra tồn tại SKU theo điều kiện | `product_ai.shelf_availability_product` |
| POST | `/products/detection` | Trả vùng bao (bounding box) sản phẩm trong ảnh | `product_ai.detect_product_from_image` |

### Ghi chú kỹ thuật quan trọng (rút ra khi bổ sung 3 API ảnh, 2026-08-28)

- **`add_or_update_product`** (dùng chung cho POST /products và PUT .../images) gọi `ProductCollection.add()` (không phải `Products.add()` batch cũ) **cho từng ảnh riêng lẻ, song song** qua `asyncio.gather` + `asyncio.to_thread` (SDK gọi HTTP đồng bộ nên cần `to_thread` để không block event loop). Mỗi ảnh trả status/error độc lập — không phải all-or-nothing. `id` trong response **chỉ có giá trị khi `status == "completed"`, ngược lại là `null`** — vì SDK yêu cầu app tự sinh `image_id` TRƯỚC khi gọi thêm (không phải SDK cấp id sau khi lưu thành công), nên nếu trả id cả khi thất bại sẽ gây hiểu nhầm là đã lưu được (đã sửa theo yêu cầu 2026-08-28).
- **SDK có "quirk"**: `ProductClient.remove_example()` (dùng cho xoá 1 ảnh) luôn trả `status: "completed"` **kể cả khi lỗi** (collection không tồn tại, hoặc exception) — chỉ phân biệt được qua sự xuất hiện của key `"error"` trong response. Route `DELETE /products/images/{image_id}` xử lý bằng cách check `"error" in result`, KHÔNG dựa vào `status`. Nếu sau này bọc thêm hàm nào khác của SDK, phải tự kiểm tra lại cách hàm đó báo lỗi, không giả định `status` luôn đáng tin.
- **`ProductCollection.list(collection_name)`** trả về TOÀN BỘ ảnh trong collection (không filter theo sản phẩm) — endpoint `GET /products/{id}/images` phải tự lọc theo `product_id` ở tầng app (`product_ai.get_images_by_product`).
- **⚠️ Mỗi ảnh có thể tương ứng NHIỀU dòng trong vector DB** (SDK sinh nhiều vector embedding tăng cường/data augmentation cho 1 ảnh, insert từng vector thành 1 dòng ChromaDB riêng nhưng cùng `image_id` — xem `ProductClient.add_example()`, vòng lặp `for eb in response["results"]["upload_augment_products"]`). Mọi chỗ đọc dữ liệu qua `list_examples()`/`ProductCollection.list()` **phải gộp (dedupe) theo `image_id`** trước khi trả về người dùng, nếu không sẽ đếm/hiển thị nhân bản (bug thực tế gặp 2026-08-28: 60 ảnh add vào báo lại 236 dòng). `product_ai.get_images_by_product()` đã xử lý việc này; nếu sau này viết thêm chỗ khác đọc `ProductCollection.list()`, phải nhớ áp dụng lại.
- **⚠️ SDK gọi `requests.get`/`requests.post` KHÔNG có `timeout`** ở cả bước tải ảnh từ URL (`multipart_constructor.get_file()`) và bước gọi dịch vụ embedding (`ProductEmbeddingClient.post()`, `client/product/product_embedding.py`). Nếu ảnh/server phản hồi chậm hoặc treo, request có thể treo vô thời hạn. Vì `add_or_update_product()` gọi nhiều ảnh song song qua `asyncio.gather`, chỉ cần 1 ảnh bị treo là treo cả request (bug thực tế gặp 2026-08-28 với payload 60 ảnh). Đã vá ở tầng app bằng `asyncio.wait_for(..., timeout=IMAGE_PROCESSING_TIMEOUT_SECONDS)` (hiện = 90s, tăng từ 30s ban đầu vì có ảnh thật load được trên trình duyệt nhưng vẫn bị báo timeout ở mức 30s) quanh mỗi ảnh trong `product_ai.py` — ảnh vượt timeout trả `status: "failed"` thay vì treo cả response. Lưu ý: `wait_for` chỉ hủy chờ ở phía coroutine, KHÔNG kill được thread nền đang chạy `requests` (Python không có API kill thread), nên thread bị treo vẫn tồn tại ngầm cho tới khi OS tự ngắt kết nối — đây là giới hạn của SDK/`requests`, không sửa triệt để được từ phía app này (SDK là dependency ngoài, cài qua git). Nếu lặp lại nhiều lần có thể làm cạn thread pool mặc định của `asyncio.to_thread`.

## 4. DeepVision SDK — phần đã dùng vs. chưa dùng

SDK (`deepvision-sdk==0.1.0`, cài trong `venv/`) cung cấp nhiều service hơn những gì app này đang bọc. Hữu ích khi có yêu cầu **bổ sung dịch vụ mới**.

**Đã dùng trong app này:**
- `service.ProductRecognitionService`, `service.ProductCountService`, `service.OnShelfAvailabilityService`, `service.ProductDetectionService`
- `collections.Products`, `collections.ProductCollection`

**Có sẵn trong SDK nhưng app CHƯA wrap (chưa có endpoint):**
- Face: `FaceDetectionService`, `FaceRecognitionService`, `FaceVerificationService`, `FaceVerifyService`, `FaceCountService`, `collections.FaceCollection`, `collections.Subjects`
- Product: `ProductVerificationService`, `ProductVerifyService`
- Audit (nhóm liên quan trực tiếp tới "chấm điểm trưng bày", khả năng cao sẽ được yêu cầu sau này): `AdjacenciesyService`, `SequenceOfProductService`, `ShareOfShelfService`, `SeperateCategoriesService`, `RightShelfService`, `RightQuantityService`, `BigPicturePlanogramService`, `PlanogramExtractService`
- Khác: `WaterMeterService`, `PowerMeterService`, `PPEService`, `ImageTaggingService`, `OCRService`, `PlanogramService`

Tất cả khởi tạo qua `DeepVision.init_<tên>_service(api_key)`, cùng pattern với những service đã dùng — xem `venv/lib/python3.12/site-packages/deepvision/core/model.py`.

## 5. Ghi chú / rủi ro phát hiện khi quét (2026-08-28) — CHƯA sửa, cần xác nhận trước khi động vào

1. **`config.py:4`** — `RECOGNITION_API_KEY` hardcode dạng plaintext và đã commit vào git (không phải qua biến môi trường/secret manager). Rủi ro lộ secret trong lịch sử git.
2. ~~`.gitignore` không khớp tên thư mục venv thực tế~~ → Đã fix 2026-08-28: thêm `venv/` vào `.gitignore` (giữ nguyên `.venv/` cũ). `git status` không còn báo `venv/` nữa.
3. **`routers/products.py:146-167`** — khối code bị comment (vẽ bounding box bằng cv2, lưu file ảnh) nằm trong `count_recognition`, kéo theo các import `cv2, numpy, os, datetime, base64` hiện chỉ phục vụ đoạn code chết này.
4. ~~Repo hiện chưa có bộ test nào~~ → Đã có `tests/` (pytest, thêm 2026-08-28) cho các endpoint ảnh sản phẩm — xem mục 3 và [docs/requests-log.md](docs/requests-log.md). Các API còn lại (count_recognition, shelf_availibility, detection, collections...) vẫn chưa có test.
5. App không override `domain`/`port` của SDK — luôn dùng mặc định của SDK (`https://vision.ekgis.vn`, port rỗng). Nếu cần trỏ sang môi trường khác (staging/on-prem) thì hiện chưa có cơ chế cấu hình.

*(Không tự sửa các mục trên — chờ bạn xác nhận từng mục có cần xử lý hay không, theo đúng quy trình ở mục 6.)*

## 6. Quy trình làm việc bắt buộc trong dự án này

Theo yêu cầu của bạn (2026-08-28), mọi phiên làm việc sau trên repo này phải tuân thủ:

1. **Không tự suy luận/giả định.** Khi có điểm chưa rõ (yêu cầu mơ hồ, thiếu thông tin, nhiều cách hiểu), phải hỏi và chờ xác nhận trước khi code, không được tự quyết thay.
2. **Fix lỗi / bổ sung dịch vụ đều phải có kế hoạch triển khai trước**, trình bày cho bạn duyệt trước khi implement.
3. **Sau khi hoàn thành, phải có bộ test để bạn tự kiểm thử** và xác nhận dịch vụ không lỗi trước khi coi là xong việc.
4. **Mọi yêu cầu (bug fix / tính năng mới / quyết định) phải được ghi lại** vào [docs/requests-log.md](docs/requests-log.md) để AI ở phiên sau nắm được ngữ cảnh mà không cần quét lại toàn bộ.

Khi bắt đầu một yêu cầu mới, AI nên đọc `CLAUDE.md` (file này) + `docs/requests-log.md` trước, thay vì quét lại toàn bộ mã nguồn.
