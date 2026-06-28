# Thảo luận chỉnh sửa Schema

Ghi lại các vấn đề đang thảo luận. Chưa chốt — sẽ cập nhật README sau khi thống nhất.

---

# Vấn đề

## 1. Tách event 06 thành 3 event riêng

**Hiện tại:** Event 06 gộp chung `loai_hanh_dong` (niêm yết / hủy niêm yết / chuyển sàn) vào 1 schema.

**Vấn đề:** Các trường cần thiết khác nhau theo từng loại hành động → dẫn đến nhiều trường conditional → LLM dễ hallucinate.

**Đề xuất:** Tách thành 3 event riêng:

| | 06a. Niêm yết | 06b. Hủy niêm yết | 06c. Chuyển sàn |
|---|---|---|---|
| `ten_to_chuc` | ✓ | ✓ | ✓ |
| `ma_co_phieu` | ✓ | ✓ | ✓ |
| `san_giao_dich` | ✓ | ✓ | ✓ (sàn mới) |
| `san_giao_dich_cu` | ✗ | ✗ | ✓ |
| `so_luong_co_phieu` | ✓ | ✗ | ✓ |
| `ngay_hieu_luc` | ✓ | ✓ | ✓ |
| `ly_do` | ✗ | ✓ | ✗ |

---

## 2. Thêm trường `ma_co_phieu` và `so_luong_co_phieu` vào event 06

**Hiện tại:** Schema 06 không có `ma_co_phieu` và `so_luong_co_phieu`.

**Vấn đề:**
- `ma_co_phieu` (VD: BVB) khác với `ten_to_chuc` (BVBank) — cần để lookup, không nên bỏ qua.
- `so_luong_co_phieu` hầu như luôn có trong thông báo niêm yết chính thức.

**Đề xuất:** Thêm cả 2 trường, áp dụng theo bảng trên (optional với hủy niêm yết).

---

## 3. Định nghĩa trường `confidence`

**Hiện tại:** `confidence` (high/medium/low) không có tiêu chí rõ ràng.

**Đề xuất:** Định nghĩa theo trạng thái xác nhận của sự kiện:
- `high` — đã xảy ra / được xác nhận chính thức
- `medium` — kế hoạch / đang chờ phê duyệt
- `low` — tin đồn / chưa xác minh

---

## 4. Xử lý bài báo không có sự kiện

**Đề xuất:** Dùng 2 giá trị phân biệt thay vì `null`:
- `event_type: "NONE"` — bài thực sự không có sự kiện (phân tích thị trường, nhận định chung)
- `event_type: "UNCERTAIN"` — bài có thể có sự kiện nhưng LLM không extract được (bài mơ hồ, thiếu thông tin)

---

## 5. Không dùng trường `note` tự do

**Vấn đề:** Trường free-text → LLM dễ hallucinate, diễn giải thay vì trích dẫn.

**Đề xuất:** Thay bằng:
- `raw_quote` — copy nguyên văn từ bài, không tự sinh
- `missing_fields` — ghi lý do tại sao trường bị null (VD: `{"so_luong": "bài chưa công bố chính thức"}`)

---

## 7. Tách event 07 thành 2 event riêng

**Hiện tại:** Event 07 gộp chung M&A và Góp vốn chiến lược.

**Vấn đề:** 2 loại này khác nhau về bản chất, chiều hướng và trường cần thiết:
- M&A = **inbound** — bên ngoài mua/thâu tóm công ty niêm yết
- Góp vốn = **outbound** — công ty niêm yết đem vốn đầu tư vào chỗ khác

Gộp chung còn gây overlap với event 09 (Thay đổi tỷ lệ sở hữu cổ đông).

**Đề xuất:** Tách thành 2 event:

**07a. M&A** — bên ngoài mua/sáp nhập vào công ty niêm yết
```
ben_mua · ten_to_chuc · loai_giao_dich (mua lại/sáp nhập)
· ty_le_so_huu_truoc · ty_le_so_huu_sau · gia_tri_thuong_vu · ngay_hoan_tat
```

**07b. Đầu tư / Góp vốn ra ngoài** — công ty niêm yết đầu tư vào công ty khác
```
ten_to_chuc · ten_cong_ty_dau_tu_vao · ty_le_so_huu
· gia_tri_dau_tu · muc_dich · ngay_thuc_hien
```

**Ranh giới rõ sau khi tách:**
- **07a** — bên ngoài mua vào công ty niêm yết (thay đổi quyền kiểm soát)
- **07b** — công ty niêm yết đầu tư ra ngoài
- **09** — cổ đông hiện hữu mua thêm/bán bớt trên thị trường

---

## 6. Boundary case event 13 — Lãnh đạo cấp cao qua đời

**Vấn đề:** Bài đề cập cựu lãnh đạo qua đời — có nên label event 13 không?

**Đề xuất:** Chỉ label event 13 nếu người đó còn ít nhất 1 trong các điều kiện:
- Còn là cổ đông lớn
- Là sáng lập viên
- Còn giữ vai trò cố vấn chính thức

Thêm trường `con_lien_quan: bool` + `ly_do_lien_quan` để ghi nhận.

---

# Schema đề xuất

## Danh sách event

| id | Tên event |
|---|---|
| **— Cổ tức —** | |
| 01 | Chi trả cổ tức |
| **— Cổ phiếu —** | |
| 02 | Phát hành thêm cổ phiếu |
| 03 | Chia tách cổ phiếu |
| 04 | Gộp cổ phiếu |
| 05 | Niêm yết |
| 06 | Hủy niêm yết |
| 07 | Chuyển sàn |
| **— Trái phiếu —** | |
| 08 | Phát hành trái phiếu |
| **— Cổ đông —** | |
| 09 | Cổ đông thay đổi tỷ lệ sở hữu |
| 10 | Cổ đông cầm cố cổ phiếu |
| 11 | Cổ đông phong tỏa cổ phiếu |
| **— Nhân sự —** | |
| 12 | Thay đổi nhân sự chủ chốt |
| 13 | Lãnh đạo cấp cao qua đời |
| **— Đầu tư / Kiếm tiền —** | |
| 14 | M&A |
| 15 | Đầu tư |
| 16 | Hợp đồng lớn |
| **— Tổn thất —** | |
| 17 | Tổn thất tài sản nghiêm trọng |
| 18 | Bồi thường lớn cho bên ngoài |
| **— Pháp lý —** | |
| 19 | Vấn đề pháp lý với tổ chức |
| 20 | Vấn đề pháp lý với cá nhân |
| 21 | Phá sản |

---

## Từ khóa lọc

Mẫu tin được **giữ lại** nếu `title + head + body` chứa ít nhất 1 cụm từ trong nhóm tương ứng.
Script lọc: `data_pipelines/filter_by_event_keywords.py`

| id | Tên event | Cụm từ lọc |
|---|---|---|
| **— Cổ tức —** | | |
| 01 | Chi trả cổ tức | cổ tức, trả cổ tức, chi trả cổ tức, tạm ứng cổ tức, chia cổ tức, cổ tức bằng tiền, cổ tức bằng cổ phiếu |
| **— Cổ phiếu —** | | |
| 02 | Phát hành thêm cổ phiếu | phát hành thêm cổ phiếu, chào bán cổ phiếu, phát hành riêng lẻ, phát hành ra công chúng, ESOP, quyền mua cổ phần, phát hành cổ phiếu tăng vốn |
| 03 | Chia tách cổ phiếu | chia tách cổ phiếu, tách cổ phiếu, tỷ lệ chia tách |
| 04 | Gộp cổ phiếu | gộp cổ phiếu, hoán đổi cổ phiếu, tỷ lệ gộp cổ phiếu |
| 05 | Niêm yết | chính thức niêm yết, lên sàn, đăng ký niêm yết, được niêm yết, niêm yết cổ phiếu, đưa vào giao dịch, niêm yết lần đầu |
| 06 | Hủy niêm yết | hủy niêm yết, hủy đăng ký giao dịch, rời sàn, bị hủy niêm yết, delisting |
| 07 | Chuyển sàn | chuyển sàn, chuyển niêm yết, từ UPCoM lên HOSE, từ UPCoM lên HNX, từ HNX sang HOSE, chuyển sang sàn |
| **— Trái phiếu —** | | |
| 08 | Phát hành trái phiếu | phát hành trái phiếu, chào bán trái phiếu, trái phiếu doanh nghiệp, lô trái phiếu, trái phiếu riêng lẻ |
| **— Cổ đông —** | | |
| 09 | Cổ đông thay đổi tỷ lệ sở hữu | đăng ký mua cổ phiếu, đăng ký bán cổ phiếu, mua thêm cổ phần, bán bớt cổ phần, thay đổi tỷ lệ sở hữu, giao dịch nội bộ, cổ đông lớn đăng ký |
| 10 | Cổ đông cầm cố cổ phiếu | cầm cố cổ phiếu, thế chấp cổ phiếu, cầm cố cổ phần |
| 11 | Cổ đông phong tỏa cổ phiếu | phong tỏa cổ phiếu, phong tỏa cổ phần, bị phong tỏa cổ phiếu |
| **— Nhân sự —** | | |
| 12 | Thay đổi nhân sự chủ chốt | bổ nhiệm, miễn nhiệm, từ nhiệm, thôi chức, thay đổi nhân sự, thay đổi lãnh đạo, bầu lại HĐQT, bầu lại ban kiểm soát |
| 13 | Lãnh đạo cấp cao qua đời | qua đời, từ trần, tử vong, qua đời đột ngột, lãnh đạo qua đời |
| **— Đầu tư / Kiếm tiền —** | | |
| 14 | M&A | mua lại, sáp nhập, thâu tóm, thay đổi quyền kiểm soát, nhà đầu tư chiến lược mua, mua cổ phần chi phối |
| 15 | Đầu tư | rót vốn, góp vốn, hợp tác đầu tư, đầu tư vào, mua phần vốn góp, đầu tư chiến lược |
| 16 | Hợp đồng lớn | ký kết hợp đồng, trúng thầu, hợp đồng hợp tác, ký kết thỏa thuận, ký hợp đồng |
| **— Tổn thất —** | | |
| 17 | Tổn thất tài sản nghiêm trọng | thiệt hại tài sản, cháy nổ, hỏa hoạn, tai nạn nghiêm trọng, sự cố lớn, mất mát tài sản |
| 18 | Bồi thường lớn cho bên ngoài | bồi thường, bồi hoàn, đền bù thiệt hại, thanh toán bồi thường |
| **— Pháp lý —** | | |
| 19 | Vấn đề pháp lý với tổ chức | bị xử phạt, bị thanh tra, bị kiện, vi phạm hành chính, bị cưỡng chế, tranh chấp pháp lý, bị điều tra (công ty) |
| 20 | Vấn đề pháp lý với cá nhân | bị khởi tố, bị bắt, bị tạm giam, bị điều tra (cá nhân), bị tuyên phạt, bị kết tội |
| 21 | Phá sản | phá sản, mất khả năng thanh toán, vỡ nợ, giải thể doanh nghiệp, tái cơ cấu nợ bắt buộc |

> **Lưu ý thiết kế:**
> - Các cụm từ được chọn đủ đặc trưng để tránh nhầm lẫn giữa các event (VD: "cổ tức bằng cổ phiếu" ≠ "phát hành thêm cổ phiếu").
> - Event 13 (Lãnh đạo qua đời) cần LLM kiểm tra thêm điều kiện `con_lien_quan` sau khi lọc sơ bộ.
> - Event 19 và 20 dùng ghi chú `(công ty)` / `(cá nhân)` để phân biệt chủ thể — script xử lý theo từ khóa riêng biệt, không dùng ghi chú.
> - Một bài có thể khớp nhiều event → `rule_category` là list.

---

# Label

## 1. Schema mỗi event instance

Mỗi event được extract là 1 object JSON với cấu trúc cố định:

```json
{
  "event_type": "12",
  "event_name": "Thay đổi nhân sự chủ chốt",
  "is_main_event": true,
  "confidence": "high",
  "date": "2023-01-03",
  "evidence": "bổ nhiệm ông Loic Faussier làm Tổng Giám đốc",
  "fields": {
    "entity": "SeABank",
    "person": "Loic Faussier",
    "role": "Tổng Giám đốc"
  }
}
```

| Trường | Bắt buộc | Mô tả |
|---|---|---|
| `event_type` | ✓ | ID event theo danh sách (01–21), hoặc `"NONE"` / `"UNCERTAIN"` |
| `event_name` | ✓ | Tên event tương ứng với ID |
| `is_main_event` | ✓ | `true` nếu là event chính được đề cập ở `head` |
| `confidence` | ✓ | `high` / `medium` / `low` — xem định nghĩa bên dưới |
| `date` | ✓ | Ngày xảy ra, format `YYYY-MM-DD` / `YYYY-MM` / `YYYY` |
| `evidence` | ✓ | Trích nguyên văn câu/cụm từ từ bài làm bằng chứng |
| `fields` | ✓ | Các trường dữ liệu tùy theo `event_type` |

---

## 2. Định nghĩa `confidence`

| Mức | Định nghĩa | Ví dụ |
|---|---|---|
| `high` | Sự kiện đã xảy ra / được xác nhận chính thức trong bài. Có thể thiếu một số field nhưng bản thân sự kiện là chắc chắn. | "03/01/2023, bổ nhiệm ông Loic làm TGĐ" |
| `medium` | Sự kiện xuất hiện trong bài nhưng là kế hoạch, dự kiến, hoặc đang chờ phê duyệt — chưa hoàn tất. | "SeABank dự kiến phát hành thêm cổ phiếu trong Q2" |
| `low` | Model suy luận ra từ ngữ cảnh, sự kiện không được nêu trực tiếp trong bài. | Bài nói doanh thu giảm mạnh → model suy ra có tổn thất tài sản |

---

## 3. Tiêu chí extract event

**Nguồn:** Extract từ toàn bộ bài (`title + head + body`), không chỉ `head`.

**Một thông tin được coi là event khi thỏa mãn cả 3:**
1. Có **chủ thể + hành động** rõ ràng (không mơ hồ)
2. Là **tin mới hoặc sự kiện cụ thể**, không phải lịch sử nền / giới thiệu nhân vật
3. Thuộc **21 event types** đã định nghĩa

**Không extract khi:**
- Thông tin chỉ là bối cảnh / lý lịch nhân vật (VD: "ông từng làm HSBC 10 năm")
- Sự kiện quá chung chung, không có đủ thông tin để điền fields
- Không thuộc bất kỳ event type nào trong danh sách

---

## 4. Số lượng event per bài

Không giới hạn cứng. Nguyên tắc:

- Bài 1 event chính → extract 1
- Bài có nhiều event rõ ràng → extract hết
- Bài có nhiều sự kiện lịch sử nền → chỉ lấy sự kiện mới, bỏ background

**Bài không có event:** Dùng 2 giá trị đặc biệt thay vì list rỗng:
- `event_type: "NONE"` — bài thực sự không có sự kiện (phân tích thị trường, nhận định)
- `event_type: "UNCERTAIN"` — bài có thể có sự kiện nhưng LLM không extract được

---

## 5. Chính sách dữ liệu training

| Confidence | Đưa vào train? | Ghi chú |
|---|---|---|
| `high` | ✓ Luôn giữ | Label sạch nhất |
| `medium` | ✓ Giữ | Model học được "event dự kiến" |
| `low` | ⚠ Có chọn lọc | Chỉ giữ nếu human reviewer confirm; bỏ nếu annotation không nhất quán |

**Giai đoạn 1:** Train với `high` + `medium` để ổn định model.
**Giai đoạn 2:** Thêm dần `low` sau khi có baseline tốt và annotation `low` đã review kỹ.

---

## 6. Data split (~9000 bài)

```
Train :  7,200 bài  (80%)
Val   :    900 bài  (10%)  ← tune hyperparams
Test  :    900 bài  (10%)  ← đánh giá cuối, không dùng trong quá trình train
```

Chia **stratified theo `main_event_type`** để đảm bảo event hiếm có mặt ở cả 3 split.

```python
from sklearn.model_selection import train_test_split

train, temp = train_test_split(data, test_size=0.2, stratify=[d["main_event_type"] for d in data])
val, test   = train_test_split(temp, test_size=0.5, stratify=[d["main_event_type"] for d in temp])
```

**Ngưỡng samples tối thiểu để fine-tune có hiệu quả:**

| Số samples | Kết quả kỳ vọng |
|---|---|
| < 50 | Không học được |
| 50–200 | Học được nhưng không ổn định |
| 200–500 | Baseline chấp nhận được |
| 500+ | Tốt |

Event type có < 50 samples → cân nhắc gộp vào nhóm cha hoặc augment.

---

## 7. Đánh giá chất lượng (Metrics)

Đánh giá theo 3 tầng:

**Tầng 1 — Event Detection F1:** Model có nhận ra đúng event types không?
```
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * P * R / (P + R)
```

**Tầng 2 — Event Matching:** Dùng `(event_type, date, entity)` làm key để match event instance giữa output và ground truth.

**Tầng 3 — Field Accuracy:** Với mỗi event đã match, so sánh từng field:
- **Exact match** cho các trường ngắn (tên, mã, số)
- **Token F1** cho các trường text dài (`evidence`, `ly_do`)

**Metric tổng hợp giai đoạn đầu:** Event type F1 + Field exact match rate (trên các event đã detect đúng).
