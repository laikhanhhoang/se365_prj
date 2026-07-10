# Hướng dẫn chạy – data_pipelines

> Tất cả lệnh đều chạy từ **thư mục gốc dự án** (PROJECT_DIR), không phải từ bên trong `data_pipelines/`.

---

## 1. Cào link từ Vietstock — `crawl/vietstock_crawl_links.py`

**Chạy thử (debug, hiện trình duyệt, 1 ngày):**
```bash
python data_pipelines/crawl/vietstock_crawl_links_selenium.py --debug --head
```
Output mẫu đúng: xem file `data_pipelines/crawl/vietstock_links_20260601_20260601_CHUAN.txt`

**Chạy thật (headless, nhiều ngày):**
```bash
# Windows (PowerShell)
python data_pipelines/crawl/vietstock_crawl_links_selenium.py `
    --start 01-06-2026 `
    --end   05-06-2026 `
    --output data_pipelines/crawl/vietstock_links_<start>_<end>.txt

# Linux / macOS
python3 data_pipelines/crawl/vietstock_crawl_links_selenium.py \
    --start 01-06-2026 \
    --end   05-06-2026 \
    --output data_pipelines/crawl/vietstock_links_<start>_<end>.txt
```

**Tham số:**

| Tham số | Mặc định | Mô tả |
| :--- | :--- | :--- |
| `--start` | `01-06-2026` | Ngày bắt đầu (DD-MM-YYYY) |
| `--end` | _(giống start)_ | Ngày kết thúc (DD-MM-YYYY) |
| `--output` | `data_pipelines/vietstock_links.txt` | File output (đường dẫn tương đối từ PROJECT_DIR) |
| `--debug` | tắt | In log chi tiết |
| `--head` | tắt | Hiện trình duyệt (bỏ cờ này để chạy headless) |

---

## 2. Cào nội dung bài viết từ links — `crawl/vietstock_crawl_data_from_links.py`

**Chạy thử (debug, hiện trình duyệt, dùng file mẫu):**
```bash
python data_pipelines/crawl/vietstock_crawl_data_from_links_selenium.py --debug --head
```
Output mẫu đúng: xem file `data_pipelines/crawl/vietstock_crawled_data_20260601_20260601_CHUAN.jsonl`

**Chạy thật (headless, dùng file link đã cào ở bước 1):**
```bash
# Windows (PowerShell)
python data_pipelines/crawl/vietstock_crawl_data_from_links_selenium.py `
    --links_file data_pipelines/crawl/vietstock_links_<start>_<end>.txt

# Linux / macOS
python3 data_pipelines/crawl/vietstock_crawl_data_from_links_selenium.py \
    --links_file data_pipelines/crawl/vietstock_links_<start>_<end>.txt
```

**Tham số:**

| Tham số | Mặc định | Mô tả |
| :--- | :--- | :--- |
| `--links_file` | `data_pipelines/crawl/vietstock_links_20260601_20260601_CHUAN.txt` | File chứa danh sách link (đường dẫn tương đối từ PROJECT_DIR) |
| `--debug` | tắt | In log chi tiết |
| `--head` | tắt | Hiện trình duyệt (bỏ cờ này để chạy headless) |

---

## 3. Chuẩn hoá dataset — `labelling/step01_preprocess.py`

Chuẩn hoá record thô về đúng field trong `dataset.schema` của `labelling/data_schema.json`.
Nếu `strict_required: "no"`, tự sinh `id` (chỉ khi record chưa có) và ghép toàn bộ field còn lại thành `content`.

```bash
python data_pipelines/labelling/step01_preprocess.py
```

Sửa `preprocess_config["in_out"]` trong file để đổi cặp file input/output cần xử lý.

## 4. Lọc theo keyword — `labelling/step02_filter.py`

Lọc bài viết theo `events[].keywords` trong `data_schema.json` (khớp trên `title`/`head`/`body`).

```bash
python data_pipelines/labelling/step02_filter.py
```

Sửa `filter_config["in_out"]`/`"combine"` trong file để đổi phạm vi lọc.

## 5. Gán nhãn bằng OpenAI — `labelling/step03_auto_label_openai.py`

Gọi model qua prompt trong `labelling/prompts/`, ghi thẳng phản hồi thô (`label_raw`) — **có resume**, không xử lý lại sample đã có id trong output.

```bash
python data_pipelines/labelling/step03_auto_label_openai.py
```

Cần file `data_pipelines/.env` chứa `OPENAI_KEY`.

## 6. Hậu xử lý — `labelling/step04_postprocess.py`

Parse `label_raw` thành list event có cấu trúc, bỏ event có `event_type` không có trong `events[].name` của `data_schema.json`, cảnh báo field thiếu/thừa theo `events[].fields`.

```bash
python data_pipelines/labelling/step04_postprocess.py
```

---

## Quy trình đầy đủ

```
Bước 1: Cào link         →  data_pipelines/crawl/vietstock_crawl_links.py
Bước 2: Cào data         →  data_pipelines/crawl/vietstock_crawl_data_from_links.py
Bước 3: Chuẩn hoá dataset →  data_pipelines/labelling/step01_preprocess.py
Bước 4: Lọc keyword       →  data_pipelines/labelling/step02_filter.py
Bước 5: Gán nhãn          →  data_pipelines/labelling/step03_auto_label_openai.py
Bước 6: Hậu xử lý         →  data_pipelines/labelling/step04_postprocess.py
```

Taxonomy sự kiện (tên, field, keyword) được định nghĩa **duy nhất** trong `data_pipelines/labelling/data_schema.json` — step02–04 đều đọc trực tiếp từ file này, không hard-code lại.

Mỗi step có thể khai báo thêm `"log"` (đường dẫn `.txt`) trong config ở `if __name__ == "__main__":` — khi có, step sẽ ghi log tóm tắt kèm snapshot toàn bộ `data_schema.json` tại thời điểm chạy vào file đó (mặc định ghi vào `labelling/logs/`).

---

## Lưu ý

- File output được git-ignore theo pattern `**/*.txt` và `**/*.jsonl`.  
  File nào kết thúc bằng `_CHUAN.*` là file mẫu/chuẩn và **được giữ lại** trong repo.
- Đặt tên output theo convention: `vietstock_links_DDMMYYYY_DDMMYYYY.txt` để dễ theo dõi.
