# Nhật ký yêu cầu — RecognitionAPI

Ghi lại mọi yêu cầu (bug fix / tính năng mới / quyết định) để AI ở các phiên sau nắm ngữ cảnh mà không cần quét lại toàn bộ codebase. Mỗi mục nên có: ngày, yêu cầu gốc, kế hoạch đã duyệt, kết quả, trạng thái test/xác nhận.

Xem quy trình bắt buộc tại [CLAUDE.md](../CLAUDE.md#6-quy-trình-làm-việc-bắt-buộc-trong-dự-án-này).

---

## 2026-08-28 — Quét codebase lần đầu

- **Yêu cầu:** Quét lại toàn bộ ứng dụng, sinh file context cho AI, thiết lập quy trình làm việc bắt buộc (không tự suy luận, phải có kế hoạch + test cho mọi thay đổi, ghi log mọi yêu cầu).
- **Việc đã làm:** Đọc toàn bộ mã nguồn (`main.py`, `config.py`, `controllers/`, `models/`, `routers/`, `utils/`) và SDK `deepvision` đã cài trong `venv/` để đối chiếu. Tạo `CLAUDE.md` (tổng quan kiến trúc, bảng endpoint, service SDK đã dùng/chưa dùng, rủi ro phát hiện được) và file log này.
- **Thay đổi code:** Không có — đây là công việc tài liệu hoá thuần tuý.
- **Vấn đề phát hiện, đang chờ bạn xác nhận** (chi tiết ở CLAUDE.md mục 5):
  1. `RECOGNITION_API_KEY` hardcode plaintext trong `config.py`, đã commit vào git.
  2. `.gitignore` ghi `.venv/` nhưng venv thực tế tên `venv/` → không được ignore.
  3. Khối code chết (comment) vẽ bounding box trong `routers/products.py` (dòng ~146-167) kéo theo import thừa.
  4. Repo chưa có test nào.
  5. App không có cơ chế override domain/port của DeepVision SDK.
- **Trạng thái:** Chờ bạn xác nhận có xử lý các mục trên không, và mục nào ưu tiên trước.

---

## 2026-08-28 — Bổ sung 3 API quản lý ảnh sản phẩm

- **Yêu cầu gốc:** (1) Dịch vụ cập nhật ảnh sản phẩm phải trả về id kèm link ảnh; (2) xoá một ảnh theo id; (3) lấy danh sách ảnh theo một sản phẩm.
- **Quá trình xác nhận (không tự suy luận):**
  - Đọc SDK (`ProductCollection`, `Products`, `ProductClient`) để xác định khả năng thực tế trước khi lên kế hoạch.
  - Hỏi & chốt với bạn: (a) route xoá ảnh dùng dạng phẳng `DELETE /products/images/{image_id}` (không lồng trong product_id vì SDK không kiểm tra product_id khi xoá); (b) API lấy ảnh theo sản phẩm chỉ trả `image_id` (SDK không lưu URL ảnh gốc); (c) API cập nhật ảnh phải xử lý **từng ảnh riêng lẻ, song song**, trả `{id, url, status, error}` cho từng ảnh thay vì gộp cả lô; (d) áp dụng cơ chế song song này cho **cả** `POST /products` lẫn `PUT /products/{id}/images` vì 2 endpoint dùng chung 1 hàm controller.
- **Thay đổi code:**
  - `controllers/product_ai.py`: viết lại `add_or_update_product()` — gọi `ProductCollection.add()` cho từng ảnh qua `asyncio.gather(asyncio.to_thread(...))` thay vì `Products.add()` theo lô; thêm `delete_image_by_id()`, `get_images_by_product()` (lọc theo product_id từ `ProductCollection.list()` vì SDK không có API lọc sẵn).
  - `models/product.py`: thêm `ImageResultInfo` (id/url/status/error), `ProductUpdateImageOut`, `ProductImageInfo`, `ProductImagesByProductOut`; đổi `ProductCreateOut.image_paths` sang `list[ImageResultInfo]`.
  - `routers/products.py`: `POST /products` và `PUT /products/{id}/images` giờ trả status/error từng ảnh; thêm `DELETE /products/images/{image_id}`; thêm `GET /products/{id}/images`.
  - `requirements.txt`: thêm `pytest==8.3.3` (dev dependency, phục vụ bộ test mới).
  - `tests/test_product_images.py` + `tests/conftest.py`: 9 test case, mock SDK (không gọi mạng thật) — kết quả: **9/9 PASSED** (`python -m pytest tests/test_product_images.py -v`).
  - `CLAUDE.md`: cập nhật bảng endpoint + mục "Ghi chú kỹ thuật quan trọng" (đặc biệt: SDK `remove_example()` luôn trả `status: "completed"` kể cả khi lỗi — phải check key `"error"`).
- **Phát hiện đáng chú ý:** `ProductClient.remove_example()` trong SDK có bug/quirk — không bao giờ trả `status: "failed"`, kể cả khi collection không tồn tại hoặc exception; phải dựa vào key `"error"` để phát hiện lỗi. Đã xử lý trong route xoá ảnh, KHÔNG sửa trong SDK (SDK là dependency ngoài, không thuộc phạm vi sửa của repo này).
- **Cách bạn tự kiểm thử:**
  1. Test tự động (không cần mạng/API key thật): `source venv/bin/activate && python -m pytest tests/test_product_images.py -v` → kỳ vọng 9 passed.
  2. Test thủ công với DeepVision thật: chạy `fastapi dev main.py`, mở `http://127.0.0.1:8000/docs`, thử lần lượt:
     - `POST /products` với `image_paths` là URL ảnh thật → kiểm tra response trả đúng `image_paths: [{id, url, status, error}]`.
     - `PUT /products/{product_id}/images` — thử 1 ảnh có `id` (lấy id vừa tạo ở trên) và 1 ảnh không có `id` → kiểm tra ảnh có id giữ nguyên id, ảnh không có id được sinh id mới, cả 2 đều `status: "completed"`.
     - `GET /products/{product_id}/images?collection_name=...` → kiểm tra trả đúng danh sách `image_id` vừa thêm ở trên, đúng `total`.
     - `DELETE /products/images/{image_id}?collection_name=...` → xoá 1 ảnh vừa thêm, gọi lại `GET .../images` để xác nhận ảnh đã biến mất khỏi danh sách.
     - Thử `collection_name` không tồn tại cho `GET .../images` → kỳ vọng `404`.
- **Trạng thái:** Đã code + test tự động pass. **Chờ bạn chạy thử thủ công với dữ liệu thật và xác nhận không lỗi trước khi coi là hoàn tất.**

---

## 2026-08-28 — Fix `.gitignore` không khớp thư mục `venv/`

- **Yêu cầu:** Bổ sung `.gitignore` để không track file trong thư mục venv.
- **Thay đổi:** Thêm dòng `venv/` vào `.gitignore` (giữ nguyên `.venv/` cũ, không xoá). Đây chính là vấn đề #2 phát hiện lúc quét lần đầu (2026-08-28) — `.gitignore` trước đó chỉ khai báo `.venv/` trong khi thư mục thật tên `venv/`.
- **Kiểm tra:** `git status --short` sau khi sửa không còn dòng `?? venv/`.
- **Trạng thái:** Hoàn tất.

---

## 2026-08-28 — Fix bug: `GET /products/{id}/images` trả nhân bản ảnh (60 ảnh → 236 dòng)

- **Bug do bạn báo cáo:** Tạo collection `kiem_thu_1`, add 60 ảnh cho 1 sản phẩm, gọi `GET /products/{product_id}/images` thì `total` ra 236, mỗi `image_id` lặp lại nhiều lần trong response.
- **Nguyên nhân (đã trace vào SDK):** `ProductClient.add_example()` — với mỗi ảnh, dịch vụ embedding trả về nhiều vector "tăng cường" (`response["results"]["upload_augment_products"]`, thường 4 vector/ảnh). SDK insert **mỗi vector thành 1 dòng riêng** trong ChromaDB, cùng metadata `image_id`. `list_examples()` (dùng bởi `ProductCollection.list()`) đọc thẳng toàn bộ dòng, không gộp theo `image_id` → 59 ảnh add thành công × 4 vector = 236 dòng (khớp chính xác dữ liệu bạn gửi).
- **Kế hoạch đã thống nhất & thực hiện:** Sửa `product_ai.get_images_by_product()` — sau khi lọc theo `product_id`, gộp (dedupe) theo `image_id`, chỉ giữ 1 bản ghi/ảnh.
- **Thay đổi code:** `controllers/product_ai.py` (hàm `get_images_by_product`); `CLAUDE.md` (thêm cảnh báo kỹ thuật: 1 ảnh = nhiều dòng vector DB, mọi chỗ đọc `ProductCollection.list()` phải dedupe theo image_id).
- **Test:** Thêm `test_get_images_by_product_dedupes_augmented_vectors_of_same_image` trong `tests/test_product_images.py`, tái hiện đúng tình huống 1 image_id có 4 dòng trùng, xác nhận response chỉ còn 1 dòng/ảnh. Chạy `python -m pytest tests/test_product_images.py -v` → **10/10 PASSED**.
- **Cách bạn tự kiểm thử lại với dữ liệu thật:** gọi lại đúng URL bạn đã báo lỗi — `GET /products/{product_id}/images?collection_name=kiem_thu_1` — kỳ vọng `total` bằng đúng số ảnh add thành công (≈59-60, không phải 236), mỗi `image_id` chỉ xuất hiện 1 lần trong danh sách.
- **Trạng thái:** Đã code + test tự động pass. Chờ bạn xác nhận lại trên server thật với `collection_name=kiem_thu_1`.

---

## 2026-08-28 — Fix bug: `POST /products` bị treo với payload 60 ảnh

- **Bug do bạn báo cáo:** Gọi `POST /products` với 60 URL ảnh (`collection_name: kiem_thu_final_one`) thì request bị treo, không có phản hồi.
- **Nguyên nhân (đã trace vào SDK):** SDK gọi `requests.get()` (tải ảnh từ URL) và `requests.post()` (gửi ảnh lên dịch vụ embedding) đều **không set `timeout`** (`multipart_constructor.get_file()`, `ProductEmbeddingClient.post()`). Vì `add_or_update_product()` xử lý ảnh song song qua `asyncio.gather` (đã đổi ở yêu cầu trước), chỉ cần 1/60 ảnh gặp kết nối treo (server ảnh chậm/không phản hồi) là `asyncio.gather` đợi vô thời hạn, kéo treo toàn bộ request — dù các ảnh khác đã xử lý xong.
- **Kế hoạch đã thống nhất & thực hiện:** Bọc từng ảnh bằng `asyncio.wait_for(..., timeout=30s)` trong `add_or_update_product()`. Ảnh vượt timeout trả `status: "failed", error: "Timeout sau 30s..."`, không chặn các ảnh khác. Giá trị 30s do bạn chọn khi được hỏi (các lựa chọn khác: 60s, 120s).
- **Giới hạn đã báo cho bạn:** `wait_for` không kill được thread nền đang chạy `requests` thật sự (Python không hỗ trợ), nên đây là giảm nhẹ (request luôn trả lời đúng hạn) chứ chưa phải sửa tận gốc. Sửa tận gốc phải thêm `timeout=` vào chính SDK (`deepvision_python_sdk`, dependency cài qua git) — ngoài phạm vi sửa của repo này.
- **Thay đổi code:** `controllers/product_ai.py` (thêm `IMAGE_PROCESSING_TIMEOUT_SECONDS = 30`, bọc `asyncio.wait_for` quanh từng ảnh); `CLAUDE.md` (thêm cảnh báo kỹ thuật SDK không có timeout).
- **Test:** Thêm `test_add_or_update_product_image_timeout_does_not_hang_whole_request` (mô phỏng 1 ảnh "treo" bằng `time.sleep`, hạ timeout xuống 0.05s qua monkeypatch để test chạy nhanh) — xác nhận request vẫn trả về đúng hạn, ảnh treo báo `failed`, ảnh còn lại vẫn `completed`. Chạy `python -m pytest tests/test_product_images.py -v` → **11/11 PASSED**.
- **Cách bạn tự kiểm thử lại với dữ liệu thật:** gọi lại đúng payload 60 ảnh đã báo lỗi (`collection_name: kiem_thu_final_one`) — kỳ vọng request trả về trong khoảng 30-60s (không treo vô thời hạn), response liệt kê đủ 60 ảnh kèm `status`/`error` riêng từng ảnh (ảnh nào chậm/lỗi sẽ thấy rõ `status: "failed"` thay vì làm im lặng cả request).
- **Trạng thái:** Đã code + test tự động pass. Chờ bạn chạy lại với payload thật và xác nhận không còn treo.

---

## 2026-08-28 — Tăng timeout mỗi ảnh: 30s → 90s

- **Yêu cầu:** Sau khi thử với timeout 30s, bạn báo có ảnh mở được bình thường trên trình duyệt nhưng dịch vụ vẫn báo timeout — cần tăng thời gian chờ.
- **Thay đổi:** `controllers/product_ai.py` — `IMAGE_PROCESSING_TIMEOUT_SECONDS` từ `30` lên `90` (bạn chọn 90s, các lựa chọn khác đưa ra là 60s/120s).
- **Test:** Không cần sửa test (test dùng `monkeypatch` hạ timeout xuống 0.05s để chạy nhanh, không phụ thuộc giá trị thật 30/90). Chạy lại `python -m pytest tests/test_product_images.py -v` → **11/11 PASSED**.
- **Trạng thái:** Hoàn tất. Nếu vẫn còn ảnh bị timeout ở mức 90s, cần bạn xác nhận có tăng tiếp không, hoặc cân nhắc đây là dấu hiệu server ảnh/dịch vụ embedding thật sự chậm bất thường (không chỉ do thiếu timeout).

---

## 2026-08-28 — Fix: ảnh "failed" vẫn trả về id (mâu thuẫn logic)

- **Bug do bạn phát hiện:** Ảnh có `status: "failed"` nhưng vẫn có `id` trong response — trong khi id chỉ nên có khi thêm/cập nhật thành công.
- **Nguyên nhân:** SDK (`ProductCollection.add()`) yêu cầu app **tự sinh `image_id` trước** rồi mới gọi thêm (không phải SDK cấp id sau khi lưu xong), nên code cũ echo lại đúng id đã dùng để gọi bất kể thành công hay thất bại.
- **Đã thống nhất & thực hiện:** `id` chỉ trả về giá trị thật khi `status == "completed"`; khi `"failed"` thì `id: null` (ảnh vẫn xuất hiện trong danh sách kèm `url`, `status`, `error` để biết ảnh nào lỗi, lỗi gì).
- **Thay đổi code:** `models/product.py` (`ImageResultInfo.id` đổi sang `Optional[str] = None`); `controllers/product_ai.py` (`add_one_image` trả `id: None` khi status khác `"completed"`, cả nhánh timeout lẫn nhánh SDK failed); `CLAUDE.md` (ghi chú lại quy ước này).
- **Test:** Cập nhật `tests/test_product_images.py` — assert `id is None` cho ảnh failed (cả case SDK báo failed và case timeout). Chạy `python -m pytest tests/test_product_images.py -v` → **11/11 PASSED**.
- **Cách bạn tự kiểm thử lại:** Gọi `POST /products` hoặc `PUT /products/{id}/images` với ít nhất 1 ảnh chắc chắn lỗi (vd URL ảnh không có sản phẩm nào) → kiểm tra ảnh đó trong response có `"id": null`, còn ảnh thành công vẫn có `id` bình thường.
- **Trạng thái:** Đã code + test tự động pass. Chờ bạn xác nhận lại trên server thật.
