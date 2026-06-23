# Hướng dẫn chạy – data_pipelines

> Tất cả lệnh đều chạy từ **thư mục gốc dự án** (PROJECT_DIR), không phải từ bên trong `data_pipelines/`.

---

## 1. Cào link từ Vietstock — `crawl/vietstock_crawl_links.py`

**Chạy thử (debug, hiện trình duyệt, 1 ngày):**
```bash
python data_pipelines/crawl/vietstock_crawl_links.py --debug --head
```
Output mẫu đúng: xem file `data_pipelines/crawl/vietstock_links_20260601_20260601_CHUAN.txt`

**Chạy thật (headless, nhiều ngày):**
```bash
# Windows (PowerShell)
python data_pipelines/crawl/vietstock_crawl_links.py `
    --start 01-06-2026 `
    --end   05-06-2026 `
    --output data_pipelines/crawl/vietstock_links_<start>_<end>.txt

# Linux / macOS
python3 data_pipelines/crawl/vietstock_crawl_links.py \
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
python data_pipelines/crawl/vietstock_crawl_data_from_links.py --debug --head
```
Output mẫu đúng: xem file `data_pipelines/crawl/vietstock_crawled_data_20260601_20260601_CHUAN.jsonl`

**Chạy thật (headless, dùng file link đã cào ở bước 1):**
```bash
# Windows (PowerShell)
python data_pipelines/crawl/vietstock_crawl_data_from_links.py `
    --links_file data_pipelines/crawl/vietstock_links_<start>_<end>.txt

# Linux / macOS
python3 data_pipelines/crawl/vietstock_crawl_data_from_links.py \
    --links_file data_pipelines/crawl/vietstock_links_<start>_<end>.txt
```

**Tham số:**

| Tham số | Mặc định | Mô tả |
| :--- | :--- | :--- |
| `--links_file` | `data_pipelines/crawl/vietstock_links_20260601_20260601_CHUAN.txt` | File chứa danh sách link (đường dẫn tương đối từ PROJECT_DIR) |
| `--debug` | tắt | In log chi tiết |
| `--head` | tắt | Hiện trình duyệt (bỏ cờ này để chạy headless) |

---

## Quy trình đầy đủ

```
Bước 1: Cào link  →  data_pipelines/crawl/vietstock_crawl_links.py
Bước 2: Cào data  →  data_pipelines/crawl/vietstock_crawl_data_from_links.py
```

---

## Lưu ý

- File output được git-ignore theo pattern `**/*.txt` và `**/*.jsonl`.  
  File nào kết thúc bằng `_CHUAN.*` là file mẫu/chuẩn và **được giữ lại** trong repo.
- Đặt tên output theo convention: `vietstock_links_DDMMYYYY_DDMMYYYY.txt` để dễ theo dõi.
