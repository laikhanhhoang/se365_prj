# Kế hoạch refactor `data_pipelines/` (trừ `crawl/`, `utils/`)

> Trạng thái: **ĐÃ TRIỂN KHAI XONG.** Xem quyết định cuối ở mục 6.

## 1. Vấn đề hiện tại (đã audit)

Taxonomy sự kiện đang bị định nghĩa lặp lại ở **4 nơi**, không đồng bộ với nhau:

| Nơi | Chứa gì | File |
| :--- | :--- | :--- |
| Filter | `event_name` (id→tên) + `keyword` (id→từ khóa) | `filter/_config.json`, `_config1.json`, `_config_test.json` |
| Prompt LLM | Mô tả văn xuôi + field cho từng event | `label/prompt1.txt` (22 event, đánh số 01–22) |
| Validate output | `EVENTS_FIELDS` (event_type→field) | `label/format_output.py` |
| Docs | Bảng schema | `README.md` (ngoài phạm vi refactor lần này) |

**Bug phát hiện được trong lúc audit:** `filter/_config.json` và `_config1.json` chỉ có 21 id (01–21), **thiếu hẳn keyword cho "Vay vốn"** — event này có field trong `EVENTS_FIELDS`/`prompt1.txt` nhưng không có keyword nào để lọc ở bước filter. Thực tế 201 mẫu "Vay vốn" đã lọt qua được là vì bài viết đó tình cờ trùng keyword của category khác (VD "Phát hành trái phiếu"), không phải do được lọc đúng — nghĩa là các bài chỉ nói về vay vốn (không kèm trái phiếu/tài sản khác) đang bị bỏ sót ở bước filter.

Ngoài ra `_config.json`/`_config_test.json` có keyword list **phong phú hơn** `_config1.json` (nhiều từ đồng nghĩa hơn) — xem mục Rủi ro.

## 2. Cấu trúc thư mục mới

```
data_pipelines/
├── crawl/                      (không đổi)
├── utils/                      (không đổi)
├── labelling/
│   ├── __init__.py
│   ├── data_schema.json        ← NGUỒN DUY NHẤT cho dataset schema + event taxonomy
│   ├── step01_preprocess.py    (thay label/preprocess.py — tổng quát hóa theo data_schema.json)
│   ├── step02_filter.py        (thay filter/filter_by_keywords.py)
│   ├── step03_auto_label_openai.py  (thay label/auto_label_openai.py — giữ nguyên logic/resume)
│   ├── step04_postprocess.py   (thay label/format_output.py)
│   ├── prompts/
│   │   ├── prompt1.txt          (đang dùng — step03)
│   │   └── prompt2.txt          (bản tham khảo/chuẩn, chưa gán vào step nào)
│   ├── logs/                    (log tự sinh khi chạy, gitignore)
│   └── samples/
│       ├── vietstock_crawled_data_20260601_20260601_CHUAN.jsonl
│       ├── vietstock_preprocessed_20260601_20260601_CHUAN.jsonl
│       ├── vietstock_labeled_raw_prompt1_20260601_20260601_CHUAN.jsonl
│       └── vietstock_labeled_20260601_20260601_CHUAN.jsonl
├── .env
├── .gitignore
└── _HOW_TO_RUN.md              (bổ sung thêm mục step01–04)
```

`filter/` và `label/` bị xoá sau khi di chuyển xong (dùng `git mv` để giữ lịch sử).

## 3. `data_schema.json` — thiết kế

```json
{
  "dataset": {
    "schema": ["id", "content"],
    "strict_required": "no"
  },
  "events": [
    {
      "name": "Chi trả cổ tức",
      "fields": ["ten_to_chuc", "hinh_thuc_co_tuc", "ty_le", "ngay_gd_khong_huong_quyen", "ngay_thanh_toan"],
      "keywords": ["cổ tức", "trả cổ tức", "chi trả cổ tức", "tạm ứng cổ tức", "chia cổ tức", "cổ tức bằng tiền", "cổ tức bằng cổ phiếu"]
    },
    {
      "name": "Phát hành thêm cổ phiếu",
      "fields": ["ten_to_chuc", "phuong_thuc_phat_hanh", "loai_co_phieu", "so_luong", "gia_phat_hanh", "tong_gia_tri", "ngay_chot_quyen"],
      "keywords": ["phát hành thêm cổ phiếu", "chào bán cổ phiếu", "phát hành riêng lẻ", "phát hành ra công chúng", "ESOP", "quyền mua cổ phần", "phát hành cổ phiếu tăng vốn"]
    },
    {
      "name": "Chia tách cổ phiếu",
      "fields": ["ten_to_chuc", "ty_le_thuc_hien", "ngay_gd_khong_huong_quyen"],
      "keywords": ["chia tách cổ phiếu", "tách cổ phiếu", "tỷ lệ chia tách"]
    },
    {
      "name": "Gộp cổ phiếu",
      "fields": ["ten_to_chuc", "ty_le_thuc_hien", "ngay_gd_khong_huong_quyen"],
      "keywords": ["gộp cổ phiếu", "hoán đổi cổ phiếu", "tỷ lệ gộp cổ phiếu"]
    },
    {
      "name": "Niêm yết",
      "fields": ["ten_to_chuc", "ma_co_phieu", "san_giao_dich", "so_luong_co_phieu", "ngay_hieu_luc"],
      "keywords": ["chính thức niêm yết", "lên sàn", "đăng ký niêm yết", "được niêm yết", "niêm yết cổ phiếu", "đưa vào giao dịch", "niêm yết lần đầu"]
    },
    {
      "name": "Hủy niêm yết",
      "fields": ["ten_to_chuc", "ma_co_phieu", "san_giao_dich", "ngay_hieu_luc"],
      "keywords": ["hủy niêm yết", "hủy đăng ký giao dịch", "rời sàn", "bị hủy niêm yết", "delisting"]
    },
    {
      "name": "Chuyển sàn",
      "fields": ["ten_to_chuc", "ma_co_phieu", "san_giao_dich", "san_giao_dich_cu", "so_luong_co_phieu", "ngay_hieu_luc"],
      "keywords": ["chuyển sàn", "chuyển niêm yết", "từ UPCoM lên HOSE", "từ UPCoM lên HNX", "từ HNX sang HOSE", "chuyển sang sàn"]
    },
    {
      "name": "Phát hành trái phiếu",
      "fields": ["ten_to_chuc", "loai_trai_phieu", "tong_gia_tri", "lai_suat", "ky_han", "ngay_phat_hanh"],
      "keywords": ["phát hành trái phiếu", "chào bán trái phiếu", "trái phiếu doanh nghiệp", "lô trái phiếu", "trái phiếu riêng lẻ"]
    },
    {
      "name": "Cổ đông thay đổi tỷ lệ sở hữu",
      "fields": ["ten_to_chuc", "ten_co_dong", "chieu_thay_doi", "ty_le_truoc", "ty_le_sau", "so_cp_thay_doi", "ngay_bat_dau"],
      "keywords": ["đăng ký mua cổ phiếu", "đăng ký bán cổ phiếu", "mua thêm cổ phần", "bán bớt cổ phần", "thay đổi tỷ lệ sở hữu", "giao dịch nội bộ", "cổ đông lớn đăng ký"]
    },
    {
      "name": "Cổ đông cầm cố cổ phiếu",
      "fields": ["ten_to_chuc", "ben_cam_co", "ben_nhan_cam_co", "so_luong_cp", "ngay_bat_dau", "ngay_ket_thuc"],
      "keywords": ["cầm cố cổ phiếu", "thế chấp cổ phiếu", "cầm cố cổ phần"]
    },
    {
      "name": "Cổ đông phong tỏa cổ phiếu",
      "fields": ["ten_to_chuc", "ten_co_dong", "so_luong_cp", "ngay_bat_dau", "ngay_ket_thuc", "co_quan_ra_lenh"],
      "keywords": ["phong tỏa cổ phiếu", "phong tỏa cổ phần", "bị phong tỏa cổ phiếu"]
    },
    {
      "name": "Thay đổi nhân sự chủ chốt",
      "fields": ["ten_to_chuc", "ten_nhan_su", "trang_thai", "chuc_vu", "nguoi_thay_the"],
      "keywords": ["bổ nhiệm", "miễn nhiệm", "từ nhiệm", "thôi chức", "thay đổi nhân sự", "thay đổi lãnh đạo", "bầu lại HĐQT", "bầu lại ban kiểm soát"]
    },
    {
      "name": "Lãnh đạo cấp cao qua đời",
      "fields": ["ten_to_chuc", "ten_lanh_dao", "chuc_vu", "con_lien_quan", "ngay_ghi_nhan"],
      "keywords": ["qua đời", "từ trần", "tử vong", "qua đời đột ngột", "lãnh đạo qua đời"]
    },
    {
      "name": "M&A",
      "fields": ["ben_mua", "ten_to_chuc", "loai_giao_dich", "ty_le_so_huu_truoc", "ty_le_so_huu_sau", "gia_tri_thuong_vu", "ngay_hoan_tat"],
      "keywords": ["mua lại", "sáp nhập", "thâu tóm", "thay đổi quyền kiểm soát", "nhà đầu tư chiến lược mua", "mua cổ phần chi phối"]
    },
    {
      "name": "Đầu tư",
      "fields": ["ten_to_chuc", "ten_cong_ty_dau_tu_vao", "ty_le_so_huu", "gia_tri_dau_tu", "muc_dich", "ngay_thuc_hien"],
      "keywords": ["rót vốn", "góp vốn", "hợp tác đầu tư", "đầu tư vào", "mua phần vốn góp", "đầu tư chiến lược"]
    },
    {
      "name": "Hợp đồng lớn",
      "fields": ["ten_to_chuc", "ten_doi_tac", "loai_hop_dong", "ten_du_an", "gia_tri_hop_dong", "thoi_gian_thuc_hien", "ngay_ky"],
      "keywords": ["ký kết hợp đồng", "trúng thầu", "hợp đồng hợp tác", "ký kết thỏa thuận", "ký hợp đồng"]
    },
    {
      "name": "Vay vốn",
      "fields": ["ten_to_chuc", "ben_cho_vay", "tong_gia_tri_khoan_vay", "muc_dich", "ky_han", "ben_bao_lanh", "ngay_ky"],
      "keywords": ["vay"]
    },
    {
      "name": "Tổn thất tài sản nghiêm trọng",
      "fields": ["ten_to_chuc", "mo_ta_su_co", "gia_tri_ton_that", "bao_hiem_boi_thuong", "ngay_cong_bo"],
      "keywords": ["thiệt hại tài sản", "cháy nổ", "hỏa hoạn", "tai nạn nghiêm trọng", "sự cố lớn", "mất mát tài sản"]
    },
    {
      "name": "Bồi thường lớn cho bên ngoài",
      "fields": ["ten_to_chuc", "ben_nhan_boi_thuong", "so_tien", "ly_do", "ngay_cong_bo"],
      "keywords": ["bồi thường", "bồi hoàn", "đền bù thiệt hại", "thanh toán bồi thường"]
    },
    {
      "name": "Vấn đề pháp lý với tổ chức",
      "fields": ["thuc_the_bi_xu_ly", "co_quan_xu_phat", "ly_do_vi_pham", "hinh_thuc_xu_phat", "so_tien_phat", "ngay_quyet_dinh"],
      "keywords": ["bị xử phạt", "bị thanh tra", "bị kiện", "vi phạm hành chính", "bị cưỡng chế", "tranh chấp pháp lý"]
    },
    {
      "name": "Vấn đề pháp lý với cá nhân",
      "fields": ["ten_ca_nhan", "ten_to_chuc", "chuc_vu", "toi_danh", "loai_hanh_dong", "co_quan_thuc_thi", "ngay_thuc_thi"],
      "keywords": ["bị khởi tố", "bị bắt", "bị tạm giam", "bị điều tra", "bị tuyên phạt", "bị kết tội"]
    },
    {
      "name": "Phá sản",
      "fields": ["ten_to_chuc", "loai_hanh_dong", "nganh_nghe", "toa_an_thu_ly", "ngay_cong_bo", "ngay_phan_quyet"],
      "keywords": ["phá sản", "mất khả năng thanh toán", "vỡ nợ", "giải thể doanh nghiệp", "tái cơ cấu nợ bắt buộc"]
    }
  ]
}
```

Ghi chú thiết kế:
- Bỏ hệ id số "01"–"22" — dùng thẳng `name` làm khoá định danh (không cần bảng tra id↔tên như trước).
- `fields` lấy nguyên từ `EVENTS_FIELDS` hiện tại trong `format_output.py`.
- `keywords` lấy theo bản **phong phú hơn** (`_config.json`/`_config_test.json`) thay vì bản `_config1.json` đang chạy — xem Rủi ro #2.
- **Không** đưa mô tả văn xuôi (câu giải thích nghiệp vụ) vào đây — phần đó vẫn nằm trong `prompts/prompt1.txt`, chỉnh tay khi cần (đúng theo yêu cầu, chỉ "name/fields/keywords").

## 4. Từng step sau refactor

Tất cả 4 step đều có thêm key `"log"` (optional) trong config dict ở `__main__` — đường dẫn 1 file `.txt`. Khi có, mỗi step sẽ ghi log tóm tắt (giống bảng tổng kết hiện có ở filter) **kèm snapshot toàn bộ nội dung `data_schema.json` tại thời điểm chạy** vào cuối file log — dùng `build_run_log_text()` (helper chung, đặt ở `utils/file_processor.py`). Mục đích: vì `data_schema.json` là tài nguyên chung có thể đổi theo thời gian, log giúp biết chính xác schema nào đã tạo ra output nào, mà không cần giữ nhiều file config version khác nhau.

### `step01_preprocess.py` (thay `preprocess.py`)
- Đọc `dataset.schema` + `dataset.strict_required` từ `data_schema.json`.
- `strict_required == "yes"`: validate record có đúng và chỉ có các field trong `schema`; ghi thẳng ra output (không transform), WARN nếu lệch.
- `strict_required == "no"`: với mỗi record — **chỉ tự sinh `id` tăng dần nếu record chưa có `id`** (record đã có `id` thì giữ nguyên); `content` = nối tất cả field còn lại hiện có trong record (kể cả `link` — không cần lọc field kỹ, theo yêu cầu), bỏ field rỗng/None; sau đó chỉ giữ lại field nằm trong `schema`.
- Bỏ hẳn `formatted_fields`/`deleted_fields` khỏi config script — nay đọc từ `data_schema.json`.
- Không resume/append (giữ theo thay đổi đã áp dụng ở `preprocess.py` cũ — ghi đè mỗi lần chạy).

### `step02_filter.py` (thay `filter_by_keywords.py`)
- Đọc `events[].name` + `events[].keywords` từ `data_schema.json` để build dict keyword — **không còn file config riêng** (`configs/` bị bỏ hoàn toàn, càng nhiều file càng rối).
- Config của step nằm inline trong `__main__` (giống 3 step khác): chỉ còn `"in_out"`, `"combine"` (optional), `"log"` (optional).
- Logic lọc (`filter_by_keywords()`, matching theo `title/head/body`) giữ nguyên, đổi key đếm/log từ id số sang tên event (không cần bảng `event_name` tra id↔tên nữa).

### `step03_auto_label_openai.py` (thay `auto_label_openai.py`)
- Giữ nguyên 100% logic, kể cả resume/`_get_existing_ids` (đã xác nhận giữ nguyên — tốn API, không giống step01/04 là xử lý local nhanh).
- Chỉ đổi đường dẫn `prompt_file` sang `labelling/prompts/prompt1.txt`, thêm `"log"` (optional) vào config.

### `step04_postprocess.py` (thay `format_output.py`)
- Đọc `events[].name` + `events[].fields` từ `data_schema.json` thay cho `EVENTS_FIELDS` hard-code.
- Giữ nguyên logic đã thêm trước đó: bỏ event có `event_type` lạ (không có trong `data_schema.json`), ghi đè output mỗi lần chạy (không resume).
- `raw_field`/`output_field` (`"label_raw"`/`"events"`) **không** phải field của `data_schema.json` (tên field kỹ thuật nối giữa 2 step, không phải taxonomy) — vẫn để trong config script, không tính là duplicate. Thêm `"log"` (optional).

## 5. Bảng di chuyển file (dùng `git mv` để giữ lịch sử)

| File cũ | File mới |
| :--- | :--- |
| `filter/filter_by_keywords.py` | `labelling/step02_filter.py` |
| `filter/_config.json`, `_config1.json`, `_config_test.json` | xoá (nội dung "in_out"/"combine" chuyển vào inline config trong `step02_filter.py`; `event_name`/`keyword` chuyển vào `data_schema.json`) |
| `filter/_log*.txt` | xoá (log tự sinh lại khi chạy `step02`, ghi vào `labelling/logs/`) |
| `filter/__init__.py` | `labelling/__init__.py` |
| `label/preprocess.py` | `labelling/step01_preprocess.py` |
| `label/auto_label_openai.py` | `labelling/step03_auto_label_openai.py` |
| `label/format_output.py` | `labelling/step04_postprocess.py` |
| `label/prompt1.txt` | `labelling/prompts/prompt1.txt` |
| `label/prompt2.txt` | `labelling/prompts/prompt2.txt` |
| `label/vietstock_*_CHUAN.jsonl` (4 file) | `labelling/samples/` |
| _(mới)_ | `labelling/data_schema.json` |
| _(mới)_ | `labelling/logs/` |

Sau khi di chuyển xong: xoá `data_pipelines/filter/`, `data_pipelines/label/`.

## 6. Quyết định cuối (đã chốt)

1. **`id` tự sinh khi `strict_required="no"`**: chỉ tự sinh khi record **thật sự thiếu** `id`; nếu record đã có `id` thì giữ nguyên.
2. **Cấu trúc config**: bỏ hoàn toàn folder `configs/` — mỗi step dùng config inline trong `__main__` (giống pattern đã có ở `preprocess.py`/`auto_label_openai.py`/`format_output.py`), thêm key `"log"` (đường dẫn `.txt`) để in log tóm tắt + snapshot `data_schema.json` tại thời điểm chạy.
3. **Keyword "Vay vốn"**: dùng `["vay"]` — 1 từ khóa duy nhất, đơn giản, ưu tiên recall.
4. **`content` gộp toàn bộ field kể cả `link`**: chấp nhận, không cần lọc field kỹ.
5. **Phạm vi**: chỉ refactor code trong `data_pipelines/` — không đụng tới dữ liệu cũ trong `data/` (không migrate lại 1714 mẫu đã label).
6. **`prompt2.txt`**: giữ lại trong `prompts/` làm tài nguyên chuẩn để tham khảo (mô tả sự kiện giống `prompt1.txt`, chỉ thêm 1 chỉ dẫn xử lý thông tin bị điều chỉnh trong bài).
7. **README.md**: cập nhật cùng lần refactor này — verify bảng schema vẫn khớp `data_schema.json`, bổ sung mục hướng dẫn chạy step01–04 (hiện README/`_HOW_TO_RUN.md` mới chỉ có bước crawl).
8. **2 đề xuất gộp sự kiện pháp lý / bồi thường-tổn thất**: để sau, không áp dụng trong lần refactor này.

## 7. Thứ tự triển khai

1. Tạo `labelling/data_schema.json`.
2. Thêm helper `build_run_log_text()` vào `utils/file_processor.py`.
3. `git mv` file di chuyển được (prompts, samples, `__init__.py`) theo bảng mục 5.
4. Viết `step01_preprocess.py`, `step02_filter.py`, `step04_postprocess.py` theo logic đọc từ `data_schema.json`; `step03` chỉ đổi path + thêm `"log"`.
5. Xoá `data_pipelines/filter/`, `data_pipelines/label/` (sau khi đã chuyển hết).
6. Cập nhật `_HOW_TO_RUN.md` và `README.md`.
7. Chạy thử toàn bộ pipeline trên `labelling/samples/*_CHUAN.jsonl` để verify.
